"""
Intent Verifier — Checks whether git diff output matches a story's stated intent.

Pure Python heuristic checks (no LLM needed). Extracts action verbs from the
story description and verifies that the diff reflects the expected kind of change.

Integrated into the verification step in base_workflow.py.
"""

import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Action verb categories — mapped from story description keywords
ACTION_VERBS = {
    "create": {"create", "add", "introduce", "implement", "build", "scaffold", "generate", "write", "new"},
    "fix": {"fix", "repair", "patch", "resolve", "correct", "handle", "address", "debug"},
    "update": {"update", "modify", "change", "adjust", "enhance", "improve", "refactor", "revise", "configure"},
    "delete": {"delete", "remove", "drop", "clean", "prune", "strip", "eliminate"},
    "expand": {"expand", "extend", "grow", "augment", "enrich", "elaborate", "flesh out"},
}


@dataclass
class IntentVerificationResult:
    """Result of intent verification."""

    aligned: bool  # True if changes match intent
    confidence: float  # 0-1, how confident the check is
    issues: list[str] = field(default_factory=list)  # Specific misalignment details
    scope_warnings: list[str] = field(default_factory=list)  # Files modified outside stated scope


def _classify_intent(text: str) -> str:
    """Extract the primary action intent from story description text.

    Scans the first sentence and title-like patterns for action verbs.
    Returns one of: 'create', 'fix', 'update', 'delete', 'expand', or 'unknown'.
    """
    text_lower = text.lower()
    # Prioritize the first line / sentence — that's usually the imperative
    first_line = text_lower.split("\n")[0]
    first_sentence = re.split(r"[.!?]", first_line)[0]
    search_text = first_sentence if first_sentence.strip() else text_lower[:200]

    words = set(re.findall(r"\b[a-z]+\b", search_text))

    # Check each category, return first match
    # Order: expand before create because "extend" is more specific than "new"
    for intent in ("fix", "delete", "expand", "create", "update"):
        if words & ACTION_VERBS[intent]:
            return intent

    return "unknown"


def _parse_diff_stats(diff_text: str) -> dict:
    """Parse a unified diff to extract file-level statistics.

    Returns dict with keys:
      - new_files: list of files that appear as new (--- /dev/null)
      - deleted_files: list of files that were deleted (+++ /dev/null)
      - modified_files: list of files that were modified (neither new nor deleted)
      - additions: total added lines
      - deletions: total deleted lines
    """
    new_files: list[str] = []
    deleted_files: list[str] = []
    modified_files: list[str] = []
    additions = 0
    deletions = 0

    current_old = None
    current_new = None

    for line in diff_text.split("\n"):
        if line.startswith("--- "):
            path = line[4:].strip()
            # Strip a/ prefix from git diffs
            if path.startswith("a/"):
                path = path[2:]
            current_old = path
        elif line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_new = path

            # Classify the file
            if current_old == "/dev/null" and current_new and current_new != "/dev/null":
                new_files.append(current_new)
            elif current_new == "/dev/null" and current_old and current_old != "/dev/null":
                deleted_files.append(current_old)
            elif current_new and current_new != "/dev/null":
                modified_files.append(current_new)

            current_old = None
            current_new = None
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1

    return {
        "new_files": new_files,
        "deleted_files": deleted_files,
        "modified_files": modified_files,
        "additions": additions,
        "deletions": deletions,
    }


def _extract_referenced_files(text: str) -> set[str]:
    """Extract file paths or filenames mentioned in a story description or ACs.

    Looks for patterns like path/to/file.py, `filename.ext`, etc.
    """
    # Match file paths (with extensions) — handles both bare and backtick-quoted
    patterns = [
        r"`([^`]+\.\w{1,10})`",  # backtick-quoted: `src/foo.py`
        r"(?:^|\s)((?:[\w./-]+/)?[\w.-]+\.\w{1,10})(?:\s|$|[,;:])",  # bare paths
    ]
    files = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            candidate = match.group(1).strip()
            # Filter out common false positives
            if candidate and not candidate.startswith("http") and "..." not in candidate:
                files.add(candidate)
    return files


class IntentVerifier:
    """Verifies that code changes match the story's stated intent."""

    def verify_intent(
        self,
        story_description: str,
        acceptance_criteria: list[str],
        diff_text: str,
        modified_files: list[str],
    ) -> IntentVerificationResult:
        """Check if the diff aligns with the story's intent.

        Pure Python heuristic checks (no LLM needed):
        - For "create" stories: were new files created? Do filenames match expected outputs?
        - For "expand" stories: did file line counts increase?
        - For "fix" stories: were the specific files mentioned in the story modified?
        - For "delete" stories: were files removed?
        - Check that only expected files were modified (no unrelated changes)
        """
        issues: list[str] = []

        # Empty diff is always a misalignment (no changes were made)
        if not diff_text or not diff_text.strip():
            return IntentVerificationResult(
                aligned=False,
                confidence=0.9,
                issues=["Empty diff — no changes were made but the story requires action"],
            )

        intent = _classify_intent(story_description)
        diff_stats = _parse_diff_stats(diff_text)

        # Combine all AC text for reference extraction
        full_text = story_description + "\n" + "\n".join(acceptance_criteria)
        referenced_files = _extract_referenced_files(full_text)

        if intent == "create":
            issues.extend(self._check_create(diff_stats, referenced_files, modified_files))
        elif intent == "fix":
            issues.extend(self._check_fix(diff_stats, referenced_files, modified_files))
        elif intent == "update":
            issues.extend(self._check_update(diff_stats, referenced_files, modified_files))
        elif intent == "delete":
            issues.extend(self._check_delete(diff_stats))
        elif intent == "expand":
            issues.extend(self._check_expand(diff_stats))
        # "unknown" intent — we can still check scope but not specific alignment

        # Scope warnings (separate from alignment issues)
        scope_warnings = self.check_scope_creep(
            story_description,
            modified_files,
            working_directory="",  # Not needed for basic scope check
        )

        # Determine confidence based on intent clarity
        confidence = 0.8 if intent != "unknown" else 0.4

        return IntentVerificationResult(
            aligned=len(issues) == 0,
            confidence=confidence,
            issues=issues,
            scope_warnings=scope_warnings,
        )

    def _check_create(
        self,
        diff_stats: dict,
        referenced_files: set[str],
        modified_files: list[str],
    ) -> list[str]:
        """Verify a 'create' intent: new files should exist in the diff."""
        issues = []
        if not diff_stats["new_files"]:
            issues.append("Create story but no new files were added in the diff. Expected at least one new file.")
        return issues

    def _check_fix(
        self,
        diff_stats: dict,
        referenced_files: set[str],
        modified_files: list[str],
    ) -> list[str]:
        """Verify a 'fix' intent: referenced files should be modified."""
        issues = []
        if not modified_files:
            issues.append("Fix story but no files were modified.")
            return issues

        # If specific files are referenced, check they were touched
        if referenced_files:
            all_changed = set(modified_files) | set(diff_stats["new_files"])
            # Check by basename match (story may reference relative paths differently)
            changed_basenames = {os.path.basename(f) for f in all_changed}
            for ref_file in referenced_files:
                ref_basename = os.path.basename(ref_file)
                if ref_basename not in changed_basenames and ref_file not in all_changed:
                    # Only flag if the referenced file looks like a real target
                    # (not a generic mention like "README.md" in description)
                    if "/" in ref_file or ref_file.endswith(".py"):
                        issues.append(f"Fix story references '{ref_file}' but it was not modified.")
        return issues

    def _check_update(
        self,
        diff_stats: dict,
        referenced_files: set[str],
        modified_files: list[str],
    ) -> list[str]:
        """Verify an 'update' intent: files should be modified (not just created)."""
        issues = []
        if not modified_files and not diff_stats["modified_files"]:
            issues.append("Update story but no existing files were modified.")
        return issues

    def _check_delete(self, diff_stats: dict) -> list[str]:
        """Verify a 'delete' intent: files should be removed or lines deleted."""
        issues = []
        if not diff_stats["deleted_files"] and diff_stats["deletions"] == 0:
            issues.append("Delete/remove story but no files were deleted and no lines were removed.")
        return issues

    def _check_expand(self, diff_stats: dict) -> list[str]:
        """Verify an 'expand' intent: additions should exceed deletions."""
        issues = []
        if diff_stats["additions"] <= diff_stats["deletions"]:
            issues.append(
                f"Expand story but file did not grow: "
                f"+{diff_stats['additions']}/-{diff_stats['deletions']} lines. "
                f"Expected more additions than deletions."
            )
        return issues

    def check_scope_creep(
        self,
        story_description: str,
        modified_files: list[str],
        working_directory: str,
    ) -> list[str]:
        """Flag files that were modified but aren't mentioned in the story.

        Returns a list of warning strings for files that look out-of-scope.
        """
        if not modified_files:
            return []

        # Extract referenced files from story description
        referenced = _extract_referenced_files(story_description)

        # Build a set of "expected" basenames and directory prefixes
        expected_basenames = {os.path.basename(f) for f in referenced}
        expected_dirs = set()
        for f in referenced:
            dirname = os.path.dirname(f)
            # Require at least 2 path segments to avoid overly broad matches
            # (e.g., "src" alone would match everything under src/)
            if dirname and "/" in dirname:
                expected_dirs.add(dirname)

        # Also extract directory-level references from description
        dir_patterns = re.findall(r"(?:^|\s)([\w./-]+/)(?:\s|$)", story_description)
        for d in dir_patterns:
            expected_dirs.add(d.rstrip("/"))

        warnings = []
        for filepath in modified_files:
            basename = os.path.basename(filepath)
            filedir = os.path.dirname(filepath)

            # Skip if file or its basename is explicitly referenced
            if filepath in referenced or basename in expected_basenames:
                continue

            # Skip if the file is in a referenced directory
            if any(filedir.startswith(d) or d.startswith(filedir) for d in expected_dirs if d):
                continue

            # Skip common files that are always acceptable to modify
            if basename in (
                "__init__.py",
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "requirements.txt",
                ".gitignore",
                "conftest.py",
            ):
                continue

            warnings.append(f"File '{filepath}' was modified but is not referenced in the story description.")

        return warnings
