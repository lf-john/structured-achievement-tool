"""
FUSE Integration Tests — Option E.

Tests for FUSE mount health, read/write operations, sync timing,
and sentinel file checks. These tests require the FUSE mount to be
available and are automatically skipped when it is not.

Run explicitly:  pytest tests/test_fuse_integration.py -v
Not included in standard test suite (requires live FUSE mount).
"""

import os
import time

import pytest

from src.execution.fuse_sentinel import FuseSentinel

# Skip entire module if FUSE mount is not available
FUSE_ROOT = os.path.expanduser("~/GoogleDrive/DriveSyncFiles")
FUSE_AVAILABLE = os.path.isdir(FUSE_ROOT) and os.listdir(FUSE_ROOT)

pytestmark = pytest.mark.skipif(
    not FUSE_AVAILABLE,
    reason="FUSE mount not available at ~/GoogleDrive/DriveSyncFiles",
)


class TestFuseSentinel:
    """Test the FUSE sentinel health check."""

    def test_sentinel_healthy_with_real_mount(self):
        """Sentinel check should pass when FUSE is mounted."""
        sentinel = FuseSentinel()
        assert sentinel.is_healthy() is True

    def test_sentinel_unhealthy_with_missing_file(self):
        """Sentinel check should fail when sentinel file doesn't exist."""
        sentinel = FuseSentinel(sentinel_path="/nonexistent/path/to/file.md")
        assert sentinel.is_healthy() is False
        assert sentinel.consecutive_failures == 1

    def test_sentinel_consecutive_failures_increment(self):
        """Consecutive failures should increment on repeated failures."""
        sentinel = FuseSentinel(sentinel_path="/nonexistent/path/to/file.md")
        sentinel.is_healthy()
        sentinel.is_healthy()
        sentinel.is_healthy()
        assert sentinel.consecutive_failures == 3

    def test_sentinel_recovers_after_failure(self):
        """Sentinel should reset failure counter on recovery."""
        sentinel = FuseSentinel()
        # Force a failure first
        sentinel._consecutive_failures = 5
        # Now check with real mount — should recover
        assert sentinel.is_healthy() is True
        assert sentinel.consecutive_failures == 0

    def test_seconds_since_healthy(self):
        """seconds_since_healthy should return a reasonable value."""
        sentinel = FuseSentinel()
        # Before any check, should be infinity
        assert sentinel.seconds_since_healthy == float("inf")
        # After a check, should be near zero
        sentinel.is_healthy()
        assert sentinel.seconds_since_healthy < 2.0


class TestFuseReadOperations:
    """Test reading from FUSE mount."""

    def test_read_known_file(self):
        """Should be able to read CLAUDE.md from FUSE mount."""
        claude_md = os.path.join(FUSE_ROOT, "sat-tasks", "CLAUDE.md")
        if not os.path.exists(claude_md):
            pytest.skip("CLAUDE.md not found in sat-tasks/")
        with open(claude_md) as f:
            content = f.read()
        assert len(content) > 0
        assert "Claude" in content or "claude" in content.lower()

    def test_list_task_directories(self):
        """Should be able to list task directories."""
        tasks_dir = os.path.join(FUSE_ROOT, "sat-tasks")
        if not os.path.exists(tasks_dir):
            pytest.skip("sat-tasks/ not found")
        entries = os.listdir(tasks_dir)
        assert len(entries) > 0

    def test_read_does_not_hang(self):
        """File reads should complete within a reasonable time."""
        claude_md = os.path.join(FUSE_ROOT, "sat-tasks", "CLAUDE.md")
        if not os.path.exists(claude_md):
            pytest.skip("CLAUDE.md not found in sat-tasks/")
        start = time.time()
        with open(claude_md) as f:
            _ = f.read()
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Read took {elapsed:.1f}s (expected < 5s)"


class TestFuseWriteOperations:
    """Test writing to FUSE mount (uses a temp file, cleans up after)."""

    def test_write_and_read_back(self):
        """Should be able to write a file and read it back."""
        test_dir = os.path.join(FUSE_ROOT, "sat-tasks", "_test_temp")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "_fuse_test.md")
        try:
            content = f"FUSE test at {time.time()}\n"
            with open(test_file, "w") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            with open(test_file) as f:
                read_back = f.read()
            assert read_back == content
        finally:
            try:
                os.remove(test_file)
                os.rmdir(test_dir)
            except OSError:
                pass

    def test_fsync_completes(self):
        """os.fsync() should complete without hanging."""
        test_dir = os.path.join(FUSE_ROOT, "sat-tasks", "_test_temp")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "_fuse_fsync_test.md")
        try:
            start = time.time()
            with open(test_file, "w") as f:
                f.write("fsync test\n")
                f.flush()
                os.fsync(f.fileno())
            elapsed = time.time() - start
            assert elapsed < 10.0, f"fsync took {elapsed:.1f}s (expected < 10s)"
        finally:
            try:
                os.remove(test_file)
                os.rmdir(test_dir)
            except OSError:
                pass


class TestFuseSyncTiming:
    """Test sync timing characteristics of the FUSE mount.

    These tests characterize how quickly changes propagate
    through the FUSE layer. Not pass/fail per se, but useful
    for understanding timing constraints.
    """

    def test_file_mtime_updates_on_write(self):
        """mtime should update when a file is written."""
        test_dir = os.path.join(FUSE_ROOT, "sat-tasks", "_test_temp")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "_mtime_test.md")
        try:
            with open(test_file, "w") as f:
                f.write("v1\n")
                f.flush()
                os.fsync(f.fileno())
            mtime1 = os.path.getmtime(test_file)
            time.sleep(1.1)  # Ensure different timestamp
            with open(test_file, "w") as f:
                f.write("v2\n")
                f.flush()
                os.fsync(f.fileno())
            mtime2 = os.path.getmtime(test_file)
            assert mtime2 > mtime1, "mtime did not update after write"
        finally:
            try:
                os.remove(test_file)
                os.rmdir(test_dir)
            except OSError:
                pass
