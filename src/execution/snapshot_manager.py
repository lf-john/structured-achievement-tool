"""
Snapshot Manager — Capture and restore working directory state.

Used by config/maintenance workflows to capture state before EXECUTE
and rollback on GREEN_CHECK failure.

Snapshots are git-based: we record the current commit hash and can
restore to it by resetting the working tree.
"""

import logging
import subprocess

logger = logging.getLogger(__name__)


def capture_snapshot(working_directory: str) -> str | None:
    """Capture current git state as a snapshot (commit hash).

    Stages and commits any uncommitted changes first to ensure
    the snapshot is complete.

    Returns the commit hash, or None if capture fails.
    """
    try:
        # Commit any pending changes so we have a clean snapshot point
        subprocess.run(
            ["git", "add", "-A"],
            cwd=working_directory,
            capture_output=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", "SAT: pre-execute snapshot", "--allow-empty"],
            cwd=working_directory,
            capture_output=True,
            timeout=30,
        )

        # Get current commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            commit_hash = result.stdout.strip()
            logger.info(f"Snapshot captured: {commit_hash[:12]}")
            return commit_hash
        else:
            logger.error(f"Failed to get HEAD: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"Snapshot capture failed: {e}")
        return None


def rollback_to_snapshot(working_directory: str, snapshot_hash: str) -> bool:
    """Rollback working directory to a previous snapshot.

    Uses git reset --hard to restore to the snapshot commit.
    Returns True if rollback succeeded.
    """
    if not snapshot_hash:
        logger.warning("No snapshot hash provided, cannot rollback")
        return False

    try:
        result = subprocess.run(
            ["git", "reset", "--hard", snapshot_hash],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"Rollback to snapshot {snapshot_hash[:12]} succeeded")
            return True
        else:
            logger.error(f"Rollback failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return False
