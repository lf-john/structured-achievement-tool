"""
Git Manager — Worktree management, auto-commit, reset, and diff operations.

Ported from Ralph Pro GitManager (lines 1130-1288).
"""

import logging
import os
import subprocess
from dataclasses import dataclass

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


def _prune_worktrees(project_path: str) -> None:
    """Prune stale worktree references before creating new ones.

    Removes worktree entries whose directories no longer exist on disk,
    preventing 'already checked out' errors from leftover metadata.
    """
    result = _run_git(["worktree", "prune"], project_path)
    if result.returncode != 0:
        logger.warning(f"git worktree prune failed: {result.stderr.strip()}")
    else:
        logger.debug("Pruned stale worktree references")


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

    # Prune stale worktree references before creating new ones
    _prune_worktrees(project_path)

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
    target_branch: str | None = None,
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


# --- Story-level worktree isolation ---
# These functions provide per-story isolation so agentic LLMs cannot modify
# the main SAT source tree during CODE phases.  The worktree lives at
# <base_dir>/.worktrees/<story-id> on branch story/<story-id>.


def create_story_worktree(story_id: str, base_dir: str, worktree_base: str | None = None) -> str:
    """Create a git worktree for isolated story execution.

    Creates a worktree at ``<worktree_base>/<story_id>`` (or
    ``<base_dir>/.worktrees/<story_id>`` if no worktree_base is provided)
    with a new branch ``story/<story_id>`` based on the current HEAD.

    Args:
        story_id: Unique story identifier (used in path and branch name).
        base_dir: The root of the main git repository.
        worktree_base: Optional custom base directory for worktrees.
            Useful for per-project worktree locations.

    Returns:
        Absolute path to the new worktree directory.

    Raises:
        RuntimeError: If the worktree cannot be created (git not available,
            conflicting state, etc.).
    """
    # Sanitize story_id for filesystem and branch safety
    safe_id = story_id.replace("/", "_").replace(" ", "_").replace("..", "_")
    wt_base = worktree_base or os.path.join(base_dir, ".worktrees")
    worktree_path = os.path.join(wt_base, safe_id)
    branch_name = f"story/{safe_id}"

    # If the worktree already exists on disk, reuse it
    if os.path.isdir(worktree_path):
        logger.info(f"Worktree already exists at {worktree_path}, reusing")
        return worktree_path

    # Prune stale worktree references before creating new ones
    _prune_worktrees(base_dir)

    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

    # Check whether the branch already exists (leftover from a prior run)
    result = _run_git(["rev-parse", "--verify", branch_name], base_dir)
    branch_exists = result.returncode == 0

    if branch_exists:
        # Delete the stale branch so we start fresh from current HEAD
        _run_git(["branch", "-D", branch_name], base_dir)
        logger.info(f"Deleted stale branch {branch_name}")

    # Create worktree with a new branch from HEAD
    result = _run_git(
        ["worktree", "add", "-b", branch_name, worktree_path, "HEAD"],
        base_dir,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create worktree at {worktree_path}: {result.stderr.strip()}"
        )

    logger.info(f"Created worktree at {worktree_path} on branch {branch_name}")
    return worktree_path


def merge_story_worktree(
    worktree_path: str,
    base_dir: str,
    verify_after_merge: bool = True,
) -> bool:
    """Merge changes from a story worktree branch back into the current branch.

    Performs a fast-forward merge if possible, otherwise a normal merge commit.
    On merge conflict the merge is aborted and ``False`` is returned.

    After a successful merge the commit is tagged with ``story/<story_id>``
    for easy rollback.  If *verify_after_merge* is True (the default), a
    post-merge test suite is executed and the merge is reverted automatically
    when tests fail.

    Args:
        worktree_path: Path to the worktree (used to derive the branch name).
        base_dir: Root of the main git repository.
        verify_after_merge: Run ``pytest`` after merge and revert on failure.

    Returns:
        True if the merge (and optional verification) succeeded, False otherwise.
    """
    safe_id = os.path.basename(worktree_path)
    branch_name = f"story/{safe_id}"

    # First, make sure all changes in the worktree are committed
    wt_status = _run_git(["status", "--porcelain"], worktree_path)
    if wt_status.returncode == 0 and wt_status.stdout.strip():
        _run_git(["add", "-A"], worktree_path)
        _run_git(
            ["commit", "-m", f"feat({safe_id}): final worktree commit before merge"],
            worktree_path,
        )

    # Stash any dirty state in the base repo before merging
    base_status = _run_git(["status", "--porcelain"], base_dir)
    base_dirty = base_status.returncode == 0 and base_status.stdout.strip()
    if base_dirty:
        # Include untracked files in stash so they don't block the merge
        stash_result = _run_git(["stash", "push", "--include-untracked", "-m", f"pre-merge-{safe_id}"], base_dir)
        if stash_result.returncode == 0:
            logger.info(f"Stashed dirty base repo state before merging {branch_name}")
        else:
            logger.warning(f"Failed to stash base repo: {stash_result.stderr.strip()}")
            base_dirty = False  # Don't try to pop later

    # Record the current branch in the main repo so we can return to it
    head_result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], base_dir)
    original_branch = head_result.stdout.strip() if head_result.returncode == 0 else "main"

    merge_ok = False
    try:
        # Try fast-forward first
        result = _run_git(["merge", "--ff-only", branch_name], base_dir)
        if result.returncode == 0:
            logger.info(f"Fast-forward merged {branch_name} into {original_branch}")
            merge_ok = True
        else:
            # Fall back to merge commit
            result = _run_git(
                ["merge", branch_name, "-m", f"Merge story {safe_id} into {original_branch}"],
                base_dir,
            )
            if result.returncode == 0:
                logger.info(f"Merge-committed {branch_name} into {original_branch}")
                merge_ok = True
            else:
                # Merge conflict — abort
                logger.error(f"Merge conflict merging {branch_name}: {result.stderr.strip()}")
                _run_git(["merge", "--abort"], base_dir)
                return False

    except Exception as e:
        logger.error(f"Merge failed for {branch_name}: {e}")
        try:
            _run_git(["merge", "--abort"], base_dir)
        except Exception:
            pass
        return False

    finally:
        # Restore stashed state regardless of merge outcome
        if base_dirty:
            pop_result = _run_git(["stash", "pop"], base_dir)
            if pop_result.returncode == 0:
                logger.info(f"Restored stashed base repo state after merge of {branch_name}")
            else:
                logger.warning(f"Failed to pop stash after merge: {pop_result.stderr.strip()}")

    if not merge_ok:
        return False

    # Tag the merge commit for rollback support
    commit_hash = _run_git(["rev-parse", "HEAD"], base_dir)
    if commit_hash.returncode == 0:
        tag_story_commit(base_dir, safe_id, commit_hash.stdout.strip())

    # Post-merge verification
    if verify_after_merge:
        if not verify_merge(base_dir, safe_id):
            logger.warning(
                f"Post-merge verification failed for story {safe_id}; merge has been reverted"
            )
            return False

    return True


def remove_story_worktree(worktree_path: str, base_dir: str) -> None:
    """Remove a story worktree and clean up its branch.

    Safe to call even if the worktree has already been removed.

    Args:
        worktree_path: Path to the worktree directory.
        base_dir: Root of the main git repository.
    """
    safe_id = os.path.basename(worktree_path)
    branch_name = f"story/{safe_id}"

    # Remove the worktree
    if os.path.isdir(worktree_path):
        result = _run_git(["worktree", "remove", worktree_path, "--force"], base_dir)
        if result.returncode != 0:
            logger.warning(
                f"git worktree remove failed for {worktree_path}: {result.stderr.strip()}"
            )
            # Fallback: manual removal + prune
            import shutil
            try:
                shutil.rmtree(worktree_path)
            except OSError as e:
                logger.warning(f"shutil.rmtree failed for {worktree_path}: {e}")
            _run_git(["worktree", "prune"], base_dir)

    # Delete the branch
    result = _run_git(["branch", "-D", branch_name], base_dir)
    if result.returncode != 0:
        logger.debug(f"Branch {branch_name} already deleted or never existed")

    logger.info(f"Cleaned up worktree {worktree_path} and branch {branch_name}")


def get_worktree_diff(worktree_path: str) -> str:
    """Return the combined staged + unstaged diff in a worktree.

    Useful for logging what a story changed before deciding to merge or discard.

    Args:
        worktree_path: Path to the worktree directory.

    Returns:
        The diff output as a string (may be empty if no changes).
    """
    # Staged changes
    staged = _run_git(["diff", "--cached"], worktree_path)
    staged_text = staged.stdout if staged.returncode == 0 else ""

    # Unstaged changes
    unstaged = _run_git(["diff"], worktree_path)
    unstaged_text = unstaged.stdout if unstaged.returncode == 0 else ""

    # Also include untracked files as a list
    untracked = _run_git(["ls-files", "--others", "--exclude-standard"], worktree_path)
    untracked_text = ""
    if untracked.returncode == 0 and untracked.stdout.strip():
        untracked_text = f"\n=== Untracked files ===\n{untracked.stdout}"

    combined = staged_text + unstaged_text + untracked_text
    return combined.strip()


def auto_commit(
    working_directory: str,
    story_id: str,
    phase_name: str,
    message: str | None = None,
) -> str | None:
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


def get_current_commit(working_directory: str) -> str | None:
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


def get_diff(working_directory: str, against: str | None = None) -> str:
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


def get_diff_stat(working_directory: str, against: str | None = None) -> str:
    """Get a summary of changes (files modified, insertions, deletions)."""
    ref = against or "HEAD~1"
    result = _run_git(["diff", "--stat", ref, "HEAD"], working_directory)
    if result.returncode == 0:
        return result.stdout
    return ""


def get_modified_files(working_directory: str, against: str | None = None) -> list[str]:
    """Get list of modified files."""
    ref = against or "HEAD~1"
    result = _run_git(["diff", "--name-only", ref, "HEAD"], working_directory)
    if result.returncode == 0:
        return [f for f in result.stdout.strip().split("\n") if f]
    return []


# --- Rollback helpers ---


PYTEST_TIMEOUT = 120  # seconds for the test suite


def tag_story_commit(
    working_directory: str, story_id: str, commit_hash: str
) -> bool:
    """Create a git tag ``story/<story_id>`` at *commit_hash*.

    If the tag already exists it is replaced (force-created) so the tag
    always points to the latest merge for that story.

    Args:
        working_directory: Root of the git repository.
        story_id: Story identifier (used in the tag name).
        commit_hash: The commit to tag.

    Returns:
        True if the tag was created successfully.
    """
    tag_name = f"story/{story_id}"
    result = _run_git(["tag", "-f", tag_name, commit_hash], working_directory)
    if result.returncode == 0:
        logger.info(f"Tagged commit {commit_hash[:8]} as {tag_name}")
        return True
    logger.warning(f"Failed to create tag {tag_name}: {result.stderr.strip()}")
    return False


def verify_merge(working_directory: str, story_id: str) -> bool:
    """Run the test suite after a merge and revert if tests fail.

    Executes ``pytest tests/ -x -q --timeout=120`` in *working_directory*.
    If the tests pass the function returns True.  On failure the merge
    commit is reverted with ``git revert HEAD --no-edit`` (preserving
    history rather than using a hard reset) and False is returned.

    Args:
        working_directory: Root of the git repository where tests should run.
        story_id: Story identifier (used only for logging).

    Returns:
        True if tests pass, False if they fail (merge is reverted).
    """
    logger.info(f"Running post-merge verification for story {story_id}")

    try:
        result = subprocess.run(
            ["pytest", "tests/", "-x", "-q", f"--timeout={PYTEST_TIMEOUT}"],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=PYTEST_TIMEOUT + 30,  # allow a little headroom
        )
    except subprocess.TimeoutExpired:
        logger.error(f"Post-merge tests timed out for story {story_id}")
        result = None  # treat timeout as failure
    except FileNotFoundError:
        logger.warning("pytest not found; skipping post-merge verification")
        return True  # degrade gracefully — don't block merge if pytest missing

    if result is not None and result.returncode == 0:
        logger.info(f"Post-merge tests passed for story {story_id}")
        return True

    # Tests failed — revert the merge commit to preserve history
    test_output = result.stdout if result else "(timed out)"
    logger.error(
        f"Post-merge tests FAILED for story {story_id}. "
        f"Output:\n{test_output}\nReverting merge commit."
    )

    revert = _run_git(["revert", "HEAD", "--no-edit"], working_directory)
    if revert.returncode == 0:
        logger.info(f"Successfully reverted merge commit for story {story_id}")
    else:
        logger.error(
            f"Failed to revert merge commit for story {story_id}: "
            f"{revert.stderr.strip()}"
        )

    return False


def rollback_story(working_directory: str, story_id: str) -> bool:
    """Revert the commit associated with a story tag.

    Looks up the tag ``story/<story_id>`` and creates a revert commit that
    undoes the tagged commit.  This preserves full history (no hard reset).

    Args:
        working_directory: Root of the git repository.
        story_id: Story identifier whose merge should be rolled back.

    Returns:
        True if the revert succeeded, False otherwise.
    """
    tag_name = f"story/{story_id}"

    # Resolve the tag to a commit hash
    result = _run_git(["rev-list", "-n", "1", tag_name], working_directory)
    if result.returncode != 0:
        logger.error(f"Tag {tag_name} not found — cannot rollback story {story_id}")
        return False

    commit_hash = result.stdout.strip()
    logger.info(f"Rolling back story {story_id} (commit {commit_hash[:8]})")

    revert = _run_git(["revert", commit_hash, "--no-edit"], working_directory)
    if revert.returncode == 0:
        logger.info(f"Successfully rolled back story {story_id}")
        return True

    logger.error(
        f"Revert failed for story {story_id}: {revert.stderr.strip()}. "
        "Manual intervention may be required."
    )
    # Abort the revert if it left us in a conflicted state
    _run_git(["revert", "--abort"], working_directory)
    return False
