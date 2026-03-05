"""Tests for src.github.issue_manager — Story ↔ GitHub Issue mapping."""

from unittest.mock import patch

from src.github.gh_cli import GHResult
from src.github.issue_manager import (
    STATUS_LABELS,
    STORY_TYPE_LABELS,
    IssueManager,
)


def _make_story(**overrides) -> dict:
    base = {
        "id": "US-010",
        "title": "Add login page",
        "description": "Implement the login page with email/password.",
        "type": "development",
        "complexity": 5,
        "acceptanceCriteria": ["Login form renders", "Invalid credentials show error"],
        "dependsOn": ["US-009"],
    }
    base.update(overrides)
    return base


class TestIssueManagerCreate:
    @patch("src.github.issue_manager.run_gh")
    def test_creates_issue_with_correct_title(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout="https://github.com/owner/repo/issues/42\n",
            success=True,
        )
        mgr = IssueManager(repo="owner/repo")
        story = _make_story()

        result = mgr.create_issue(story, task_name="sat-enhancements")

        assert result.success
        assert result.issue_number == 42
        assert result.issue_url == "https://github.com/owner/repo/issues/42"

        # Check title format
        create_call = [c for c in mock_gh.call_args_list if c[0][0][0:2] == ["issue", "create"]]
        assert len(create_call) >= 1
        args = create_call[0][0][0]
        title_idx = args.index("--title") + 1
        assert "[US-010]" in args[title_idx]
        assert "Add login page" in args[title_idx]

    @patch("src.github.issue_manager.run_gh")
    def test_creates_issue_with_labels(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout="https://github.com/owner/repo/issues/1\n",
            success=True,
        )
        mgr = IssueManager(repo="owner/repo")
        story = _make_story(type="debug")

        mgr.create_issue(story, task_name="fix-bugs")

        create_calls = [c for c in mock_gh.call_args_list if "issue" in str(c) and "create" in str(c)]
        assert len(create_calls) >= 1
        args = create_calls[0][0][0]
        label_idx = args.index("--label") + 1
        assert "type:debug" in args[label_idx]
        assert "status:pending" in args[label_idx]

    @patch("src.github.issue_manager.run_gh")
    def test_failed_creation_returns_error(self, mock_gh):
        mock_gh.return_value = GHResult(
            stderr="permission denied", success=False, exit_code=1,
        )
        mgr = IssueManager(repo="owner/repo")
        story = _make_story()

        result = mgr.create_issue(story, task_name="test")

        assert not result.success
        assert "permission denied" in result.error

    @patch("src.github.issue_manager.run_gh")
    def test_issue_body_contains_story_id(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout="https://github.com/owner/repo/issues/5\n",
            success=True,
        )
        mgr = IssueManager(repo="owner/repo")
        story = _make_story()

        mgr.create_issue(story, task_name="test")

        create_calls = [c for c in mock_gh.call_args_list if "issue" in str(c) and "create" in str(c)]
        args = create_calls[0][0][0]
        body_idx = args.index("--body") + 1
        body = args[body_idx]
        assert "US-010" in body
        assert "Acceptance Criteria" in body
        assert "Login form renders" in body

    @patch("src.github.issue_manager.run_gh")
    def test_issue_body_contains_dependencies(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout="https://github.com/owner/repo/issues/5\n",
            success=True,
        )
        mgr = IssueManager(repo="owner/repo")
        story = _make_story()

        mgr.create_issue(story, task_name="test")

        create_calls = [c for c in mock_gh.call_args_list if "issue" in str(c) and "create" in str(c)]
        args = create_calls[0][0][0]
        body_idx = args.index("--body") + 1
        body = args[body_idx]
        assert "US-009" in body


class TestIssueManagerUpdateStatus:
    @patch("src.github.issue_manager.run_gh")
    def test_updates_status_label(self, mock_gh):
        mock_gh.return_value = GHResult(success=True)
        mgr = IssueManager(repo="owner/repo")

        result = mgr.update_status(42, "working")

        assert result is True
        # Should have called add-label with status:working
        add_calls = [c for c in mock_gh.call_args_list
                     if "--add-label" in str(c) and "status:working" in str(c)]
        assert len(add_calls) >= 1

    @patch("src.github.issue_manager.run_gh")
    def test_closes_on_complete(self, mock_gh):
        mock_gh.return_value = GHResult(success=True)
        mgr = IssueManager(repo="owner/repo")

        mgr.update_status(42, "complete")

        close_calls = [c for c in mock_gh.call_args_list
                       if "close" in str(c)]
        assert len(close_calls) >= 1

    @patch("src.github.issue_manager.run_gh")
    def test_invalid_status_defaults_to_pending(self, mock_gh):
        mock_gh.return_value = GHResult(success=True)
        mgr = IssueManager(repo="owner/repo")

        mgr.update_status(42, "invalid_status")

        add_calls = [c for c in mock_gh.call_args_list
                     if "--add-label" in str(c) and "status:pending" in str(c)]
        assert len(add_calls) >= 1


class TestIssueManagerFind:
    @patch("src.github.issue_manager.run_gh")
    def test_finds_existing_issue(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout='[{"number": 42}]', success=True,
        )
        mgr = IssueManager(repo="owner/repo")

        result = mgr.find_issue_by_story_id("US-010")
        assert result == 42

    @patch("src.github.issue_manager.run_gh")
    def test_returns_none_when_not_found(self, mock_gh):
        mock_gh.return_value = GHResult(stdout="[]", success=True)
        mgr = IssueManager(repo="owner/repo")

        result = mgr.find_issue_by_story_id("US-999")
        assert result is None


class TestIssueManagerComment:
    @patch("src.github.issue_manager.run_gh")
    def test_adds_comment(self, mock_gh):
        mock_gh.return_value = GHResult(success=True)
        mgr = IssueManager(repo="owner/repo")

        result = mgr.add_comment(42, "Story completed successfully.")
        assert result is True

    @patch("src.github.issue_manager.run_gh")
    def test_comment_failure(self, mock_gh):
        mock_gh.return_value = GHResult(success=False)
        mgr = IssueManager(repo="owner/repo")

        result = mgr.add_comment(42, "test")
        assert result is False


class TestStoryTypeLabels:
    def test_all_types_have_labels(self):
        expected_types = {"development", "config", "maintenance", "debug", "research", "review"}
        assert set(STORY_TYPE_LABELS.keys()) == expected_types

    def test_all_labels_have_prefix(self):
        for label in STORY_TYPE_LABELS.values():
            assert label.startswith("type:")

    def test_all_status_labels_have_prefix(self):
        for label in STATUS_LABELS.values():
            assert label.startswith("status:")
