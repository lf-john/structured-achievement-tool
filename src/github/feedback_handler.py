"""
Feedback Handler — Converts PR review comments into follow-up SAT stories.

Reads review comments from a PR, groups them by file/concern, and creates
new SAT story files that can be picked up by the daemon for processing.

Each review comment becomes a follow-up story with:
- Type based on comment content (debug for bugs, development for features, etc.)
- Reference to the original PR and story
- Acceptance criteria derived from the review feedback
"""

import json
import logging
import os
from dataclasses import dataclass

from src.github.gh_cli import get_repo_from_remote, run_gh

logger = logging.getLogger(__name__)


@dataclass
class ReviewComment:
    """A single review comment from a PR."""
    body: str
    author: str
    path: str | None = None
    line: int | None = None
    comment_type: str = "general"  # general, inline, review


@dataclass
class FollowUpStory:
    """A follow-up story generated from review feedback."""
    story_id: str
    title: str
    description: str
    story_type: str
    source_pr: int
    source_story_id: str
    acceptance_criteria: list


class FeedbackHandler:
    """Processes PR review feedback into actionable follow-up stories."""

    def __init__(self, repo: str | None = None, cwd: str | None = None):
        self.repo = repo or get_repo_from_remote(cwd)
        self.cwd = cwd

    def get_review_comments(self, pr_number: int) -> list[ReviewComment]:
        """Fetch all review comments from a PR.

        Collects both inline code review comments and general review comments.

        Returns:
            List of ReviewComment objects.
        """
        comments = []

        # Get inline review comments (on specific lines)
        result = run_gh(
            ["api", f"repos/:owner/:repo/pulls/{pr_number}/comments",
             "--paginate"],
            repo=self.repo, cwd=self.cwd,
        )

        if result.success and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                for comment in data:
                    comments.append(ReviewComment(
                        body=comment.get("body", ""),
                        author=comment.get("user", {}).get("login", "unknown"),
                        path=comment.get("path"),
                        line=comment.get("line") or comment.get("original_line"),
                        comment_type="inline",
                    ))
            except json.JSONDecodeError:
                pass

        # Get general review comments (not on specific lines)
        review_result = run_gh(
            ["api", f"repos/:owner/:repo/pulls/{pr_number}/reviews",
             "--paginate"],
            repo=self.repo, cwd=self.cwd,
        )

        if review_result.success and review_result.stdout.strip():
            try:
                reviews = json.loads(review_result.stdout)
                for review in reviews:
                    body = review.get("body", "").strip()
                    if body:  # Skip empty review bodies
                        comments.append(ReviewComment(
                            body=body,
                            author=review.get("user", {}).get("login", "unknown"),
                            comment_type="review",
                        ))
            except json.JSONDecodeError:
                pass

        logger.info(f"Fetched {len(comments)} review comments from PR #{pr_number}")
        return comments

    def generate_follow_up_stories(
        self,
        pr_number: int,
        source_story_id: str,
        task_name: str,
        comments: list[ReviewComment] | None = None,
    ) -> list[FollowUpStory]:
        """Generate follow-up stories from PR review comments.

        Groups related comments and creates a story for each distinct concern.

        Args:
            pr_number: The PR number with review feedback.
            source_story_id: The original story ID that created this PR.
            task_name: Task name for story ID generation.
            comments: Optional pre-fetched comments. If None, fetches from API.

        Returns:
            List of FollowUpStory objects.
        """
        if comments is None:
            comments = self.get_review_comments(pr_number)

        if not comments:
            logger.info(f"No review comments on PR #{pr_number}")
            return []

        # Group comments by file (inline) and keep general ones separate
        file_groups: dict[str, list[ReviewComment]] = {}
        general_comments: list[ReviewComment] = []

        for comment in comments:
            if comment.path:
                file_groups.setdefault(comment.path, []).append(comment)
            else:
                general_comments.append(comment)

        stories = []
        counter = 1

        # Create stories from file-grouped inline comments
        for filepath, file_comments in file_groups.items():
            story = self._create_story_from_comments(
                comments=file_comments,
                source_pr=pr_number,
                source_story_id=source_story_id,
                task_name=task_name,
                counter=counter,
                filepath=filepath,
            )
            stories.append(story)
            counter += 1

        # Create stories from general review comments
        for comment in general_comments:
            story = self._create_story_from_comments(
                comments=[comment],
                source_pr=pr_number,
                source_story_id=source_story_id,
                task_name=task_name,
                counter=counter,
            )
            stories.append(story)
            counter += 1

        logger.info(f"Generated {len(stories)} follow-up stories from PR #{pr_number}")
        return stories

    def write_story_files(
        self,
        stories: list[FollowUpStory],
        output_dir: str,
    ) -> list[str]:
        """Write follow-up stories as task files for daemon pickup.

        Each story becomes a markdown file with <Pending> tag in the
        output directory, ready for the SAT daemon to process.

        Args:
            stories: List of follow-up stories to write.
            output_dir: Directory to write story files into.

        Returns:
            List of file paths written.
        """
        os.makedirs(output_dir, exist_ok=True)
        written_files = []

        for story in stories:
            filename = f"{story.story_id}_follow-up.md"
            filepath = os.path.join(output_dir, filename)

            content = self._build_story_file(story)

            with open(filepath, "w") as f:
                f.write(content)

            # fsync for Google Drive reliability
            try:
                fd = os.open(filepath, os.O_RDONLY)
                os.fsync(fd)
                os.close(fd)
            except OSError:
                pass

            written_files.append(filepath)
            logger.info(f"Wrote follow-up story: {filepath}")

        return written_files

    # --- Private helpers ---

    def _create_story_from_comments(
        self,
        comments: list[ReviewComment],
        source_pr: int,
        source_story_id: str,
        task_name: str,
        counter: int,
        filepath: str | None = None,
    ) -> FollowUpStory:
        """Create a single follow-up story from a group of comments."""
        # Determine story type from comment content
        story_type = self._classify_feedback_type(comments)

        # Generate story ID
        story_id = f"{source_story_id}-fb{counter}"

        # Build title
        if filepath:
            basename = os.path.basename(filepath)
            title = f"Address review feedback on {basename}"
        else:
            # Use first few words of comment
            first_body = comments[0].body[:60].strip()
            if len(comments[0].body) > 60:
                first_body += "..."
            title = f"Review feedback: {first_body}"

        # Build description
        description_parts = [
            f"Follow-up from PR #{source_pr} (story {source_story_id}).",
            "",
        ]

        if filepath:
            description_parts.append(f"**File:** `{filepath}`")
            description_parts.append("")

        description_parts.append("**Review comments:**")
        description_parts.append("")

        for comment in comments:
            author = comment.author
            location = ""
            if comment.path and comment.line:
                location = f" (line {comment.line})"
            elif comment.path:
                location = f" ({comment.path})"
            description_parts.append(f"- @{author}{location}: {comment.body}")

        description = "\n".join(description_parts)

        # Build acceptance criteria
        criteria = [
            f"All review feedback from PR #{source_pr} is addressed",
        ]
        if filepath:
            criteria.append(f"Changes to `{filepath}` satisfy reviewer concerns")
        criteria.append("Updated code passes all existing tests")

        return FollowUpStory(
            story_id=story_id,
            title=title,
            description=description,
            story_type=story_type,
            source_pr=source_pr,
            source_story_id=source_story_id,
            acceptance_criteria=criteria,
        )

    def _classify_feedback_type(self, comments: list[ReviewComment]) -> str:
        """Classify the type of follow-up story based on comment content."""
        combined = " ".join(c.body.lower() for c in comments)

        # Bug indicators
        if any(word in combined for word in ["bug", "broken", "crash", "error", "fix", "wrong"]):
            return "debug"

        # Security indicators
        if any(word in combined for word in ["security", "vulnerability", "injection", "xss", "auth"]):
            return "debug"

        # Refactoring indicators
        if any(word in combined for word in ["refactor", "cleanup", "simplify", "rename"]):
            return "maintenance"

        # Documentation indicators
        if any(word in combined for word in ["document", "comment", "readme", "docstring"]):
            return "maintenance"

        # Default to development (feature work)
        return "development"

    def _build_story_file(self, story: FollowUpStory) -> str:
        """Build the markdown file content for a follow-up story."""
        lines = [
            f"# {story.title}",
            "",
            story.description,
            "",
            "## Acceptance Criteria",
            "",
        ]

        for criterion in story.acceptance_criteria:
            lines.append(f"- {criterion}")

        lines.extend([
            "",
            f"**Type:** {story.story_type}",
            f"**Source PR:** #{story.source_pr}",
            f"**Source Story:** {story.source_story_id}",
            "",
            "# <Pending>",
        ])

        return "\n".join(lines)
