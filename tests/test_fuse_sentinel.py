"""Unit tests for FuseSentinel (no FUSE mount required)."""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from src.execution.fuse_sentinel import FuseSentinel


class TestFuseSentinelUnit:
    """Test FuseSentinel with mock/temp files."""

    def test_healthy_with_real_file(self, tmp_path):
        """Sentinel should report healthy for a real file with content."""
        sentinel_file = tmp_path / "sentinel.md"
        sentinel_file.write_text("# Test sentinel content\n")
        sentinel = FuseSentinel(sentinel_path=str(sentinel_file))
        assert sentinel.is_healthy() is True
        assert sentinel.consecutive_failures == 0

    def test_unhealthy_missing_file(self):
        """Sentinel should report unhealthy for missing file."""
        sentinel = FuseSentinel(sentinel_path="/nonexistent/path.md")
        assert sentinel.is_healthy() is False
        assert sentinel.consecutive_failures == 1

    def test_unhealthy_empty_file(self, tmp_path):
        """Sentinel should report unhealthy for empty file."""
        sentinel_file = tmp_path / "empty.md"
        sentinel_file.write_text("")
        sentinel = FuseSentinel(sentinel_path=str(sentinel_file))
        assert sentinel.is_healthy() is False

    def test_consecutive_failures_increment(self):
        """Failures should count up."""
        sentinel = FuseSentinel(sentinel_path="/nonexistent/path.md")
        for i in range(5):
            sentinel.is_healthy()
        assert sentinel.consecutive_failures == 5

    def test_recovery_resets_counter(self, tmp_path):
        """Recovery should reset the failure counter."""
        sentinel_file = tmp_path / "sentinel.md"
        sentinel_file.write_text("content\n")
        sentinel = FuseSentinel(sentinel_path=str(sentinel_file))
        # Simulate failures
        sentinel._consecutive_failures = 10
        # Now check with real file
        assert sentinel.is_healthy() is True
        assert sentinel.consecutive_failures == 0

    def test_seconds_since_healthy_initial(self):
        """Before any check, seconds_since_healthy should be infinity."""
        sentinel = FuseSentinel(sentinel_path="/nonexistent/path.md")
        assert sentinel.seconds_since_healthy == float("inf")

    def test_seconds_since_healthy_after_check(self, tmp_path):
        """After a successful check, should be near zero."""
        sentinel_file = tmp_path / "sentinel.md"
        sentinel_file.write_text("content\n")
        sentinel = FuseSentinel(sentinel_path=str(sentinel_file))
        sentinel.is_healthy()
        assert sentinel.seconds_since_healthy < 2.0

    def test_os_error_handled(self, tmp_path):
        """OSError during read should be handled gracefully."""
        sentinel = FuseSentinel(sentinel_path=str(tmp_path / "sentinel.md"))
        # File doesn't exist — should handle gracefully
        assert sentinel.is_healthy() is False

    def test_wait_for_healthy_immediate(self, tmp_path):
        """wait_for_healthy should return immediately if already healthy."""
        sentinel_file = tmp_path / "sentinel.md"
        sentinel_file.write_text("content\n")
        sentinel = FuseSentinel(sentinel_path=str(sentinel_file))
        assert sentinel.wait_for_healthy(timeout=1.0) is True

    def test_wait_for_healthy_timeout(self):
        """wait_for_healthy should return False on timeout."""
        sentinel = FuseSentinel(sentinel_path="/nonexistent/path.md")
        assert sentinel.wait_for_healthy(timeout=0.5, interval=0.1) is False


class TestRcloneRCHealth:
    """Test rclone RC API health check integration."""

    def test_rc_healthy_response(self, tmp_path):
        """RC returning healthy stats should pass."""
        sentinel_file = tmp_path / "sentinel.md"
        sentinel_file.write_text("content\n")
        sentinel = FuseSentinel(sentinel_path=str(sentinel_file))

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"fatalErrors": 0, "errors": 0, "bytes": 1024}
        ).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert sentinel.is_healthy() is True
            assert sentinel._rc_available is True

    def test_rc_fatal_errors_unhealthy(self, tmp_path):
        """RC reporting fatal errors should fail."""
        sentinel_file = tmp_path / "sentinel.md"
        sentinel_file.write_text("content\n")
        sentinel = FuseSentinel(sentinel_path=str(sentinel_file))

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"fatalErrors": 3, "errors": 1}
        ).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert sentinel.is_healthy() is False
            assert sentinel.consecutive_failures == 1

    def test_rc_unavailable_still_healthy(self, tmp_path):
        """If RC endpoint is not available, sentinel file check alone is sufficient."""
        sentinel_file = tmp_path / "sentinel.md"
        sentinel_file.write_text("content\n")
        sentinel = FuseSentinel(sentinel_path=str(sentinel_file))

        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            assert sentinel.is_healthy() is True
            assert sentinel._rc_available is False

    def test_rc_check_returns_none_when_unavailable(self, tmp_path):
        """_check_rclone_rc should return None when RC is not running."""
        sentinel_file = tmp_path / "sentinel.md"
        sentinel_file.write_text("content\n")
        sentinel = FuseSentinel(sentinel_path=str(sentinel_file))

        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            result = sentinel._check_rclone_rc()
            assert result is None


class TestTaskStateHubUnit:
    """Test DatabaseManager task state hub methods."""

    @pytest.fixture
    def db(self, tmp_path):
        from src.db.database_manager import DatabaseManager
        return DatabaseManager(str(tmp_path / "test.db"))

    def test_upsert_and_get(self, db):
        """Basic upsert and retrieval."""
        db.upsert_task_state("/path/to/task.md", "pending", signal="pending")
        state = db.get_task_state("/path/to/task.md")
        assert state is not None
        assert state["status"] == "pending"
        assert state["signal"] == "pending"

    def test_transition_valid(self, db):
        """Valid transition should succeed."""
        db.upsert_task_state("/path/to/task.md", "pending")
        assert db.transition_task_state("/path/to/task.md", "working") is True
        state = db.get_task_state("/path/to/task.md")
        assert state["status"] == "working"

    def test_transition_invalid(self, db):
        """Invalid transition should fail."""
        db.upsert_task_state("/path/to/task.md", "pending")
        assert db.transition_task_state("/path/to/task.md", "finished") is False
        state = db.get_task_state("/path/to/task.md")
        assert state["status"] == "pending"  # Unchanged

    def test_transition_pending_to_working_to_finished(self, db):
        """Full happy path transition."""
        db.upsert_task_state("/path/to/task.md", "pending")
        assert db.transition_task_state("/path/to/task.md", "working") is True
        assert db.transition_task_state("/path/to/task.md", "finished") is True
        state = db.get_task_state("/path/to/task.md")
        assert state["status"] == "finished"

    def test_transition_working_to_failed(self, db):
        """Failure transition."""
        db.upsert_task_state("/path/to/task.md", "pending")
        db.transition_task_state("/path/to/task.md", "working")
        assert db.transition_task_state(
            "/path/to/task.md", "failed", error_summary="test error"
        ) is True
        state = db.get_task_state("/path/to/task.md")
        assert state["status"] == "failed"
        assert state["error_summary"] == "test error"

    def test_increment_retry(self, db):
        """Retry count should increment."""
        db.upsert_task_state("/path/to/task.md", "failed")
        count = db.increment_task_retry("/path/to/task.md")
        assert count == 1
        count = db.increment_task_retry("/path/to/task.md")
        assert count == 2

    def test_get_tasks_by_state(self, db):
        """Filter tasks by status."""
        db.upsert_task_state("/a.md", "pending")
        db.upsert_task_state("/b.md", "working")
        db.upsert_task_state("/c.md", "pending")
        pending = db.get_tasks_by_state("pending")
        assert len(pending) == 2

    def test_get_failed_under_max_retries(self, db):
        """Should only return tasks under max retry count."""
        db.upsert_task_state("/a.md", "failed")
        db.upsert_task_state("/b.md", "failed")
        # Bump /b.md to 15 retries
        for _ in range(15):
            db.increment_task_retry("/b.md")
        failed = db.get_failed_task_states(max_retries=10)
        assert len(failed) == 1
        assert failed[0]["task_path"] == "/a.md"

    def test_clear_task_state(self, db):
        """Clear should remove the task."""
        db.upsert_task_state("/a.md", "finished")
        db.clear_task_state("/a.md")
        assert db.get_task_state("/a.md") is None

    def test_upsert_preserves_existing_error(self, db):
        """Upsert with None error_summary should preserve existing."""
        db.upsert_task_state("/a.md", "failed", error_summary="original error")
        db.upsert_task_state("/a.md", "pending")  # No error_summary
        state = db.get_task_state("/a.md")
        assert state["error_summary"] == "original error"
