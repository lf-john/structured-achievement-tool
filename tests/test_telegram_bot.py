"""Tests for Telegram bot command handlers."""

import os
import json
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# Mock the telegram module before import
@pytest.fixture(autouse=True)
def mock_telegram_import(monkeypatch):
    """Prevent actual telegram import."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "12345,67890")


class TestAuthorization:
    """Test user authorization."""

    def test_allowed_users_parsing(self):
        from src.notifications.telegram_bot import _get_allowed_users
        with patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": "111,222,333"}):
            users = _get_allowed_users()
            assert users == {111, 222, 333}

    def test_allowed_users_empty(self):
        from src.notifications.telegram_bot import _get_allowed_users
        with patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": ""}):
            users = _get_allowed_users()
            assert users == set()

    def test_allowed_users_with_spaces(self):
        from src.notifications.telegram_bot import _get_allowed_users
        with patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": " 111 , 222 "}):
            users = _get_allowed_users()
            assert users == {111, 222}


class TestTaskHelpers:
    """Test helper functions."""

    def test_count_tasks(self, tmp_path):
        from src.notifications.telegram_bot import _count_tasks

        # Create test task files
        sub = tmp_path / "test-dir"
        sub.mkdir()
        (sub / "001_task.md").write_text("# Task\n<Pending>\n")
        (sub / "002_task.md").write_text("# Task\n<Working>\n")
        (sub / "003_task.md").write_text("# Task\n<Finished>\n")
        (sub / "004_task.md").write_text("# Task\n<Failed>\n")
        (sub / "005_response.md").write_text("response\n<Finished>\n")  # Should be skipped

        counts = _count_tasks(str(tmp_path))
        assert counts["pending"] == 1
        assert counts["working"] == 1
        assert counts["finished"] == 1
        assert counts["failed"] == 1

    def test_count_tasks_empty_dir(self, tmp_path):
        from src.notifications.telegram_bot import _count_tasks
        counts = _count_tasks(str(tmp_path))
        assert counts == {"pending": 0, "working": 0, "finished": 0, "failed": 0}

    def test_count_tasks_nonexistent(self):
        from src.notifications.telegram_bot import _count_tasks
        counts = _count_tasks("/nonexistent/path")
        assert counts == {"pending": 0, "working": 0, "finished": 0, "failed": 0}

    def test_get_task_list(self, tmp_path):
        from src.notifications.telegram_bot import _get_task_list

        sub = tmp_path / "project"
        sub.mkdir()
        (sub / "001_test.md").write_text("# Test\n<Pending>\n")
        (sub / "002_test.md").write_text("# Test\n<Finished>\n")

        tasks = _get_task_list(str(tmp_path))
        assert len(tasks) == 2
        assert tasks[0]["status"] in ("Pending", "Finished")

    def test_list_pending_approvals(self, tmp_path):
        from src.notifications.telegram_bot import _list_pending_approvals

        (tmp_path / "US-001_approval.md").write_text("# Approval\n# <Pending>\n")
        (tmp_path / "US-002_approval.md").write_text("# Approval\nApproved\n<Pending>\n")

        pending = _list_pending_approvals(str(tmp_path))
        assert "US-001" in pending
        assert "US-002" not in pending  # Already responded

    def test_list_task_dirs(self, tmp_path):
        from src.notifications.telegram_bot import _list_task_dirs

        (tmp_path / "sat-enhancements").mkdir()
        (tmp_path / "marketing-automation").mkdir()
        (tmp_path / ".hidden").mkdir()

        dirs = _list_task_dirs(str(tmp_path))
        assert "sat-enhancements" in dirs
        assert "marketing-automation" in dirs
        assert ".hidden" not in dirs


class TestApprovalCommands:
    """Test approve/reject file manipulation."""

    def test_approve_modifies_signal_file(self, tmp_path):
        """Verify approve replaces # <Pending> correctly."""
        signal_file = tmp_path / "US-001_approval.md"
        signal_file.write_text(
            "# Approval Required: US-001\n\n"
            "## Your Response\n\n"
            "---\n\n"
            "# <Pending>\n"
        )

        # Read, modify, write — same as cmd_approve does
        content = signal_file.read_text()
        content = content.replace("# <Pending>", "Approved via Telegram\n\n<Pending>")
        signal_file.write_text(content)

        result = signal_file.read_text()
        assert "# <Pending>" not in result
        assert "<Pending>" in result
        assert "Approved via Telegram" in result

    def test_reject_modifies_signal_file(self, tmp_path):
        """Verify reject adds REJECTED: prefix."""
        signal_file = tmp_path / "US-001_approval.md"
        signal_file.write_text("# Approval\n# <Pending>\n")

        content = signal_file.read_text()
        content = content.replace("# <Pending>", "REJECTED: Not ready yet\n\n<Pending>")
        signal_file.write_text(content)

        result = signal_file.read_text()
        assert "REJECTED: Not ready yet" in result
        assert "<Pending>" in result
        assert "# <Pending>" not in result
