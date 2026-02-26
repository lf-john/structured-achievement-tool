"""Stability Timeout Fallback for SAT task processing.

Tracks task files waiting for user acknowledgement (# <Pending> marker).
If a file remains unmodified for the configured timeout period, it is
treated as ready for processing — a fallback for when the user forgets
to remove the '#' safety prefix.

Phase 2, item 2.12.
"""

import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StabilityTimeout:
    """Track file modification times and trigger auto-processing after timeout.

    The daemon's poll cycle calls check_file() each iteration. Files containing
    '# <Pending>' that remain unmodified for timeout_seconds are considered
    ready. Files with '<Working>' or without the '# <Pending>' marker are
    never auto-processed.
    """

    def __init__(self, timeout_seconds: int = 300):
        self.timeout_seconds = timeout_seconds
        # file_path -> (tracked_mtime, first_seen_at)
        # tracked_mtime: the mtime we observed when we started (or re-started) tracking
        # first_seen_at: wall-clock time when we first saw that mtime unchanged
        self._tracked_files: dict[str, tuple[float, float]] = {}

    def check_file(self, file_path: str) -> bool:
        """Check if a file has timed out and should be auto-processed.

        Returns True if the file should be processed (timeout expired).
        Returns False if not ready yet.
        """
        if not os.path.isfile(file_path):
            self._tracked_files.pop(file_path, None)
            return False

        # Check markers
        if not self._has_pending_marker(file_path):
            # No '# <Pending>' — stop tracking if we were
            if file_path in self._tracked_files:
                logger.debug(
                    "File no longer has # <Pending> marker, removing from tracking: %s",
                    file_path,
                )
                self._tracked_files.pop(file_path, None)
            return False

        if self._has_working_marker(file_path):
            # Actively being worked on — do not timeout
            if file_path in self._tracked_files:
                logger.debug(
                    "File has <Working> marker, removing from tracking: %s",
                    file_path,
                )
                self._tracked_files.pop(file_path, None)
            return False

        # File qualifies for tracking
        current_mtime = os.path.getmtime(file_path)
        now = time.time()

        if file_path not in self._tracked_files:
            # Start tracking
            self._tracked_files[file_path] = (current_mtime, now)
            logger.debug(
                "Started stability tracking for %s (mtime=%.2f)",
                file_path,
                current_mtime,
            )
            return False

        tracked_mtime, first_seen_at = self._tracked_files[file_path]

        if current_mtime != tracked_mtime:
            # File was modified — user is editing, reset timer
            self._tracked_files[file_path] = (current_mtime, now)
            logger.debug(
                "File modified, resetting stability timer for %s (new mtime=%.2f)",
                file_path,
                current_mtime,
            )
            return False

        # mtime unchanged — check if timeout has elapsed
        elapsed = now - first_seen_at
        if elapsed >= self.timeout_seconds:
            logger.info(
                "Stability timeout triggered for %s after %.0f seconds "
                "(timeout=%d). Auto-processing as ready.",
                file_path,
                elapsed,
                self.timeout_seconds,
            )
            return True

        return False

    def reset(self, file_path: str) -> None:
        """Reset tracking for a file (e.g., after processing)."""
        if file_path in self._tracked_files:
            logger.debug("Reset stability tracking for %s", file_path)
            self._tracked_files.pop(file_path, None)

    def is_tracking(self, file_path: str) -> bool:
        """Check if a file is currently being tracked."""
        return file_path in self._tracked_files

    def _has_pending_marker(self, file_path: str) -> bool:
        """Check if file contains '# <Pending>' (safety marker).

        This is the user-convention marker where '# <Pending>' means
        the user hasn't yet acknowledged — the '#' prefix is the safety
        gate that SAT waits for the user to remove.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return "# <Pending>" in content
        except (OSError, UnicodeDecodeError):
            return False

    def _has_working_marker(self, file_path: str) -> bool:
        """Check if file contains '<Working>' (should not timeout)."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return "<Working>" in content
        except (OSError, UnicodeDecodeError):
            return False

    def get_tracked_files(self) -> dict[str, float]:
        """Return dict of tracked files and their remaining timeout seconds.

        Values are seconds remaining before timeout triggers.
        Negative values mean the timeout has already elapsed.
        """
        now = time.time()
        result = {}
        for file_path, (tracked_mtime, first_seen_at) in self._tracked_files.items():
            elapsed = now - first_seen_at
            remaining = self.timeout_seconds - elapsed
            result[file_path] = remaining
        return result
