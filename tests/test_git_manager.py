"""Tests for src.execution.git_manager — Git operations."""

import os
import subprocess

import pytest

from src.execution.git_manager import (
    _run_git,
    auto_commit,
    create_worktree,
    get_current_commit,
    get_diff,
    get_modified_files,
    reset_to_commit,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    # Create initial commit
    (tmp_path / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)
    return tmp_path


class TestRunGit:
    def test_successful_command(self, git_repo):
        result = _run_git(["status"], str(git_repo))
        assert result.returncode == 0

    def test_invalid_command(self, git_repo):
        result = _run_git(["invalid-command"], str(git_repo))
        assert result.returncode != 0


class TestGetCurrentCommit:
    def test_returns_hash(self, git_repo):
        commit = get_current_commit(str(git_repo))
        assert commit is not None
        assert len(commit) == 40  # Full SHA

    def test_returns_none_for_non_repo(self, tmp_path):
        commit = get_current_commit(str(tmp_path))
        assert commit is None


class TestAutoCommit:
    def test_commits_changes(self, git_repo):
        # Create a new file
        (git_repo / "new_file.py").write_text("print('hello')")
        commit_hash = auto_commit(str(git_repo), "US-001", "CODE")
        assert commit_hash is not None
        assert len(commit_hash) == 40

    def test_no_changes_returns_none(self, git_repo):
        commit_hash = auto_commit(str(git_repo), "US-001", "CODE")
        assert commit_hash is None

    def test_commit_message_format(self, git_repo):
        (git_repo / "file.py").write_text("x = 1")
        auto_commit(str(git_repo), "US-001", "CODE")
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"], cwd=git_repo, capture_output=True, text=True
        )
        assert "US-001" in result.stdout
        assert "CODE" in result.stdout


class TestResetToCommit:
    def test_reset_removes_changes(self, git_repo):
        base = get_current_commit(str(git_repo))

        # Add new file and commit
        (git_repo / "extra.py").write_text("extra")
        auto_commit(str(git_repo), "US-001", "CODE")

        # Reset
        success = reset_to_commit(str(git_repo), base)
        assert success
        assert not (git_repo / "extra.py").exists()


class TestGetDiff:
    def test_shows_changes(self, git_repo):
        (git_repo / "file.py").write_text("new content")
        auto_commit(str(git_repo), "US-001", "CODE")
        diff = get_diff(str(git_repo))
        assert "new content" in diff

    def test_empty_diff_no_changes(self, git_repo):
        # Make two commits so HEAD~1 exists
        (git_repo / "a.py").write_text("a")
        auto_commit(str(git_repo), "US-001", "A")
        diff = get_diff(str(git_repo), against="HEAD")
        assert diff == ""


class TestGetModifiedFiles:
    def test_lists_modified(self, git_repo):
        (git_repo / "changed.py").write_text("changed")
        auto_commit(str(git_repo), "US-001", "CODE")
        files = get_modified_files(str(git_repo))
        assert "changed.py" in files


class TestCreateWorktree:
    def test_existing_path_returns_existed(self, git_repo):
        worktree_path = os.path.join(str(git_repo), "worktrees", "test-task")
        os.makedirs(worktree_path, exist_ok=True)
        info = create_worktree(str(git_repo), "test-task")
        assert info.success
        assert info.existed
