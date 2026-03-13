"""Tests for src.execution.snapshot_manager."""

from unittest.mock import MagicMock, patch

from src.execution.snapshot_manager import capture_snapshot, rollback_to_snapshot


class TestCaptureSnapshot:
    @patch("src.execution.snapshot_manager.subprocess.run")
    def test_returns_commit_hash(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git commit
            MagicMock(returncode=0, stdout="abc123def456\n"),  # git rev-parse  pragma: allowlist secret
        ]
        result = capture_snapshot("/project")
        assert result == "abc123def456"  # pragma: allowlist secret
        assert mock_run.call_count == 3

    @patch("src.execution.snapshot_manager.subprocess.run")
    def test_returns_none_on_rev_parse_failure(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git commit
            MagicMock(returncode=1, stderr="error"),  # git rev-parse fails
        ]
        result = capture_snapshot("/project")
        assert result is None

    @patch("src.execution.snapshot_manager.subprocess.run")
    def test_returns_none_on_exception(self, mock_run):
        mock_run.side_effect = Exception("git not found")
        result = capture_snapshot("/project")
        assert result is None


class TestRollbackToSnapshot:
    @patch("src.execution.snapshot_manager.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert rollback_to_snapshot("/project", "abc123") is True

    @patch("src.execution.snapshot_manager.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        assert rollback_to_snapshot("/project", "abc123") is False

    def test_no_hash_returns_false(self):
        assert rollback_to_snapshot("/project", "") is False
        assert rollback_to_snapshot("/project", None) is False

    @patch("src.execution.snapshot_manager.subprocess.run")
    def test_exception_returns_false(self, mock_run):
        mock_run.side_effect = Exception("timeout")
        assert rollback_to_snapshot("/project", "abc123") is False
