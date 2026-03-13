"""Tests for StabilityTimeout fallback module."""

import os
from unittest.mock import patch

import pytest

from src.execution.stability_timeout import StabilityTimeout

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_file(path, content: str) -> None:
    """Write content to a file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _touch(path, mtime: float) -> None:
    """Set a file's mtime (and atime) to a specific timestamp."""
    os.utime(path, (mtime, mtime))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStabilityTimeout:
    """Core behaviour of StabilityTimeout."""

    def test_pending_marker_triggers_after_timeout(self, tmp_path):
        """File with '# <Pending>' should trigger after timeout elapses."""
        task_file = tmp_path / "task.md"
        _write_file(task_file, "# Response\nSome content\n# <Pending>\n")

        st = StabilityTimeout(timeout_seconds=300)
        file_path = str(task_file)

        base_time = 1000000.0
        # Set file mtime to a known value
        _touch(file_path, base_time)

        with patch("time.time") as mock_time, patch("os.path.getmtime") as mock_getmtime:
            mock_getmtime.return_value = base_time

            # First check — starts tracking
            mock_time.return_value = base_time
            assert st.check_file(file_path) is False
            assert st.is_tracking(file_path)

            # 299 seconds later — not yet
            mock_time.return_value = base_time + 299
            assert st.check_file(file_path) is False

            # 300 seconds later — triggers
            mock_time.return_value = base_time + 300
            assert st.check_file(file_path) is True

    def test_no_marker_not_tracked(self, tmp_path):
        """File without '# <Pending>' should never be tracked."""
        task_file = tmp_path / "task.md"
        _write_file(task_file, "# Response\nSome content\n<Pending>\n")

        st = StabilityTimeout(timeout_seconds=10)
        file_path = str(task_file)

        with patch("time.time", return_value=1000000.0):
            assert st.check_file(file_path) is False
            assert not st.is_tracking(file_path)

    def test_working_marker_not_tracked(self, tmp_path):
        """File with '<Working>' should never be tracked, even if '# <Pending>' is also present."""
        task_file = tmp_path / "task.md"
        _write_file(task_file, "# Response\n<Working>\n# <Pending>\n")

        st = StabilityTimeout(timeout_seconds=10)
        file_path = str(task_file)

        with patch("time.time", return_value=1000000.0):
            assert st.check_file(file_path) is False
            assert not st.is_tracking(file_path)

    def test_working_marker_removes_existing_tracking(self, tmp_path):
        """If a tracked file gains '<Working>', tracking should stop."""
        task_file = tmp_path / "task.md"
        file_path = str(task_file)
        _write_file(task_file, "# Response\n# <Pending>\n")

        st = StabilityTimeout(timeout_seconds=300)
        base_time = 1000000.0

        with patch("time.time", return_value=base_time), patch("os.path.getmtime", return_value=base_time):
            st.check_file(file_path)
            assert st.is_tracking(file_path)

        # Now add <Working> marker
        _write_file(task_file, "# Response\n<Working>\n# <Pending>\n")

        with patch("time.time", return_value=base_time + 100):
            st.check_file(file_path)
            assert not st.is_tracking(file_path)

    def test_timer_resets_on_modification(self, tmp_path):
        """Timer resets when file mtime changes (user is editing)."""
        task_file = tmp_path / "task.md"
        file_path = str(task_file)
        _write_file(task_file, "# <Pending>\n")

        st = StabilityTimeout(timeout_seconds=300)
        base_time = 1000000.0

        with patch("time.time") as mock_time, patch("os.path.getmtime") as mock_getmtime:
            # Start tracking
            mock_getmtime.return_value = base_time
            mock_time.return_value = base_time
            st.check_file(file_path)
            assert st.is_tracking(file_path)

            # 200 seconds later, file is modified
            mock_getmtime.return_value = base_time + 200
            mock_time.return_value = base_time + 200
            assert st.check_file(file_path) is False

            # 299 seconds after the modification — should NOT trigger
            # (only 99 seconds since reset)
            mock_time.return_value = base_time + 499
            assert st.check_file(file_path) is False

            # 300 seconds after modification — now triggers
            mock_time.return_value = base_time + 500
            assert st.check_file(file_path) is True

    def test_reset_clears_tracking(self, tmp_path):
        """reset() should remove a file from tracking."""
        task_file = tmp_path / "task.md"
        file_path = str(task_file)
        _write_file(task_file, "# <Pending>\n")

        st = StabilityTimeout(timeout_seconds=300)
        base_time = 1000000.0

        with patch("time.time", return_value=base_time), patch("os.path.getmtime", return_value=base_time):
            st.check_file(file_path)
            assert st.is_tracking(file_path)

        st.reset(file_path)
        assert not st.is_tracking(file_path)

    def test_reset_noop_for_untracked(self):
        """reset() on an untracked file should not error."""
        st = StabilityTimeout()
        st.reset("/nonexistent/file.md")  # Should not raise

    def test_configurable_timeout(self, tmp_path):
        """Timeout duration should be configurable."""
        task_file = tmp_path / "task.md"
        file_path = str(task_file)
        _write_file(task_file, "# <Pending>\n")

        st = StabilityTimeout(timeout_seconds=60)
        base_time = 1000000.0

        with patch("time.time") as mock_time, patch("os.path.getmtime") as mock_getmtime:
            mock_getmtime.return_value = base_time

            mock_time.return_value = base_time
            st.check_file(file_path)

            # 59 seconds — not yet
            mock_time.return_value = base_time + 59
            assert st.check_file(file_path) is False

            # 60 seconds — triggers
            mock_time.return_value = base_time + 60
            assert st.check_file(file_path) is True

    def test_get_tracked_files_returns_remaining_time(self, tmp_path):
        """get_tracked_files() should return remaining seconds for each file."""
        task_a = tmp_path / "a.md"
        task_b = tmp_path / "b.md"
        _write_file(task_a, "# <Pending>\n")
        _write_file(task_b, "# <Pending>\n")
        path_a = str(task_a)
        path_b = str(task_b)

        st = StabilityTimeout(timeout_seconds=300)
        base_time = 1000000.0

        with patch("time.time") as mock_time, patch("os.path.getmtime") as mock_getmtime:
            mock_getmtime.return_value = base_time

            # Start tracking both at base_time
            mock_time.return_value = base_time
            st.check_file(path_a)
            st.check_file(path_b)

            # Check remaining at base_time + 100
            mock_time.return_value = base_time + 100
            tracked = st.get_tracked_files()
            assert path_a in tracked
            assert path_b in tracked
            assert tracked[path_a] == pytest.approx(200.0)
            assert tracked[path_b] == pytest.approx(200.0)

    def test_get_tracked_files_negative_when_expired(self, tmp_path):
        """get_tracked_files() returns negative values for expired files."""
        task_file = tmp_path / "task.md"
        file_path = str(task_file)
        _write_file(task_file, "# <Pending>\n")

        st = StabilityTimeout(timeout_seconds=300)
        base_time = 1000000.0

        with patch("time.time") as mock_time, patch("os.path.getmtime") as mock_getmtime:
            mock_getmtime.return_value = base_time
            mock_time.return_value = base_time
            st.check_file(file_path)

            mock_time.return_value = base_time + 350
            tracked = st.get_tracked_files()
            assert tracked[file_path] == pytest.approx(-50.0)

    def test_nonexistent_file_not_tracked(self):
        """A file that doesn't exist should not be tracked."""
        st = StabilityTimeout(timeout_seconds=10)
        assert st.check_file("/does/not/exist.md") is False
        assert not st.is_tracking("/does/not/exist.md")

    def test_marker_removed_stops_tracking(self, tmp_path):
        """If '# <Pending>' is removed from a tracked file, tracking stops."""
        task_file = tmp_path / "task.md"
        file_path = str(task_file)
        _write_file(task_file, "# <Pending>\n")

        st = StabilityTimeout(timeout_seconds=300)
        base_time = 1000000.0

        with patch("time.time", return_value=base_time), patch("os.path.getmtime", return_value=base_time):
            st.check_file(file_path)
            assert st.is_tracking(file_path)

        # User removes the marker (changes to <Pending> without #)
        _write_file(task_file, "<Pending>\n")

        with patch("time.time", return_value=base_time + 100):
            assert st.check_file(file_path) is False
            assert not st.is_tracking(file_path)

    def test_default_timeout_is_300(self):
        """Default timeout should be 300 seconds (5 minutes)."""
        st = StabilityTimeout()
        assert st.timeout_seconds == 300
