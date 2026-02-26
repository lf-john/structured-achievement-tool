"""Tests for src.github.pr_manager — Pull request management."""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.github.gh_cli import GHResult
from src.github.pr_manager import PRManager, PRResult


def _make_story(**overrides) -> dict:
    base = {
        "id": "US-015",
        "title": "Add user profile page",
        "description": "Create a user profile page with avatar and bio.",
        "type": "development",
        "complexity": 4,
        "acceptanceCriteria": ["Profile renders", "Avatar uploads work"],
    }
    base.update(overrides)
    return base


class TestPRManagerCreate:
    @patch("src.github.pr_manager.run_gh")
    def test_creates_pr_with_correct_title(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout="https://github.com/owner/repo/pull/7\n",
            success=True,
        )
        mgr = PRManager(repo="owner/repo")
        story = _make_story()

        result = mgr.create_pr(story, branch_name="task/US-015")

        assert result.success
        assert result.pr_number == 7
        assert result.pr_url == "https://github.com/owner/repo/pull/7"

        args = mock_gh.call_args[0][0]
        title_idx = args.index("--title") + 1
        assert "[US-015]" in args[title_idx]

    @patch("src.github.pr_manager.run_gh")
    def test_creates_pr_with_base_branch(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout="https://github.com/owner/repo/pull/1\n",
            success=True,
        )
        mgr = PRManager(repo="owner/repo")

        mgr.create_pr(_make_story(), branch_name="task/US-015", base_branch="develop")

        args = mock_gh.call_args[0][0]
        base_idx = args.index("--base") + 1
        assert args[base_idx] == "develop"

    @patch("src.github.pr_manager.run_gh")
    def test_creates_draft_pr(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout="https://github.com/owner/repo/pull/1\n",
            success=True,
        )
        mgr = PRManager(repo="owner/repo")

        mgr.create_pr(_make_story(), branch_name="task/US-015", draft=True)

        args = mock_gh.call_args[0][0]
        assert "--draft" in args

    @patch("src.github.pr_manager.run_gh")
    def test_pr_body_contains_story_info(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout="https://github.com/owner/repo/pull/1\n",
            success=True,
        )
        mgr = PRManager(repo="owner/repo")

        mgr.create_pr(_make_story(), branch_name="task/US-015")

        args = mock_gh.call_args[0][0]
        body_idx = args.index("--body") + 1
        body = args[body_idx]
        assert "US-015" in body
        assert "Acceptance Criteria" in body
        assert "Profile renders" in body

    @patch("src.github.pr_manager.run_gh")
    def test_pr_body_links_issue(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout="https://github.com/owner/repo/pull/1\n",
            success=True,
        )
        mgr = PRManager(repo="owner/repo")

        mgr.create_pr(_make_story(), branch_name="task/US-015", issue_number=42)

        args = mock_gh.call_args[0][0]
        body_idx = args.index("--body") + 1
        body = args[body_idx]
        assert "#42" in body

    @patch("src.github.pr_manager.run_gh")
    def test_failed_creation(self, mock_gh):
        mock_gh.return_value = GHResult(
            stderr="branch not found", success=False, exit_code=1,
        )
        mgr = PRManager(repo="owner/repo")

        result = mgr.create_pr(_make_story(), branch_name="task/US-015")

        assert not result.success
        assert "branch not found" in result.error


class TestPRManagerPush:
    @patch("subprocess.run")
    def test_push_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mgr = PRManager(repo="owner/repo")

        result = mgr.push_branch("task/US-015", "/tmp/repo")

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "push" in cmd
        assert "-u" in cmd
        assert "origin" in cmd

    @patch("subprocess.run")
    def test_push_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="rejected")
        mgr = PRManager(repo="owner/repo")

        result = mgr.push_branch("task/US-015", "/tmp/repo")

        assert result is False


class TestPRManagerFind:
    @patch("src.github.pr_manager.run_gh")
    def test_finds_existing_pr(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout='[{"number": 7}]', success=True,
        )
        mgr = PRManager(repo="owner/repo")

        result = mgr.find_pr_by_branch("task/US-015")
        assert result == 7

    @patch("src.github.pr_manager.run_gh")
    def test_no_pr_found(self, mock_gh):
        mock_gh.return_value = GHResult(stdout="[]", success=True)
        mgr = PRManager(repo="owner/repo")

        result = mgr.find_pr_by_branch("task/US-999")
        assert result is None


class TestPRManagerMerge:
    @patch("src.github.pr_manager.run_gh")
    def test_squash_merge(self, mock_gh):
        mock_gh.return_value = GHResult(success=True)
        mgr = PRManager(repo="owner/repo")

        result = mgr.merge_pr(7, merge_method="squash")

        assert result is True
        args = mock_gh.call_args[0][0]
        assert "--squash" in args
        assert "--delete-branch" in args

    @patch("src.github.pr_manager.run_gh")
    def test_merge_without_branch_delete(self, mock_gh):
        mock_gh.return_value = GHResult(success=True)
        mgr = PRManager(repo="owner/repo")

        mgr.merge_pr(7, delete_branch=False)

        args = mock_gh.call_args[0][0]
        assert "--delete-branch" not in args

    @patch("src.github.pr_manager.run_gh")
    def test_merge_failure(self, mock_gh):
        mock_gh.return_value = GHResult(success=False, stderr="conflicts")
        mgr = PRManager(repo="owner/repo")

        result = mgr.merge_pr(7)
        assert result is False


class TestPRManagerStatus:
    @patch("src.github.pr_manager.run_gh")
    def test_get_status(self, mock_gh):
        mock_gh.return_value = GHResult(
            stdout='{"state": "OPEN", "mergeable": "MERGEABLE", "number": 7}',
            success=True,
        )
        mgr = PRManager(repo="owner/repo")

        status = mgr.get_pr_status(7)
        assert status is not None
        assert status["state"] == "OPEN"
        assert status["mergeable"] == "MERGEABLE"

    @patch("src.github.pr_manager.run_gh")
    def test_status_not_found(self, mock_gh):
        mock_gh.return_value = GHResult(success=False)
        mgr = PRManager(repo="owner/repo")

        status = mgr.get_pr_status(999)
        assert status is None


class TestPRManagerComments:
    @patch("src.github.pr_manager.run_gh")
    def test_add_comment(self, mock_gh):
        mock_gh.return_value = GHResult(success=True)
        mgr = PRManager(repo="owner/repo")

        result = mgr.add_pr_comment(7, "Tests passing!")
        assert result is True
