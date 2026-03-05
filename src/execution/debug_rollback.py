"""
Debug Rollback Manager — Tag-based rollback for debug fix attempts.

Phase 2.3: Before applying any debug fix, tags the current state so that
failed fixes can be cleanly rolled back via git reset --hard.

Tag naming convention:
    debug-{task_id}-attempt-{n}-pre   (created before fix is applied)
    debug-{task_id}-attempt-{n}-post  (created after successful fix)
"""

import logging

from src.execution.git_manager import (
    _run_git,
    auto_commit,
    get_current_commit,
    reset_to_commit,
)

logger = logging.getLogger(__name__)


class DebugRollbackError(Exception):
    """Raised when a debug rollback operation fails."""


class DebugRollback:
    """Manages git-tag-based rollback for debug fix attempts.

    Workflow:
        1. Check for uncommitted changes; stash if needed.
        2. create_pre_fix_tag() — snapshot before the fix.
        3. Apply the fix (external caller).
        4. Run validation (external caller).
        5a. On success: create_post_fix_tag().
        5b. On failure: rollback() to pre-fix tag.
    """

    def __init__(self, working_directory: str):
        self.working_directory = working_directory

    # ------------------------------------------------------------------
    # Tag helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tag_name(task_id: str, attempt: int, phase: str) -> str:
        """Build a canonical tag name.

        Args:
            task_id: Task identifier (e.g. 'SAT-042').
            attempt: Attempt number (1-based).
            phase: Either 'pre' or 'post'.
        """
        return f"debug-{task_id}-attempt-{attempt}-{phase}"

    def _tag_exists(self, tag_name: str) -> bool:
        """Return True if the tag already exists locally."""
        result = _run_git(
            ["rev-parse", "--verify", f"refs/tags/{tag_name}"],
            self.working_directory,
        )
        return result.returncode == 0

    def _create_tag(self, tag_name: str, message: str) -> str:
        """Create an annotated git tag at HEAD.

        Returns the tag name on success.
        Raises DebugRollbackError on failure.
        """
        result = _run_git(
            ["tag", "-a", tag_name, "-m", message],
            self.working_directory,
        )
        if result.returncode != 0:
            raise DebugRollbackError(
                f"Failed to create tag '{tag_name}': {result.stderr.strip()}"
            )
        logger.info("Created tag %s", tag_name)
        return tag_name

    def _delete_tag(self, tag_name: str) -> bool:
        """Delete a local tag. Returns True on success."""
        result = _run_git(["tag", "-d", tag_name], self.working_directory)
        if result.returncode != 0:
            logger.warning(
                "Failed to delete tag '%s': %s", tag_name, result.stderr.strip()
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_uncommitted_changes(self) -> bool:
        """Check for uncommitted changes (staged or unstaged) in the working directory."""
        result = _run_git(["status", "--porcelain"], self.working_directory)
        if result.returncode != 0:
            logger.error(
                "git status failed: %s", result.stderr.strip()
            )
            # Conservative: treat errors as "yes, there are changes"
            return True
        return bool(result.stdout.strip())

    def stash_changes(self) -> bool:
        """Stash any uncommitted changes before debug starts.

        Returns True if changes were stashed (or there was nothing to stash).
        Returns False on error.
        """
        if not self.has_uncommitted_changes():
            logger.debug("No uncommitted changes to stash.")
            return True

        result = _run_git(
            ["stash", "push", "-m", "debug-rollback: pre-debug stash"],
            self.working_directory,
        )
        if result.returncode != 0:
            logger.error("git stash failed: %s", result.stderr.strip())
            return False

        logger.info("Stashed uncommitted changes before debug session.")
        return True

    def pop_stash(self) -> bool:
        """Restore the most recent stashed changes.

        Returns True on success, False on failure (e.g. merge conflict).
        """
        result = _run_git(["stash", "pop"], self.working_directory)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.error("git stash pop failed: %s", stderr)
            # If pop fails due to conflict, the stash is NOT dropped — user
            # can resolve manually.  We do NOT auto-drop.
            return False

        logger.info("Restored stashed changes.")
        return True

    def create_pre_fix_tag(self, task_id: str, attempt: int) -> str:
        """Create the pre-fix snapshot tag.

        Raises DebugRollbackError if there are uncommitted changes (caller
        should stash or commit first) or if tagging fails.

        Returns the tag name.
        """
        if self.has_uncommitted_changes():
            raise DebugRollbackError(
                "Uncommitted changes detected. Stash or commit before "
                "creating a pre-fix tag."
            )

        tag_name = self._tag_name(task_id, attempt, "pre")

        if self._tag_exists(tag_name):
            logger.warning(
                "Tag '%s' already exists — deleting and re-creating.", tag_name
            )
            self._delete_tag(tag_name)

        commit = get_current_commit(self.working_directory)
        logger.info(
            "Creating pre-fix tag for task=%s attempt=%d at commit=%s",
            task_id,
            attempt,
            commit or "unknown",
        )
        return self._create_tag(
            tag_name,
            f"Pre-fix snapshot for task {task_id}, attempt {attempt}",
        )

    def create_post_fix_tag(self, task_id: str, attempt: int) -> str:
        """Create the post-fix tag after a successful fix.

        Returns the tag name.  Raises DebugRollbackError on failure.
        """
        tag_name = self._tag_name(task_id, attempt, "post")

        if self._tag_exists(tag_name):
            logger.warning(
                "Tag '%s' already exists — deleting and re-creating.", tag_name
            )
            self._delete_tag(tag_name)

        commit = get_current_commit(self.working_directory)
        logger.info(
            "Creating post-fix tag for task=%s attempt=%d at commit=%s",
            task_id,
            attempt,
            commit or "unknown",
        )
        return self._create_tag(
            tag_name,
            f"Post-fix snapshot for task {task_id}, attempt {attempt}",
        )

    def rollback(self, tag_name: str) -> bool:
        """Hard-reset the working directory to *tag_name*.

        Uses git_manager.reset_to_commit under the hood (which also cleans
        untracked files).

        Returns True on success, False on failure.
        """
        if not self._tag_exists(tag_name):
            logger.error(
                "Cannot rollback: tag '%s' does not exist.", tag_name
            )
            return False

        # Resolve tag to commit hash
        result = _run_git(
            ["rev-list", "-n", "1", tag_name],
            self.working_directory,
        )
        if result.returncode != 0:
            logger.error(
                "Failed to resolve tag '%s' to a commit: %s",
                tag_name,
                result.stderr.strip(),
            )
            return False

        commit_hash = result.stdout.strip()
        logger.info(
            "Rolling back to tag '%s' (commit %s).", tag_name, commit_hash
        )

        success = reset_to_commit(self.working_directory, commit_hash)
        if success:
            logger.info("Rollback to '%s' succeeded.", tag_name)
        else:
            logger.error("Rollback to '%s' failed.", tag_name)
        return success

    # ------------------------------------------------------------------
    # Convenience: full attempt lifecycle
    # ------------------------------------------------------------------

    def attempt_fix(
        self,
        task_id: str,
        attempt: int,
        apply_fn,
        validate_fn,
    ) -> bool:
        """Run a complete fix-and-validate cycle with automatic rollback.

        Args:
            task_id: Task identifier.
            attempt: 1-based attempt number.
            apply_fn: Callable that applies the fix. Receives no arguments.
                      May raise on failure.
            validate_fn: Callable that returns True if the fix is valid.

        Returns True if the fix passed validation, False otherwise.
        """
        # 1. Ensure clean state
        if self.has_uncommitted_changes():
            logger.info("Stashing uncommitted changes before attempt.")
            if not self.stash_changes():
                logger.error("Cannot stash changes; aborting attempt.")
                return False

        # 2. Pre-fix tag
        pre_tag = self.create_pre_fix_tag(task_id, attempt)

        # 3. Apply fix
        try:
            apply_fn()
        except Exception as exc:
            logger.error("apply_fn raised: %s — rolling back.", exc)
            self.rollback(pre_tag)
            return False

        # 4. Auto-commit the fix so validation runs against committed state
        commit_hash = auto_commit(
            self.working_directory,
            task_id,
            "debug-fix",
            message=f"debug({task_id}): attempt {attempt} fix",
        )
        if commit_hash:
            logger.info("Fix committed as %s.", commit_hash)

        # 5. Validate
        try:
            valid = validate_fn()
        except Exception as exc:
            logger.error("validate_fn raised: %s — treating as failure.", exc)
            valid = False

        if valid:
            self.create_post_fix_tag(task_id, attempt)
            logger.info(
                "Attempt %d for task %s PASSED validation.", attempt, task_id
            )
            return True

        # 6. Rollback on failure
        logger.warning(
            "Attempt %d for task %s FAILED validation — rolling back.",
            attempt,
            task_id,
        )
        self.rollback(pre_tag)
        return False
