"""
PR Manager — Creates and manages pull requests for SAT stories.

Each story gets:
1. A feature branch: task/<story_id>
2. Code committed via git_manager auto_commit
3. Branch pushed to remote
4. PR created with story context as description

Integrates with git_manager for branch/worktree operations and
issue_manager for linking PRs to issues.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from src.github.gh_cli import run_gh, get_repo_from_remote
from src.execution.git_manager import (
    get_diff_stat,
    get_modified_files,
    get_current_commit,
)

logger = logging.getLogger(__name__)


@dataclass
class PRResult:
    """Result of a PR operation."""
    success: bool
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    error: Optional[str] = None


class PRManager:
    """Manages pull requests for SAT story branches."""

    def __init__(self, repo: Optional[str] = None, cwd: Optional[str] = None):
        self.repo = repo or get_repo_from_remote(cwd)
        self.cwd = cwd

    def push_branch(
        self,
        branch_name: str,
        working_directory: str,
    ) -> bool:
        """Push a local branch to remote.

        Uses git push with -u to set upstream tracking.

        Args:
            branch_name: Name of the branch to push.
            working_directory: Git repository path.

        Returns:
            True if push succeeded.
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=working_directory,
            )
            if result.returncode == 0:
                logger.info(f"Pushed branch {branch_name} to origin")
                return True
            else:
                logger.error(f"Push failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Push failed: {e}")
            return False

    def create_pr(
        self,
        story: dict,
        branch_name: str,
        base_branch: str = "main",
        working_directory: Optional[str] = None,
        issue_number: Optional[int] = None,
        draft: bool = False,
    ) -> PRResult:
        """Create a pull request for a story branch.

        Args:
            story: Story dict with id, title, description, type, acceptanceCriteria.
            branch_name: The feature branch to create PR from.
            base_branch: Target branch to merge into (default: main).
            working_directory: Git repo path for diff stats.
            issue_number: Optional linked GitHub Issue number.
            draft: Create as draft PR.

        Returns:
            PRResult with PR number and URL on success.
        """
        story_id = story.get("id", "unknown")
        title = f"[{story_id}] {story.get('title', 'Untitled')}"

        # Build PR body
        body = self._build_pr_body(story, working_directory, issue_number)

        args = [
            "pr", "create",
            "--title", title,
            "--body", body,
            "--base", base_branch,
            "--head", branch_name,
        ]

        if draft:
            args.append("--draft")

        if issue_number:
            args.extend(["--assignee", "@me"])

        result = run_gh(args, repo=self.repo, cwd=working_directory or self.cwd)

        if result.success:
            url = result.stdout.strip()
            number = self._extract_pr_number(url)
            logger.info(f"Created PR #{number} for {story_id}: {url}")
            return PRResult(success=True, pr_number=number, pr_url=url)
        else:
            logger.error(f"Failed to create PR for {story_id}: {result.stderr}")
            return PRResult(success=False, error=result.stderr)

    def find_pr_by_branch(self, branch_name: str) -> Optional[int]:
        """Find an existing PR for a branch.

        Returns:
            PR number if found, None otherwise.
        """
        result = run_gh(
            ["pr", "list", "--head", branch_name, "--json", "number", "--limit", "1"],
            repo=self.repo, cwd=self.cwd,
        )

        if result.success:
            try:
                import json
                prs = json.loads(result.stdout)
                if prs:
                    return prs[0]["number"]
            except Exception:
                pass

        return None

    def merge_pr(
        self,
        pr_number: int,
        merge_method: str = "squash",
        delete_branch: bool = True,
    ) -> bool:
        """Merge a pull request.

        Args:
            pr_number: PR number to merge.
            merge_method: "merge", "squash", or "rebase".
            delete_branch: Delete the branch after merge.

        Returns:
            True if merge succeeded.
        """
        args = ["pr", "merge", str(pr_number), f"--{merge_method}"]
        if delete_branch:
            args.append("--delete-branch")

        result = run_gh(args, repo=self.repo, cwd=self.cwd)

        if result.success:
            logger.info(f"Merged PR #{pr_number} ({merge_method})")
        else:
            logger.error(f"Failed to merge PR #{pr_number}: {result.stderr}")

        return result.success

    def get_pr_status(self, pr_number: int) -> Optional[dict]:
        """Get the current status of a PR.

        Returns:
            Dict with state, reviewDecision, mergeable, checks info.
            None if lookup fails.
        """
        result = run_gh(
            ["pr", "view", str(pr_number), "--json",
             "state,reviewDecision,mergeable,statusCheckRollup,title,number"],
            repo=self.repo, cwd=self.cwd,
        )

        if result.success:
            try:
                import json
                return json.loads(result.stdout)
            except Exception:
                pass

        return None

    def add_pr_comment(self, pr_number: int, body: str) -> bool:
        """Add a comment to a PR."""
        result = run_gh(
            ["pr", "comment", str(pr_number), "--body", body],
            repo=self.repo, cwd=self.cwd,
        )
        return result.success

    def get_review_comments(self, pr_number: int) -> list[dict]:
        """Get review comments on a PR.

        Returns:
            List of comment dicts with body, author, path, line fields.
        """
        result = run_gh(
            ["api", f"repos/:owner/:repo/pulls/{pr_number}/comments",
             "--jq", ".[].{body: .body, author: .user.login, path: .path, line: .line}"],
            repo=self.repo, cwd=self.cwd,
        )

        if result.success and result.stdout.strip():
            try:
                import json
                return json.loads(f"[{result.stdout.strip().replace(chr(10), ',')}]")
            except Exception:
                # Try line-by-line JSON objects
                comments = []
                for line in result.stdout.strip().split("\n"):
                    try:
                        comments.append(json.loads(line))
                    except Exception:
                        pass
                return comments

        return []

    # --- Private helpers ---

    def _build_pr_body(
        self,
        story: dict,
        working_directory: Optional[str] = None,
        issue_number: Optional[int] = None,
    ) -> str:
        """Build the PR description from story context."""
        story_id = story.get("id", "unknown")
        description = story.get("description", "No description.")
        story_type = story.get("type", "development")
        criteria = story.get("acceptanceCriteria", [])

        lines = [
            "## Summary",
            "",
            description,
            "",
            f"**Story:** `{story_id}` ({story_type})",
        ]

        if issue_number:
            lines.append(f"**Closes:** #{issue_number}")

        lines.append("")

        # Add change stats if available
        if working_directory:
            try:
                diff_stat = get_diff_stat(working_directory)
                if diff_stat:
                    lines.extend([
                        "## Changes",
                        "",
                        "```",
                        diff_stat,
                        "```",
                        "",
                    ])

                modified = get_modified_files(working_directory)
                if modified:
                    lines.extend([
                        "## Files Modified",
                        "",
                    ])
                    for f in modified[:20]:  # Cap at 20 files
                        lines.append(f"- `{f}`")
                    if len(modified) > 20:
                        lines.append(f"- ... and {len(modified) - 20} more")
                    lines.append("")
            except Exception:
                pass

        if criteria:
            lines.extend([
                "## Acceptance Criteria",
                "",
            ])
            for criterion in criteria:
                lines.append(f"- [ ] {criterion}")
            lines.append("")

        lines.extend([
            "---",
            "*Created by SAT (Structured Achievement Tool)*",
        ])

        return "\n".join(lines)

    def _extract_pr_number(self, url: str) -> Optional[int]:
        """Extract PR number from GitHub URL."""
        match = re.search(r'/pull/(\d+)', url)
        if match:
            return int(match.group(1))
        return None
