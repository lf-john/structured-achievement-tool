"""
Tests for IntentVerifier — diff-based intent verification.

Verifies that git diffs match the stated intent of story descriptions
and acceptance criteria using pure Python heuristics.
"""

from src.execution.intent_verifier import (
    IntentVerificationResult,
    IntentVerifier,
    _classify_intent,
    _extract_referenced_files,
    _parse_diff_stats,
)

# --- Fixtures / Helpers ---


def _make_new_file_diff(filename: str, content_lines: int = 5) -> str:
    """Generate a unified diff for a newly created file."""
    lines = "\n".join(f"+line {i}" for i in range(1, content_lines + 1))
    return (
        f"diff --git a/{filename} b/{filename}\n"
        f"new file mode 100644\n"
        f"--- /dev/null\n"
        f"+++ b/{filename}\n"
        f"@@ -0,0 +1,{content_lines} @@\n"
        f"{lines}\n"
    )


def _make_modify_diff(filename: str, additions: int = 3, deletions: int = 1) -> str:
    """Generate a unified diff for a modified file."""
    del_lines = "\n".join(f"-old line {i}" for i in range(1, deletions + 1))
    add_lines = "\n".join(f"+new line {i}" for i in range(1, additions + 1))
    return (
        f"diff --git a/{filename} b/{filename}\n"
        f"--- a/{filename}\n"
        f"+++ b/{filename}\n"
        f"@@ -1,{deletions} +1,{additions} @@\n"
        f"{del_lines}\n"
        f"{add_lines}\n"
    )


def _make_delete_file_diff(filename: str, content_lines: int = 5) -> str:
    """Generate a unified diff for a deleted file."""
    lines = "\n".join(f"-line {i}" for i in range(1, content_lines + 1))
    return (
        f"diff --git a/{filename} b/{filename}\n"
        f"deleted file mode 100644\n"
        f"--- a/{filename}\n"
        f"+++ /dev/null\n"
        f"@@ -1,{content_lines} +0,0 @@\n"
        f"{lines}\n"
    )


# --- Test _classify_intent ---


class TestClassifyIntent:
    def test_create_verbs(self):
        assert _classify_intent("Create a new authentication module") == "create"
        assert _classify_intent("Add rate limiting to the API") == "create"
        assert _classify_intent("Implement diff-based verification") == "create"
        assert _classify_intent("Build the user dashboard") == "create"

    def test_fix_verbs(self):
        assert _classify_intent("Fix the login timeout bug") == "fix"
        assert _classify_intent("Resolve database connection leak") == "fix"
        assert _classify_intent("Patch the security vulnerability in auth.py") == "fix"

    def test_update_verbs(self):
        assert _classify_intent("Update the configuration parser") == "update"
        assert _classify_intent("Refactor the test runner module") == "update"
        assert _classify_intent("Improve error handling in git_manager.py") == "update"

    def test_delete_verbs(self):
        assert _classify_intent("Delete deprecated helper functions") == "delete"
        assert _classify_intent("Remove unused imports from utils.py") == "delete"

    def test_expand_verbs(self):
        assert _classify_intent("Expand the test coverage for auth module") == "expand"
        assert _classify_intent("Extend the API with new endpoints") == "expand"

    def test_unknown_intent(self):
        assert _classify_intent("The quick brown fox") == "unknown"
        assert _classify_intent("") == "unknown"

    def test_first_line_priority(self):
        # The first line says "Fix" even though body says "Create"
        text = "Fix the broken parser\nThis will create new tests"
        assert _classify_intent(text) == "fix"


# --- Test _parse_diff_stats ---


class TestParseDiffStats:
    def test_new_file(self):
        diff = _make_new_file_diff("src/new_module.py", 10)
        stats = _parse_diff_stats(diff)
        assert "src/new_module.py" in stats["new_files"]
        assert stats["additions"] == 10
        assert stats["deletions"] == 0

    def test_deleted_file(self):
        diff = _make_delete_file_diff("src/old_module.py", 8)
        stats = _parse_diff_stats(diff)
        assert "src/old_module.py" in stats["deleted_files"]
        assert stats["deletions"] == 8
        assert stats["additions"] == 0

    def test_modified_file(self):
        diff = _make_modify_diff("src/existing.py", additions=5, deletions=2)
        stats = _parse_diff_stats(diff)
        assert "src/existing.py" in stats["modified_files"]
        assert stats["additions"] == 5
        assert stats["deletions"] == 2

    def test_multiple_files(self):
        diff = (
            _make_new_file_diff("src/a.py", 3)
            + _make_modify_diff("src/b.py", 2, 1)
            + _make_delete_file_diff("src/c.py", 4)
        )
        stats = _parse_diff_stats(diff)
        assert "src/a.py" in stats["new_files"]
        assert "src/b.py" in stats["modified_files"]
        assert "src/c.py" in stats["deleted_files"]

    def test_empty_diff(self):
        stats = _parse_diff_stats("")
        assert stats["new_files"] == []
        assert stats["deleted_files"] == []
        assert stats["modified_files"] == []
        assert stats["additions"] == 0
        assert stats["deletions"] == 0


# --- Test _extract_referenced_files ---


class TestExtractReferencedFiles:
    def test_backtick_quoted(self):
        text = "Fix the bug in `src/execution/git_manager.py` and update `tests/test_git.py`"
        files = _extract_referenced_files(text)
        assert "src/execution/git_manager.py" in files
        assert "tests/test_git.py" in files

    def test_bare_paths(self):
        text = "Modify src/daemon.py to handle edge cases"
        files = _extract_referenced_files(text)
        assert "src/daemon.py" in files

    def test_no_files(self):
        text = "Improve the overall system performance"
        files = _extract_referenced_files(text)
        assert len(files) == 0

    def test_ignores_urls(self):
        text = "See https://example.com/path.html for details"
        files = _extract_referenced_files(text)
        # Should not include the URL
        for f in files:
            assert not f.startswith("http")


# --- Test IntentVerifier.verify_intent ---


class TestVerifyIntentCreate:
    def setup_method(self):
        self.verifier = IntentVerifier()

    def test_create_with_new_files_aligned(self):
        """Create story with new files in diff -> aligned."""
        diff = _make_new_file_diff("src/execution/intent_verifier.py", 50)
        result = self.verifier.verify_intent(
            story_description="Create a new intent verification module",
            acceptance_criteria=["New file src/execution/intent_verifier.py exists"],
            diff_text=diff,
            modified_files=["src/execution/intent_verifier.py"],
        )
        assert result.aligned is True
        assert result.confidence > 0.5
        assert len(result.issues) == 0

    def test_create_with_no_new_files_misaligned(self):
        """Create story with no new files in diff -> misaligned."""
        diff = _make_modify_diff("src/existing.py", 5, 2)
        result = self.verifier.verify_intent(
            story_description="Create a new logging framework",
            acceptance_criteria=["New logging module exists"],
            diff_text=diff,
            modified_files=["src/existing.py"],
        )
        assert result.aligned is False
        assert any("no new files" in issue.lower() for issue in result.issues)


class TestVerifyIntentFix:
    def setup_method(self):
        self.verifier = IntentVerifier()

    def test_fix_modified_right_file_aligned(self):
        """Fix story that modified the right file -> aligned."""
        diff = _make_modify_diff("src/execution/git_manager.py", 3, 2)
        result = self.verifier.verify_intent(
            story_description="Fix the commit hash parsing in `src/execution/git_manager.py`",
            acceptance_criteria=["Commit hash is correctly extracted"],
            diff_text=diff,
            modified_files=["src/execution/git_manager.py"],
        )
        assert result.aligned is True
        assert len(result.issues) == 0

    def test_fix_no_files_modified_misaligned(self):
        """Fix story that didn't modify any file -> misaligned."""
        # Use a diff that only adds a new file (no modifications)
        diff = _make_new_file_diff("docs/notes.txt", 2)
        result = self.verifier.verify_intent(
            story_description="Fix the timeout bug in src/daemon.py",
            acceptance_criteria=["Timeout is handled correctly"],
            diff_text=diff,
            modified_files=[],
        )
        assert result.aligned is False
        assert any("no files were modified" in issue.lower() for issue in result.issues)


class TestVerifyIntentExpand:
    def setup_method(self):
        self.verifier = IntentVerifier()

    def test_expand_file_grew_aligned(self):
        """Expand story where file grew (more additions than deletions) -> aligned."""
        diff = _make_modify_diff("src/workflows/base_workflow.py", additions=20, deletions=3)
        result = self.verifier.verify_intent(
            story_description="Expand the verification checks in base_workflow.py",
            acceptance_criteria=["New verification checks added"],
            diff_text=diff,
            modified_files=["src/workflows/base_workflow.py"],
        )
        assert result.aligned is True
        assert len(result.issues) == 0

    def test_expand_file_shrank_misaligned(self):
        """Expand story where file shrank -> misaligned."""
        diff = _make_modify_diff("src/module.py", additions=2, deletions=10)
        result = self.verifier.verify_intent(
            story_description="Expand the error handling in module.py",
            acceptance_criteria=["More error cases covered"],
            diff_text=diff,
            modified_files=["src/module.py"],
        )
        assert result.aligned is False
        assert any("did not grow" in issue.lower() for issue in result.issues)


class TestVerifyIntentDelete:
    def setup_method(self):
        self.verifier = IntentVerifier()

    def test_delete_files_removed_aligned(self):
        """Delete story where files were removed -> aligned."""
        diff = _make_delete_file_diff("src/deprecated_util.py", 30)
        result = self.verifier.verify_intent(
            story_description="Delete the deprecated utility module",
            acceptance_criteria=["deprecated_util.py no longer exists"],
            diff_text=diff,
            modified_files=[],
        )
        assert result.aligned is True

    def test_delete_nothing_removed_misaligned(self):
        """Delete story where nothing was removed -> misaligned."""
        diff = _make_new_file_diff("src/new.py", 5)
        result = self.verifier.verify_intent(
            story_description="Remove the legacy API endpoints",
            acceptance_criteria=["Legacy endpoints are gone"],
            diff_text=diff,
            modified_files=["src/new.py"],
        )
        assert result.aligned is False
        assert any("no files were deleted" in issue.lower() for issue in result.issues)


class TestVerifyIntentScopeCreep:
    def setup_method(self):
        self.verifier = IntentVerifier()

    def test_extra_files_modified_warnings(self):
        """Scope creep: extra files modified that aren't in the story -> warnings."""
        diff = _make_modify_diff("src/daemon.py", 3, 1) + _make_modify_diff("src/unrelated/analytics.py", 5, 2)
        result = self.verifier.verify_intent(
            story_description="Fix the polling interval in `src/daemon.py`",
            acceptance_criteria=["Polling interval is configurable"],
            diff_text=diff,
            modified_files=["src/daemon.py", "src/unrelated/analytics.py"],
        )
        # The fix itself should be aligned
        assert result.aligned is True
        # But we should get a scope warning about the unrelated file
        assert len(result.scope_warnings) > 0
        assert any("analytics.py" in w for w in result.scope_warnings)

    def test_no_scope_warnings_when_all_referenced(self):
        """No scope warnings when all modified files are referenced in the story."""
        diff = _make_modify_diff("src/daemon.py", 3, 1)
        result = self.verifier.verify_intent(
            story_description="Fix the polling interval in `src/daemon.py`",
            acceptance_criteria=["Polling works correctly"],
            diff_text=diff,
            modified_files=["src/daemon.py"],
        )
        assert len(result.scope_warnings) == 0


class TestVerifyIntentEmptyDiff:
    def setup_method(self):
        self.verifier = IntentVerifier()

    def test_empty_diff_misaligned_create(self):
        """Empty diff -> misaligned for create stories."""
        result = self.verifier.verify_intent(
            story_description="Create a new module",
            acceptance_criteria=["Module exists"],
            diff_text="",
            modified_files=[],
        )
        assert result.aligned is False
        assert any("empty diff" in issue.lower() for issue in result.issues)

    def test_empty_diff_misaligned_fix(self):
        """Empty diff -> misaligned for fix stories."""
        result = self.verifier.verify_intent(
            story_description="Fix the broken login",
            acceptance_criteria=["Login works"],
            diff_text="",
            modified_files=[],
        )
        assert result.aligned is False

    def test_empty_diff_misaligned_delete(self):
        """Empty diff -> misaligned for delete stories."""
        result = self.verifier.verify_intent(
            story_description="Delete old config files",
            acceptance_criteria=["Files removed"],
            diff_text="   ",
            modified_files=[],
        )
        assert result.aligned is False

    def test_empty_diff_misaligned_expand(self):
        """Empty diff -> misaligned for expand stories."""
        result = self.verifier.verify_intent(
            story_description="Expand test coverage",
            acceptance_criteria=["More tests"],
            diff_text="",
            modified_files=[],
        )
        assert result.aligned is False

    def test_empty_diff_misaligned_update(self):
        """Empty diff -> misaligned for update stories."""
        result = self.verifier.verify_intent(
            story_description="Update the configuration",
            acceptance_criteria=["Config updated"],
            diff_text="",
            modified_files=[],
        )
        assert result.aligned is False


# --- Test check_scope_creep standalone ---


class TestCheckScopeCreep:
    def setup_method(self):
        self.verifier = IntentVerifier()

    def test_init_py_not_flagged(self):
        """__init__.py is always acceptable to modify."""
        warnings = self.verifier.check_scope_creep(
            story_description="Fix src/daemon.py",
            modified_files=["src/daemon.py", "src/__init__.py"],
            working_directory="/tmp/project",
        )
        assert not any("__init__.py" in w for w in warnings)

    def test_no_modified_files(self):
        """No warnings when no files were modified."""
        warnings = self.verifier.check_scope_creep(
            story_description="Fix something",
            modified_files=[],
            working_directory="/tmp/project",
        )
        assert warnings == []

    def test_directory_reference_covers_files(self):
        """Files in a referenced directory are not flagged."""
        warnings = self.verifier.check_scope_creep(
            story_description="Update files in src/execution/ directory",
            modified_files=["src/execution/git_manager.py", "src/execution/test_runner.py"],
            working_directory="/tmp/project",
        )
        assert len(warnings) == 0


# --- Test IntentVerificationResult dataclass ---


class TestIntentVerificationResult:
    def test_defaults(self):
        result = IntentVerificationResult(aligned=True, confidence=0.8)
        assert result.issues == []
        assert result.scope_warnings == []

    def test_with_issues(self):
        result = IntentVerificationResult(
            aligned=False,
            confidence=0.7,
            issues=["Missing file"],
            scope_warnings=["Extra file touched"],
        )
        assert len(result.issues) == 1
        assert len(result.scope_warnings) == 1
        assert not result.aligned
