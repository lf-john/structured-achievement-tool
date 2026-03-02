"""
FUSE Sentinel — Detects stale Google Drive mounts before I/O operations.

Guards remaining FUSE operations (reading new tasks, writing responses)
with a sentinel file heartbeat check. If the sentinel is missing, unreadable,
or stale, the mount is considered unhealthy and FUSE I/O is blocked until
the mount recovers.

Usage:
    sentinel = FuseSentinel("/path/to/sentinel_file")
    if sentinel.is_healthy():
        # Safe to read/write on FUSE mount
        ...
    else:
        # FUSE mount is stale — skip this cycle
        ...
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)

# Default sentinel file — a known, stable file on the FUSE mount
# Import lazily to avoid circular imports; use env var with fallback
DEFAULT_SENTINEL = os.environ.get(
    "SAT_FUSE_SENTINEL",
    os.path.expanduser("~/GoogleDrive/DriveSyncFiles/sat-tasks/CLAUDE.md"),
)

# Maximum age (seconds) before sentinel is considered stale.
# If the sentinel file's mtime is older than this AND its content is empty,
# the mount is likely hung. For a real file like CLAUDE.md, we only check
# readability and non-zero size.
STALE_THRESHOLD = 300  # 5 minutes

# rclone RC API endpoint for VFS health checks.
# Requires rclone started with --rc --rc-addr=localhost:5572 --rc-no-auth
RCLONE_RC_URL = "http://localhost:5572"
RCLONE_RC_TIMEOUT = 3  # seconds


class FuseSentinel:
    """Guard FUSE I/O operations with a sentinel file check."""

    def __init__(
        self,
        sentinel_path: str = DEFAULT_SENTINEL,
        stale_threshold: int = STALE_THRESHOLD,
        rc_url: str = RCLONE_RC_URL,
    ):
        self.sentinel_path = sentinel_path
        self.stale_threshold = stale_threshold
        self.rc_url = rc_url
        self._last_healthy: float = 0.0
        self._consecutive_failures: int = 0
        self._rc_available: Optional[bool] = None  # None = not yet checked

    def is_healthy(self) -> bool:
        """Check if the FUSE mount is healthy.

        Performs a lightweight check:
        1. Sentinel file exists
        2. Sentinel file is readable (not hung)
        3. Sentinel file has content (not an empty mount stub)

        Returns True if healthy, False if stale/unhealthy.
        """
        try:
            # Quick existence check
            if not os.path.exists(self.sentinel_path):
                self._record_failure("sentinel file does not exist")
                return False

            # Size check — a real file should have content
            size = os.path.getsize(self.sentinel_path)
            if size == 0:
                self._record_failure("sentinel file is empty")
                return False

            # Readability check — try to read a small chunk.
            # On a hung FUSE mount, this will block/timeout.
            with open(self.sentinel_path, "r", encoding="utf-8") as f:
                header = f.read(100)
            if not header:
                self._record_failure("sentinel file read returned empty")
                return False

            # Secondary signal: rclone RC API health check
            # This catches rclone process issues before they manifest as
            # filesystem problems. Non-blocking — if RC is unavailable
            # (rclone started without --rc), we rely on sentinel file alone.
            rc_status = self._check_rclone_rc()
            if rc_status is False:
                # RC is available but reports unhealthy
                self._record_failure("rclone RC API reports unhealthy VFS")
                return False
            # rc_status is True (healthy) or None (RC unavailable — ignore)

            # Success
            self._last_healthy = time.time()
            if self._consecutive_failures > 0:
                logger.info(
                    "FUSE mount recovered after %d failed checks",
                    self._consecutive_failures,
                )
            self._consecutive_failures = 0
            return True

        except OSError as e:
            self._record_failure(f"OS error: {e}")
            return False
        except Exception as e:
            self._record_failure(f"unexpected error: {e}")
            return False

    def _check_rclone_rc(self) -> Optional[bool]:
        """Check rclone RC API for VFS health.

        Returns:
            True  — rclone RC reachable and VFS is healthy
            False — rclone RC reachable but VFS has errors
            None  — rclone RC not available (not started with --rc)
        """
        try:
            # First check: is rclone process alive via /core/version
            req = urllib.request.Request(
                f"{self.rc_url}/core/stats",
                method="POST",
                data=b"{}",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=RCLONE_RC_TIMEOUT) as resp:
                data = json.loads(resp.read())

            if self._rc_available is None:
                logger.info("rclone RC API detected at %s", self.rc_url)
                self._rc_available = True

            # Check for transfer errors — non-zero fatalErrors means VFS trouble
            fatal = data.get("fatalErrors", 0)
            if fatal > 0:
                logger.warning("rclone reports %d fatal errors", fatal)
                return False

            return True

        except (urllib.error.URLError, OSError, ValueError):
            # RC endpoint not available — rclone not started with --rc
            if self._rc_available is None:
                logger.debug("rclone RC API not available at %s (this is OK)", self.rc_url)
                self._rc_available = False
            return None

    def _record_failure(self, reason: str):
        """Log a sentinel check failure."""
        self._consecutive_failures += 1
        if self._consecutive_failures <= 3 or self._consecutive_failures % 10 == 0:
            logger.warning(
                "FUSE sentinel check failed (%d consecutive): %s",
                self._consecutive_failures,
                reason,
            )

    @property
    def seconds_since_healthy(self) -> float:
        """Seconds since the last successful health check."""
        if self._last_healthy == 0.0:
            return float("inf")
        return time.time() - self._last_healthy

    @property
    def consecutive_failures(self) -> int:
        """Number of consecutive failed health checks."""
        return self._consecutive_failures

    def wait_for_healthy(self, timeout: float = 60.0, interval: float = 5.0) -> bool:
        """Block until the mount is healthy or timeout is reached.

        Returns True if mount became healthy, False on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_healthy():
                return True
            time.sleep(interval)
        return False
