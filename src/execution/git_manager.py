"""
Git Manager — Worktree management, auto-commit, reset, and diff operations.

Ported from Ralph Pro GitManager (lines 1130-1288).
"""

import os
import subprocess
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

GIT_TIMEOUT = 30  # seconds


@dataclass
class WorktreeInfo:
    """Result of worktree creation."""
    success: bool
    worktree_path: str = ""
    branch_name: str = ""
    existed: bool = False
    error: str = ""


def _run_git(args: list[str], cwd: str, timeout: int = GIT_TIMEOUT) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    cmd = ["git"] + args
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
    )


def _get_default_branch(project_path: str) -> str:
    """Detect the default branch (main, master, develop)."""
    # Method 1: symbolic-ref
    try:
        result = _run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], project_path)
        if result.returncode == 0:
            ref = result.stdout.strip()
            return ref.split("/")[-1]
    except Exception:
        pass

    # Method 2: check local branches
    for branch in ["main", "master", "develop"]:
        result = _run_git(["rev-parse", "--verify", branch], project_path)
        if result.returncode == 0:
            return branch

    # Method 3: current HEAD
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], project_path)
    if result.returncode == 0:
        return result.stdout.strip()

    return "main"


def create_worktree(project_path: str, task_id: str) -> WorktreeInfo:
    """Create a git worktree for isolated task execution.

    Creates worktree at project_path/worktrees/task_id with branch task/task_id.
    """
    worktree_path = os.path.join(project_path, "worktrees", task_id)
    branch_name = f"task/{task_id}"

    # Check if worktree already exists
    if os.path.exists(worktree_path):
        return WorktreeInfo(
            success=True,
            worktree_path=worktree_path,
            branch_name=branch_name,
            existed=True,
        )

    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

    # Check if branch exists
    result = _run_git(["rev-parse", "--verify", branch_name], project_path)
    branch_exists = result.returncode == 0

    try:
        if branch_exists:
            _run_git(["worktree", "add", worktree_path, branch_name], project_path)
        else:
            default_branch = _get_default_branch(project_path)
            _run_git(["worktree", "add", "-b", branch_name, worktree_path, default_branch], project_path)

        return WorktreeInfo(
            success=True,
            worktree_path=worktree_path,
            branch_name=branch_name,
        )
    except Exception as e:
        return WorktreeInfo(success=False, error=str(e))


def remove_worktree(project_path: str, task_id: str, delete_branch: bool = False):
    """Remove a worktree and optionally its branch."""
    worktree_path = os.path.join(project_path, "worktrees", task_id)

    try:
        _run_git(["worktree", "remove", worktree_path, "--force"], project_path)
    except Exception as e:
        logger.warning(f"Failed to remove worktree {worktree_path}: {e}")

    if delete_branch:
        branch_name = f"task/{task_id}"
        try:
            _run_git(["branch", "-D", branch_name], project_path)
        except Exception as e:
            logger.warning(f"Failed to delete branch {branch_name}: {e}")


def merge_worktree(
    project_path: str,
    task_id: str,
    target_branch: Optional[str] = None,
) -> bool:
    """Merge a task branch into the target branch."""
    branch_name = f"task/{task_id}"
    target = target_branch or _get_default_branch(project_path)

    try:
        # Switch to target branch
        _run_git(["checkout", target], project_path)

        # Try fast-forward merge first
        result = _run_git(["merge", "--ff-only", branch_name], project_path)
        if result.returncode == 0:
            return True

        # Fall back to merge commit
        result = _run_git(["merge", branch_name, "-m", f"Merge {branch_name} into {target}"], project_path)
        return result.returncode == 0

    except Exception as e:
        logger.error(f"Merge failed for {branch_name}: {e}")
        return False


def auto_commit(
    working_directory: str,
    story_id: str,
    phase_name: str,
    message: Optional[str] = None,
) -> Optional[str]:
    """Commit all changes with a standardized message.

    Returns the commit hash if a commit was made, None if no changes.
    """
    # Check for changes
    result = _run_git(["status", "--porcelain"], working_directory)
    if not result.stdout.strip():
        return None  # No changes to commit

    # Clean up problematic files (Windows reserved names)
    for bad_name in ["nul", "con", "prn", "aux"]:
        bad_path = os.path.join(working_directory, bad_name)
        if os.path.exists(bad_path):
            os.remove(bad_path)

    # Stage all changes
    _run_git(["add", "-A"], working_directory)

    # Commit
    msg = message or f"feat({story_id}): {phase_name} phase"
    result = _run_git(["commit", "-m", msg], working_directory)

    if result.returncode != 0:
        logger.warning(f"Commit failed: {result.stderr}")
        return None

    # Get commit hash
    hash_result = _run_git(["rev-parse", "HEAD"], working_directory)
    if hash_result.returncode == 0:
        return hash_result.stdout.strip()

    return None


def get_current_commit(working_directory: str) -> Optional[str]:
    """Get the current HEAD commit hash."""
    result = _run_git(["rev-parse", "HEAD"], working_directory)
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def reset_to_commit(working_directory: str, commit_hash: str) -> bool:
    """Hard reset to a specific commit."""
    result = _run_git(["reset", "--hard", commit_hash], working_directory)
    if result.returncode != 0:
        logger.error(f"Reset failed: {result.stderr}")
        return False

    # Clean untracked files
    _run_git(["clean", "-fd"], working_directory)
    return True


def get_diff(working_directory: str, against: Optional[str] = None) -> str:
    """Get the diff of changes.

    Args:
        working_directory: Git repo path
        against: Commit to diff against (default: HEAD~1)
    """
    ref = against or "HEAD~1"
    result = _run_git(["diff", ref, "HEAD"], working_directory)
    if result.returncode == 0:
        return result.stdout
    return ""


def get_diff_stat(working_directory: str, against: Optional[str] = None) -> str:
    """Get a summary of changes (files modified, insertions, deletions)."""
    ref = against or "HEAD~1"
    result = _run_git(["diff", "--stat", ref, "HEAD"], working_directory)
    if result.returncode == 0:
        return result.stdout
    return ""


def get_modified_files(working_directory: str, against: Optional[str] = None) -> list[str]:
    """Get list of modified files."""
    ref = against or "HEAD~1"
    result = _run_git(["diff", "--name-only", ref, "HEAD"], working_directory)
    if result.returncode == 0:
        return [f for f in result.stdout.strip().split("\n") if f]
    return []
