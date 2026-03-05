"""
Issue Manager — Maps SAT stories to GitHub Issues.

Each story creates a GitHub Issue with:
- Labels: story type (development, config, maintenance, debug, research, review)
          + status (pending, working, complete, failed)
- Milestone: task name (created if it doesn't exist)
- Body: story description, acceptance criteria, dependencies

Bidirectional tracking: stores GitHub issue number in story state,
stores SAT story ID in issue body.
"""

import json
import logging
import re
from dataclasses import dataclass

from src.github.gh_cli import get_repo_from_remote, run_gh

logger = logging.getLogger(__name__)

# Label prefixes for organization
TYPE_LABEL_PREFIX = "type:"
STATUS_LABEL_PREFIX = "status:"

# Valid story types → GitHub labels
STORY_TYPE_LABELS = {
    "development": "type:development",
    "config": "type:config",
    "maintenance": "type:maintenance",
    "debug": "type:debug",
    "research": "type:research",
    "review": "type:review",
}

# Status labels
STATUS_LABELS = {
    "pending": "status:pending",
    "working": "status:working",
    "complete": "status:complete",
    "failed": "status:failed",
}


@dataclass
class IssueResult:
    """Result of a GitHub Issue operation."""
    success: bool
    issue_number: int | None = None
    issue_url: str | None = None
    error: str | None = None


class IssueManager:
    """Manages the SAT story ↔ GitHub Issue mapping."""

    def __init__(self, repo: str | None = None, cwd: str | None = None):
        """Initialize with optional repo override.

        Args:
            repo: GitHub repo in "owner/name" format. If not provided,
                  auto-detected from git remote.
            cwd: Working directory for git operations.
        """
        self.repo = repo or get_repo_from_remote(cwd)
        self.cwd = cwd
        self._label_cache: set = set()
        self._milestone_cache: dict = {}  # name → number

    def create_issue(
        self,
        story: dict,
        task_name: str,
    ) -> IssueResult:
        """Create a GitHub Issue from a SAT story.

        Args:
            story: Story dict with id, title, description, type, acceptanceCriteria, dependsOn.
            task_name: Parent task name (used as milestone).

        Returns:
            IssueResult with issue number and URL on success.
        """
        story_id = story.get("id", "unknown")
        story_type = story.get("type", "development")
        title = f"[{story_id}] {story.get('title', 'Untitled')}"

        # Build issue body
        body = self._build_issue_body(story)

        # Ensure labels exist
        type_label = STORY_TYPE_LABELS.get(story_type, "type:development")
        status_label = STATUS_LABELS["pending"]
        self._ensure_labels([type_label, status_label])

        # Ensure milestone exists
        milestone = self._ensure_milestone(task_name)

        # Build gh command
        args = [
            "issue", "create",
            "--title", title,
            "--body", body,
            "--label", f"{type_label},{status_label}",
        ]
        if milestone:
            args.extend(["--milestone", task_name])

        result = run_gh(args, repo=self.repo, cwd=self.cwd)

        if result.success:
            # Extract issue number and URL from output
            # gh outputs: https://github.com/owner/repo/issues/42
            url = result.stdout.strip()
            number = self._extract_issue_number(url)
            logger.info(f"Created GitHub Issue #{number} for {story_id}: {url}")
            return IssueResult(success=True, issue_number=number, issue_url=url)
        else:
            logger.error(f"Failed to create issue for {story_id}: {result.stderr}")
            return IssueResult(success=False, error=result.stderr)

    def update_status(
        self,
        issue_number: int,
        new_status: str,
    ) -> bool:
        """Update the status label on a GitHub Issue.

        Removes old status:* labels and adds the new one.

        Args:
            issue_number: GitHub issue number.
            new_status: One of: pending, working, complete, failed.

        Returns:
            True if update succeeded.
        """
        if new_status not in STATUS_LABELS:
            logger.warning(f"Invalid status '{new_status}', using 'pending'")
            new_status = "pending"

        new_label = STATUS_LABELS[new_status]
        self._ensure_labels([new_label])

        # Remove old status labels
        for status, label in STATUS_LABELS.items():
            if status != new_status:
                run_gh(
                    ["issue", "edit", str(issue_number), "--remove-label", label],
                    repo=self.repo, cwd=self.cwd,
                )

        # Add new status label
        result = run_gh(
            ["issue", "edit", str(issue_number), "--add-label", new_label],
            repo=self.repo, cwd=self.cwd,
        )

        if result.success:
            logger.info(f"Updated Issue #{issue_number} status to {new_status}")

        # Close issue if complete
        if new_status == "complete":
            run_gh(
                ["issue", "close", str(issue_number)],
                repo=self.repo, cwd=self.cwd,
            )

        return result.success

    def find_issue_by_story_id(self, story_id: str) -> int | None:
        """Find a GitHub Issue by SAT story ID.

        Searches issue titles for the [story_id] prefix pattern.

        Returns:
            Issue number if found, None otherwise.
        """
        result = run_gh(
            ["issue", "list", "--search", f"[{story_id}] in:title", "--json", "number", "--limit", "1"],
            repo=self.repo, cwd=self.cwd,
        )

        if result.success:
            try:
                issues = json.loads(result.stdout)
                if issues:
                    return issues[0]["number"]
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        return None

    def close_issue(self, issue_number: int, reason: str = "completed") -> bool:
        """Close a GitHub Issue.

        Args:
            issue_number: GitHub issue number.
            reason: "completed" or "not_planned".
        """
        args = ["issue", "close", str(issue_number)]
        if reason == "not_planned":
            args.extend(["--reason", "not planned"])

        result = run_gh(args, repo=self.repo, cwd=self.cwd)
        return result.success

    def add_comment(self, issue_number: int, body: str) -> bool:
        """Add a comment to a GitHub Issue."""
        result = run_gh(
            ["issue", "comment", str(issue_number), "--body", body],
            repo=self.repo, cwd=self.cwd,
        )
        return result.success

    # --- Private helpers ---

    def _build_issue_body(self, story: dict) -> str:
        """Build the GitHub Issue body from a story dict."""
        story_id = story.get("id", "unknown")
        description = story.get("description", "No description provided.")
        story_type = story.get("type", "development")
        complexity = story.get("complexity", "?")
        criteria = story.get("acceptanceCriteria", [])
        depends_on = story.get("dependsOn", [])

        lines = [
            f"**SAT Story ID:** `{story_id}`",
            f"**Type:** {story_type}",
            f"**Complexity:** {complexity}/10",
            "",
            "## Description",
            "",
            description,
            "",
        ]

        if criteria:
            lines.append("## Acceptance Criteria")
            lines.append("")
            for _i, criterion in enumerate(criteria, 1):
                lines.append(f"- [ ] {criterion}")
            lines.append("")

        if depends_on:
            lines.append("## Dependencies")
            lines.append("")
            for dep in depends_on:
                lines.append(f"- `{dep}`")
            lines.append("")

        lines.append("---")
        lines.append("*Created by SAT (Structured Achievement Tool)*")

        return "\n".join(lines)

    def _ensure_labels(self, labels: list[str]) -> None:
        """Ensure labels exist in the repo, creating them if needed."""
        for label in labels:
            if label in self._label_cache:
                continue

            # Check if label exists
            result = run_gh(
                ["label", "list", "--search", label, "--json", "name"],
                repo=self.repo, cwd=self.cwd,
            )

            if result.success:
                try:
                    existing = json.loads(result.stdout)
                    if any(l["name"] == label for l in existing):
                        self._label_cache.add(label)
                        continue
                except (json.JSONDecodeError, KeyError):
                    pass

            # Create label
            color = self._label_color(label)
            create_result = run_gh(
                ["label", "create", label, "--color", color, "--force"],
                repo=self.repo, cwd=self.cwd,
            )
            if create_result.success:
                self._label_cache.add(label)
                logger.debug(f"Created label: {label}")

    def _ensure_milestone(self, task_name: str) -> int | None:
        """Ensure milestone exists, creating if needed. Returns milestone number."""
        if task_name in self._milestone_cache:
            return self._milestone_cache[task_name]

        # Check if milestone exists
        result = run_gh(
            ["api", "repos/:owner/:repo/milestones", "--jq",
             f'.[] | select(.title == "{task_name}") | .number'],
            repo=self.repo, cwd=self.cwd,
        )

        if result.success and result.stdout.strip():
            try:
                number = int(result.stdout.strip())
                self._milestone_cache[task_name] = number
                return number
            except ValueError:
                pass

        # Create milestone
        create_result = run_gh(
            ["api", "repos/:owner/:repo/milestones", "--method", "POST",
             "--field", f"title={task_name}"],
            repo=self.repo, cwd=self.cwd,
        )

        if create_result.success:
            try:
                data = json.loads(create_result.stdout)
                number = data.get("number")
                if number:
                    self._milestone_cache[task_name] = number
                    logger.debug(f"Created milestone: {task_name} (#{number})")
                    return number
            except (json.JSONDecodeError, KeyError):
                pass

        return None

    def _extract_issue_number(self, url: str) -> int | None:
        """Extract issue number from GitHub URL."""
        match = re.search(r'/issues/(\d+)', url)
        if match:
            return int(match.group(1))
        return None

    def _label_color(self, label: str) -> str:
        """Assign a color to a label based on prefix."""
        colors = {
            "type:development": "0e8a16",
            "type:config": "1d76db",
            "type:maintenance": "d4c5f9",
            "type:debug": "e11d48",
            "type:research": "fbca04",
            "type:review": "c5def5",
            "status:pending": "ededed",
            "status:working": "0075ca",
            "status:complete": "0e8a16",
            "status:failed": "d73a4a",
        }
        return colors.get(label, "ededed")
