"""Tests for src.github.gh_cli — GitHub CLI wrapper."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.github.gh_cli import GHResult, check_auth, get_repo_from_remote, run_gh


class TestGHResult:
    def test_success_result(self):
        r = GHResult(stdout="ok", exit_code=0, success=True)
        assert r.success
        assert r.exit_code == 0

    def test_json_parse(self):
        r = GHResult(stdout='{"number": 42}', success=True)
        assert r.json == {"number": 42}

    def test_json_empty(self):
        r = GHResult(stdout="", success=True)
        assert r.json == {}

    def test_json_parse_error(self):
        r = GHResult(stdout="not json", success=True)
        with pytest.raises(json.JSONDecodeError):
            r.json


class TestRunGH:
    @patch("src.github.gh_cli.subprocess.run")
    def test_successful_command(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="output", stderr="", returncode=0
        )
        result = run_gh(["issue", "list"])
        assert result.success
        assert result.stdout == "output"
        mock_run.assert_called_once()

    @patch("src.github.gh_cli.subprocess.run")
    def test_failed_command(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="", stderr="error msg", returncode=1
        )
        result = run_gh(["issue", "create"])
        assert not result.success
        assert result.exit_code == 1
        assert "error msg" in result.stderr

    @patch("src.github.gh_cli.subprocess.run")
    def test_repo_flag_added(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        run_gh(["issue", "list"], repo="owner/repo")
        cmd = mock_run.call_args[0][0]
        assert "--repo" in cmd
        assert "owner/repo" in cmd

    @patch("src.github.gh_cli.subprocess.run")
    def test_timeout_handling(self, mock_run):
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired(cmd="gh", timeout=30)
        result = run_gh(["issue", "list"])
        assert not result.success
        assert result.exit_code == -1
        assert "Timeout" in result.stderr

    @patch("src.github.gh_cli.subprocess.run")
    def test_gh_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = run_gh(["issue", "list"])
        assert not result.success
        assert "not found" in result.stderr

    @patch("src.github.gh_cli.subprocess.run")
    def test_cwd_passed_through(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        run_gh(["issue", "list"], cwd="/tmp/myrepo")
        assert mock_run.call_args[1]["cwd"] == "/tmp/myrepo"


class TestCheckAuth:
    @patch("src.github.gh_cli.run_gh")
    def test_authenticated(self, mock_run):
        mock_run.return_value = GHResult(success=True)
        assert check_auth() is True

    @patch("src.github.gh_cli.run_gh")
    def test_not_authenticated(self, mock_run):
        mock_run.return_value = GHResult(success=False)
        assert check_auth() is False


class TestGetRepoFromRemote:
    @patch("src.github.gh_cli.subprocess.run")
    def test_ssh_url(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="git@github.com:lf-john/sat.git\n", returncode=0
        )
        assert get_repo_from_remote() == "lf-john/sat"

    @patch("src.github.gh_cli.subprocess.run")
    def test_https_url(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="https://github.com/lf-john/sat.git\n", returncode=0
        )
        assert get_repo_from_remote() == "lf-john/sat"

    @patch("src.github.gh_cli.subprocess.run")
    def test_no_remote(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        assert get_repo_from_remote() is None

    @patch("src.github.gh_cli.subprocess.run")
    def test_ssh_url_no_git_suffix(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="git@github.com:owner/repo\n", returncode=0
        )
        assert get_repo_from_remote() == "owner/repo"
