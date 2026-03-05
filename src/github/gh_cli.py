"""
GitHub CLI Wrapper — Thin wrapper around `gh` for all GitHub operations.

All GitHub API calls go through `gh` CLI rather than direct REST/GraphQL.
This avoids managing OAuth tokens directly — `gh auth` handles authentication.
"""

import json
import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GH_TIMEOUT = 30  # seconds


@dataclass
class GHResult:
    """Result of a gh CLI command."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    success: bool = True

    @property
    def json(self) -> dict:
        """Parse stdout as JSON."""
        if not self.stdout.strip():
            return {}
        return json.loads(self.stdout)


def run_gh(
    args: list[str],
    repo: str | None = None,
    timeout: int = GH_TIMEOUT,
    cwd: str | None = None,
) -> GHResult:
    """Run a gh CLI command and return the result.

    Args:
        args: Command arguments (e.g., ["issue", "create", "--title", "..."])
        repo: Optional repo override (owner/name). If not provided, uses
              the repo from the current git remote.
        timeout: Command timeout in seconds.
        cwd: Working directory for the command.

    Returns:
        GHResult with stdout, stderr, exit_code, and success flag.
    """
    cmd = ["gh"] + args
    if repo:
        cmd.extend(["--repo", repo])

    logger.debug(f"gh command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )

        gh_result = GHResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            success=(result.returncode == 0),
        )

        if not gh_result.success:
            logger.warning(f"gh command failed (exit {result.returncode}): {result.stderr[:300]}")

        return gh_result

    except subprocess.TimeoutExpired:
        logger.error(f"gh command timed out after {timeout}s: {' '.join(cmd)}")
        return GHResult(
            stderr=f"Timeout after {timeout}s",
            exit_code=-1,
            success=False,
        )
    except FileNotFoundError:
        logger.error("gh CLI not found. Install with: sudo apt install gh")
        return GHResult(
            stderr="gh CLI not found",
            exit_code=-1,
            success=False,
        )


def check_auth() -> bool:
    """Check if gh CLI is authenticated."""
    result = run_gh(["auth", "status"])
    return result.success


def get_repo_from_remote(cwd: str | None = None) -> str | None:
    """Extract owner/repo from git remote origin URL.

    Returns None if no remote is configured.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode != 0:
            return None

        url = result.stdout.strip()

        # SSH format: git@github.com:owner/repo.git
        if url.startswith("git@"):
            path = url.split(":")[-1]
            return path.removesuffix(".git")

        # HTTPS format: https://github.com/owner/repo.git
        if "github.com" in url:
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                repo = parts[-1].removesuffix(".git")
                owner = parts[-2]
                return f"{owner}/{repo}"

        return None
    except Exception as e:
        logger.warning(f"Failed to get repo from remote: {e}")
        return None
