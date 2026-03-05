"""
Tests for DebugRollback — Phase 2.3 debug rollback manager.

All git operations are mocked so no real repository is needed.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.execution.debug_rollback import DebugRollback, DebugRollbackError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


OK = _make_completed_process(returncode=0, stdout="")
FAIL = _make_completed_process(returncode=1, stderr="error")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rollback(tmp_path):
    """Return a DebugRollback pointed at tmp_path."""
    return DebugRollback(str(tmp_path))


# ---------------------------------------------------------------------------
# has_uncommitted_changes
# ---------------------------------------------------------------------------

class TestHasUncommittedChanges:
    @patch("src.execution.debug_rollback._run_git")
    def test_clean_working_tree(self, mock_git, rollback):
        mock_git.return_value = _make_completed_process(stdout="")
        assert rollback.has_uncommitted_changes() is False
        mock_git.assert_called_once_with(
            ["status", "--porcelain"], rollback.working_directory
        )

    @patch("src.execution.debug_rollback._run_git")
    def test_dirty_working_tree(self, mock_git, rollback):
        mock_git.return_value = _make_completed_process(stdout=" M foo.py\n")
        assert rollback.has_uncommitted_changes() is True

    @patch("src.execution.debug_rollback._run_git")
    def test_git_status_error_is_conservative(self, mock_git, rollback):
        """If git status itself fails, treat as dirty (safe default)."""
        mock_git.return_value = FAIL
        assert rollback.has_uncommitted_changes() is True


# ---------------------------------------------------------------------------
# stash / pop
# ---------------------------------------------------------------------------

class TestStash:
    @patch("src.execution.debug_rollback._run_git")
    def test_stash_when_dirty(self, mock_git, rollback):
        # First call: status --porcelain => dirty
        # Second call: stash push => ok
        mock_git.side_effect = [
            _make_completed_process(stdout=" M foo.py\n"),
            _make_completed_process(),
        ]
        assert rollback.stash_changes() is True
        assert mock_git.call_count == 2
        mock_git.assert_any_call(
            ["stash", "push", "-m", "debug-rollback: pre-debug stash"],
            rollback.working_directory,
        )

    @patch("src.execution.debug_rollback._run_git")
    def test_stash_when_clean(self, mock_git, rollback):
        mock_git.return_value = _make_completed_process(stdout="")
        assert rollback.stash_changes() is True
        # Only status check, no stash push
        mock_git.assert_called_once()

    @patch("src.execution.debug_rollback._run_git")
    def test_stash_failure(self, mock_git, rollback):
        mock_git.side_effect = [
            _make_completed_process(stdout=" M foo.py\n"),
            FAIL,
        ]
        assert rollback.stash_changes() is False

    @patch("src.execution.debug_rollback._run_git")
    def test_pop_success(self, mock_git, rollback):
        mock_git.return_value = _make_completed_process()
        assert rollback.pop_stash() is True
        mock_git.assert_called_once_with(
            ["stash", "pop"], rollback.working_directory
        )

    @patch("src.execution.debug_rollback._run_git")
    def test_pop_failure_conflict(self, mock_git, rollback):
        mock_git.return_value = _make_completed_process(
            returncode=1, stderr="CONFLICT"
        )
        assert rollback.pop_stash() is False


# ---------------------------------------------------------------------------
# Tag creation — pre-fix
# ---------------------------------------------------------------------------

class TestCreatePreFixTag:
    @patch("src.execution.debug_rollback.get_current_commit", return_value="abc123")
    @patch("src.execution.debug_rollback._run_git")
    def test_creates_tag_on_clean_tree(self, mock_git, _mock_commit, rollback):
        # status --porcelain => clean
        # rev-parse --verify (tag exists check) => not found
        # tag -a => ok
        mock_git.side_effect = [
            _make_completed_process(stdout=""),   # status
            FAIL,                                  # tag does not exist
            _make_completed_process(),             # tag -a
        ]
        tag = rollback.create_pre_fix_tag("SAT-1", 1)
        assert tag == "debug-SAT-1-attempt-1-pre"

    @patch("src.execution.debug_rollback._run_git")
    def test_raises_on_dirty_tree(self, mock_git, rollback):
        mock_git.return_value = _make_completed_process(stdout=" M bar.py\n")
        with pytest.raises(DebugRollbackError, match="Uncommitted changes"):
            rollback.create_pre_fix_tag("SAT-1", 1)

    @patch("src.execution.debug_rollback.get_current_commit", return_value="abc123")
    @patch("src.execution.debug_rollback._run_git")
    def test_overwrites_existing_tag(self, mock_git, _mock_commit, rollback):
        # status => clean, tag exists => yes, delete => ok, create => ok
        mock_git.side_effect = [
            _make_completed_process(stdout=""),   # status (clean)
            _make_completed_process(),             # tag exists
            _make_completed_process(),             # tag -d
            _make_completed_process(),             # tag -a
        ]
        tag = rollback.create_pre_fix_tag("SAT-1", 2)
        assert tag == "debug-SAT-1-attempt-2-pre"
        # Verify delete was called
        mock_git.assert_any_call(
            ["tag", "-d", "debug-SAT-1-attempt-2-pre"],
            rollback.working_directory,
        )

    @patch("src.execution.debug_rollback.get_current_commit", return_value="abc123")
    @patch("src.execution.debug_rollback._run_git")
    def test_raises_on_tag_creation_failure(self, mock_git, _mock_commit, rollback):
        mock_git.side_effect = [
            _make_completed_process(stdout=""),   # status clean
            FAIL,                                  # tag does not exist
            _make_completed_process(returncode=1, stderr="tag error"),  # tag -a fails
        ]
        with pytest.raises(DebugRollbackError, match="Failed to create tag"):
            rollback.create_pre_fix_tag("SAT-1", 1)


# ---------------------------------------------------------------------------
# Tag creation — post-fix
# ---------------------------------------------------------------------------

class TestCreatePostFixTag:
    @patch("src.execution.debug_rollback.get_current_commit", return_value="def456")
    @patch("src.execution.debug_rollback._run_git")
    def test_creates_post_tag(self, mock_git, _mock_commit, rollback):
        mock_git.side_effect = [
            FAIL,                      # tag does not exist
            _make_completed_process(),  # tag -a
        ]
        tag = rollback.create_post_fix_tag("SAT-1", 3)
        assert tag == "debug-SAT-1-attempt-3-post"


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

class TestRollback:
    @patch("src.execution.debug_rollback.reset_to_commit", return_value=True)
    @patch("src.execution.debug_rollback._run_git")
    def test_rollback_success(self, mock_git, mock_reset, rollback):
        tag = "debug-SAT-1-attempt-1-pre"
        # tag exists check => yes
        # rev-list => commit hash
        mock_git.side_effect = [
            _make_completed_process(),                  # tag exists
            _make_completed_process(stdout="abc123\n"),  # rev-list
        ]
        assert rollback.rollback(tag) is True
        mock_reset.assert_called_once_with(rollback.working_directory, "abc123")

    @patch("src.execution.debug_rollback._run_git")
    def test_rollback_tag_does_not_exist(self, mock_git, rollback):
        mock_git.return_value = FAIL  # tag does not exist
        assert rollback.rollback("debug-SAT-1-attempt-99-pre") is False

    @patch("src.execution.debug_rollback.reset_to_commit", return_value=False)
    @patch("src.execution.debug_rollback._run_git")
    def test_rollback_reset_fails(self, mock_git, mock_reset, rollback):
        mock_git.side_effect = [
            _make_completed_process(),                  # tag exists
            _make_completed_process(stdout="abc123\n"),  # rev-list
        ]
        assert rollback.rollback("debug-SAT-1-attempt-1-pre") is False

    @patch("src.execution.debug_rollback._run_git")
    def test_rollback_revlist_fails(self, mock_git, rollback):
        mock_git.side_effect = [
            _make_completed_process(),  # tag exists
            FAIL,                       # rev-list fails
        ]
        assert rollback.rollback("debug-SAT-1-attempt-1-pre") is False


# ---------------------------------------------------------------------------
# attempt_fix — full lifecycle
# ---------------------------------------------------------------------------

class TestAttemptFix:
    @patch("src.execution.debug_rollback.auto_commit", return_value="commit123")
    @patch("src.execution.debug_rollback.get_current_commit", return_value="abc123")
    @patch("src.execution.debug_rollback.reset_to_commit", return_value=True)
    @patch("src.execution.debug_rollback._run_git")
    def test_successful_fix(self, mock_git, mock_reset, _mock_commit, mock_auto):
        rb = DebugRollback("/fake/path")
        apply_fn = MagicMock()
        validate_fn = MagicMock(return_value=True)

        # Calls in order:
        # 1. has_uncommitted_changes (status) => clean
        # 2. has_uncommitted_changes again in create_pre_fix_tag => clean
        # 3. tag exists check => no
        # 4. tag -a (pre) => ok
        # 5. tag exists check (post) => no
        # 6. tag -a (post) => ok
        mock_git.side_effect = [
            _make_completed_process(stdout=""),   # status (attempt_fix check)
            _make_completed_process(stdout=""),   # status (create_pre_fix_tag)
            FAIL,                                  # pre tag doesn't exist
            _make_completed_process(),             # create pre tag
            FAIL,                                  # post tag doesn't exist
            _make_completed_process(),             # create post tag
        ]

        result = rb.attempt_fix("SAT-1", 1, apply_fn, validate_fn)

        assert result is True
        apply_fn.assert_called_once()
        validate_fn.assert_called_once()

    @patch("src.execution.debug_rollback.auto_commit", return_value="commit123")
    @patch("src.execution.debug_rollback.get_current_commit", return_value="abc123")
    @patch("src.execution.debug_rollback.reset_to_commit", return_value=True)
    @patch("src.execution.debug_rollback._run_git")
    def test_failed_fix_rolls_back(self, mock_git, mock_reset, _mock_commit, mock_auto):
        rb = DebugRollback("/fake/path")
        apply_fn = MagicMock()
        validate_fn = MagicMock(return_value=False)

        mock_git.side_effect = [
            _make_completed_process(stdout=""),    # status (attempt_fix)
            _make_completed_process(stdout=""),    # status (create_pre_fix_tag)
            FAIL,                                   # pre tag doesn't exist
            _make_completed_process(),              # create pre tag
            # rollback sequence:
            _make_completed_process(),              # tag exists check
            _make_completed_process(stdout="abc123\n"),  # rev-list
        ]

        result = rb.attempt_fix("SAT-1", 1, apply_fn, validate_fn)

        assert result is False
        mock_reset.assert_called_once_with("/fake/path", "abc123")

    @patch("src.execution.debug_rollback.get_current_commit", return_value="abc123")
    @patch("src.execution.debug_rollback.reset_to_commit", return_value=True)
    @patch("src.execution.debug_rollback._run_git")
    def test_apply_fn_raises_rolls_back(self, mock_git, mock_reset, _mock_commit):
        rb = DebugRollback("/fake/path")
        apply_fn = MagicMock(side_effect=RuntimeError("boom"))
        validate_fn = MagicMock()

        mock_git.side_effect = [
            _make_completed_process(stdout=""),    # status (attempt_fix)
            _make_completed_process(stdout=""),    # status (create_pre_fix_tag)
            FAIL,                                   # pre tag doesn't exist
            _make_completed_process(),              # create pre tag
            # rollback sequence:
            _make_completed_process(),              # tag exists
            _make_completed_process(stdout="abc123\n"),  # rev-list
        ]

        result = rb.attempt_fix("SAT-1", 1, apply_fn, validate_fn)

        assert result is False
        validate_fn.assert_not_called()
        mock_reset.assert_called_once()

    @patch("src.execution.debug_rollback._run_git")
    def test_attempt_stashes_dirty_tree(self, mock_git):
        rb = DebugRollback("/fake/path")

        # First has_uncommitted => dirty, stash => ok,
        # then create_pre_fix_tag calls has_uncommitted => clean, ...
        mock_git.side_effect = [
            _make_completed_process(stdout=" M x.py\n"),  # status dirty
            _make_completed_process(stdout=" M x.py\n"),  # status dirty (stash_changes check)
            _make_completed_process(),                      # stash push ok
            # But then create_pre_fix_tag will also check uncommitted
            # After stash, tree is clean
            _make_completed_process(stdout=""),             # status clean
            FAIL,                                           # pre tag doesn't exist
            _make_completed_process(),                      # create pre tag
        ]

        # Patch the rest to avoid more mock gymnastics
        with (
            patch("src.execution.debug_rollback.get_current_commit", return_value="aaa"),
            patch("src.execution.debug_rollback.auto_commit", return_value="bbb"),
        ):
            apply_fn = MagicMock()
            validate_fn = MagicMock(return_value=True)

            # Need post-fix tag calls too
            mock_git.side_effect = list(mock_git.side_effect) + [
                FAIL,                      # post tag doesn't exist
                _make_completed_process(),  # create post tag
            ]

            # Rebuild side_effect fresh
            mock_git.side_effect = [
                _make_completed_process(stdout=" M x.py\n"),  # status dirty
                _make_completed_process(stdout=" M x.py\n"),  # stash check
                _make_completed_process(),                      # stash push
                _make_completed_process(stdout=""),             # create_pre status
                FAIL,                                           # pre tag no exist
                _make_completed_process(),                      # tag -a pre
                FAIL,                                           # post tag no exist
                _make_completed_process(),                      # tag -a post
            ]

            result = rb.attempt_fix("SAT-1", 1, apply_fn, validate_fn)
            assert result is True


# ---------------------------------------------------------------------------
# Tag name generation
# ---------------------------------------------------------------------------

class TestTagName:
    def test_pre_tag_format(self):
        assert DebugRollback._tag_name("SAT-42", 3, "pre") == "debug-SAT-42-attempt-3-pre"

    def test_post_tag_format(self):
        assert DebugRollback._tag_name("SAT-42", 3, "post") == "debug-SAT-42-attempt-3-post"
