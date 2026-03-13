"""Tests for src.github.feedback_handler — PR review → follow-up stories."""

import json
import os
from unittest.mock import patch

from src.github.feedback_handler import (
    FeedbackHandler,
    FollowUpStory,
    ReviewComment,
)
from src.github.gh_cli import GHResult


class TestGetReviewComments:
    @patch("src.github.feedback_handler.run_gh")
    def test_fetches_inline_comments(self, mock_gh):
        inline_data = json.dumps(
            [
                {"body": "Fix this", "user": {"login": "reviewer1"}, "path": "src/auth.py", "line": 42},
                {"body": "Add tests", "user": {"login": "reviewer2"}, "path": "src/auth.py", "line": 50},
            ]
        )
        # First call: inline comments, second: reviews
        mock_gh.side_effect = [
            GHResult(stdout=inline_data, success=True),
            GHResult(stdout="[]", success=True),
        ]
        handler = FeedbackHandler(repo="owner/repo")

        comments = handler.get_review_comments(7)

        assert len(comments) == 2
        assert comments[0].body == "Fix this"
        assert comments[0].path == "src/auth.py"
        assert comments[0].line == 42
        assert comments[0].comment_type == "inline"

    @patch("src.github.feedback_handler.run_gh")
    def test_fetches_general_review_comments(self, mock_gh):
        review_data = json.dumps(
            [
                {"body": "Overall looks good but needs refactoring", "user": {"login": "lead"}},
                {"body": "", "user": {"login": "lead"}},  # Empty body, should be skipped
            ]
        )
        mock_gh.side_effect = [
            GHResult(stdout="[]", success=True),  # inline
            GHResult(stdout=review_data, success=True),  # reviews
        ]
        handler = FeedbackHandler(repo="owner/repo")

        comments = handler.get_review_comments(7)

        assert len(comments) == 1
        assert comments[0].comment_type == "review"
        assert "refactoring" in comments[0].body

    @patch("src.github.feedback_handler.run_gh")
    def test_empty_pr_returns_empty_list(self, mock_gh):
        mock_gh.return_value = GHResult(stdout="[]", success=True)
        handler = FeedbackHandler(repo="owner/repo")

        comments = handler.get_review_comments(7)
        assert comments == []

    @patch("src.github.feedback_handler.run_gh")
    def test_api_failure_returns_empty(self, mock_gh):
        mock_gh.return_value = GHResult(stdout="", success=False)
        handler = FeedbackHandler(repo="owner/repo")

        comments = handler.get_review_comments(7)
        assert comments == []


class TestGenerateFollowUpStories:
    def test_groups_by_file(self):
        handler = FeedbackHandler(repo="owner/repo")
        comments = [
            ReviewComment(body="Fix null check", author="r1", path="src/auth.py", line=10, comment_type="inline"),
            ReviewComment(body="Add validation", author="r1", path="src/auth.py", line=20, comment_type="inline"),
            ReviewComment(body="Rename variable", author="r2", path="src/utils.py", line=5, comment_type="inline"),
        ]

        stories = handler.generate_follow_up_stories(
            pr_number=7,
            source_story_id="US-015",
            task_name="sat-test",
            comments=comments,
        )

        # 2 files → 2 stories
        assert len(stories) == 2
        auth_story = next(s for s in stories if "auth" in s.title)
        assert "Fix null check" in auth_story.description
        assert "Add validation" in auth_story.description

    def test_general_comments_create_separate_stories(self):
        handler = FeedbackHandler(repo="owner/repo")
        comments = [
            ReviewComment(body="Please add documentation", author="r1", comment_type="review"),
            ReviewComment(body="Security concern with tokens", author="r2", comment_type="review"),
        ]

        stories = handler.generate_follow_up_stories(
            pr_number=7,
            source_story_id="US-015",
            task_name="sat-test",
            comments=comments,
        )

        assert len(stories) == 2

    def test_story_id_format(self):
        handler = FeedbackHandler(repo="owner/repo")
        comments = [
            ReviewComment(body="Fix this", author="r1", path="file.py", comment_type="inline"),
        ]

        stories = handler.generate_follow_up_stories(
            pr_number=7,
            source_story_id="US-015",
            task_name="test",
            comments=comments,
        )

        assert stories[0].story_id == "US-015-fb1"

    def test_no_comments_returns_empty(self):
        handler = FeedbackHandler(repo="owner/repo")

        stories = handler.generate_follow_up_stories(
            pr_number=7,
            source_story_id="US-015",
            task_name="test",
            comments=[],
        )

        assert stories == []

    def test_classifies_bug_feedback(self):
        handler = FeedbackHandler(repo="owner/repo")
        comments = [
            ReviewComment(body="This is a bug, it crashes on null input", author="r1", comment_type="review"),
        ]

        stories = handler.generate_follow_up_stories(
            pr_number=7,
            source_story_id="US-015",
            task_name="test",
            comments=comments,
        )

        assert stories[0].story_type == "debug"

    def test_classifies_refactor_feedback(self):
        handler = FeedbackHandler(repo="owner/repo")
        comments = [
            ReviewComment(body="Please refactor this into smaller functions", author="r1", comment_type="review"),
        ]

        stories = handler.generate_follow_up_stories(
            pr_number=7,
            source_story_id="US-015",
            task_name="test",
            comments=comments,
        )

        assert stories[0].story_type == "maintenance"

    def test_default_type_is_development(self):
        handler = FeedbackHandler(repo="owner/repo")
        comments = [
            ReviewComment(body="Add pagination support", author="r1", comment_type="review"),
        ]

        stories = handler.generate_follow_up_stories(
            pr_number=7,
            source_story_id="US-015",
            task_name="test",
            comments=comments,
        )

        assert stories[0].story_type == "development"

    def test_acceptance_criteria_generated(self):
        handler = FeedbackHandler(repo="owner/repo")
        comments = [
            ReviewComment(body="Fix this", author="r1", path="src/auth.py", line=10, comment_type="inline"),
        ]

        stories = handler.generate_follow_up_stories(
            pr_number=7,
            source_story_id="US-015",
            task_name="test",
            comments=comments,
        )

        criteria = stories[0].acceptance_criteria
        assert any("PR #7" in c for c in criteria)
        assert any("auth.py" in c for c in criteria)


class TestWriteStoryFiles:
    def test_writes_files_to_directory(self, tmp_path):
        handler = FeedbackHandler(repo="owner/repo")
        stories = [
            FollowUpStory(
                story_id="US-015-fb1",
                title="Fix auth issue",
                description="Review feedback from PR #7",
                story_type="debug",
                source_pr=7,
                source_story_id="US-015",
                acceptance_criteria=["Fix the auth bug"],
            ),
        ]

        files = handler.write_story_files(stories, str(tmp_path))

        assert len(files) == 1
        assert os.path.exists(files[0])
        content = open(files[0]).read()
        assert "Fix auth issue" in content
        assert "# <Pending>" in content
        assert "debug" in content

    def test_writes_multiple_files(self, tmp_path):
        handler = FeedbackHandler(repo="owner/repo")
        stories = [
            FollowUpStory(
                story_id=f"US-015-fb{i}",
                title=f"Fix issue {i}",
                description=f"Feedback {i}",
                story_type="development",
                source_pr=7,
                source_story_id="US-015",
                acceptance_criteria=[f"Fix {i}"],
            )
            for i in range(1, 4)
        ]

        files = handler.write_story_files(stories, str(tmp_path))

        assert len(files) == 3
        for f in files:
            assert os.path.exists(f)

    def test_creates_output_directory(self, tmp_path):
        handler = FeedbackHandler(repo="owner/repo")
        output_dir = str(tmp_path / "nested" / "dir")
        stories = [
            FollowUpStory(
                story_id="US-015-fb1",
                title="Test",
                description="Test",
                story_type="development",
                source_pr=7,
                source_story_id="US-015",
                acceptance_criteria=["Test"],
            ),
        ]

        files = handler.write_story_files(stories, output_dir)

        assert len(files) == 1
        assert os.path.exists(output_dir)

    def test_file_content_has_pending_tag(self, tmp_path):
        handler = FeedbackHandler(repo="owner/repo")
        stories = [
            FollowUpStory(
                story_id="US-015-fb1",
                title="Test story",
                description="Description here",
                story_type="development",
                source_pr=7,
                source_story_id="US-015",
                acceptance_criteria=["Criterion 1", "Criterion 2"],
            ),
        ]

        files = handler.write_story_files(stories, str(tmp_path))
        content = open(files[0]).read()

        # Should end with # <Pending> for daemon pickup
        assert content.strip().endswith("# <Pending>")
        assert "#7" in content
        assert "US-015" in content
