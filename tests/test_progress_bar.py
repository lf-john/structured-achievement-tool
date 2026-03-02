"""Tests for the ntfy progress bar in Notifier."""

import pytest
from unittest.mock import patch, MagicMock

from src.notifications.notifier import Notifier


class TestProgressBar:
    @patch("src.notifications.notifier.requests.post")
    def test_sends_progress(self, mock_post):
        mock_post.return_value.status_code = 200
        notifier = Notifier(ntfy_topic="test", config={})
        result = notifier.send_progress("task-1", 3, 10, "US-003", "CODE")
        assert result is True
        mock_post.assert_called_once()

    @patch("src.notifications.notifier.requests.post")
    def test_progress_bar_format(self, mock_post):
        mock_post.return_value.status_code = 200
        notifier = Notifier(ntfy_topic="test", config={})
        notifier.send_progress("task-1", 5, 10, "US-005", "VERIFY")

        call_data = mock_post.call_args[1].get("data", b"") if mock_post.call_args[1] else mock_post.call_args.kwargs.get("data", b"")
        message = call_data.decode() if isinstance(call_data, bytes) else call_data
        assert "█" in message
        assert "░" in message
        assert "5/10" in message

    @patch("src.notifications.notifier.requests.post")
    def test_progress_complete(self, mock_post):
        mock_post.return_value.status_code = 200
        notifier = Notifier(ntfy_topic="test", config={})
        notifier.send_progress("task-1", 10, 10)

        call_headers = mock_post.call_args[1].get("headers", {}) if mock_post.call_args[1] else mock_post.call_args.kwargs.get("headers", {})
        assert "10/10" in call_headers.get("Title", "")

    @patch("src.notifications.notifier.requests.post")
    def test_zero_total_returns_false(self, mock_post):
        notifier = Notifier(ntfy_topic="test", config={})
        result = notifier.send_progress("task-1", 0, 0)
        assert result is False
        mock_post.assert_not_called()

    @patch("src.notifications.notifier.requests.post")
    def test_includes_current_story(self, mock_post):
        mock_post.return_value.status_code = 200
        notifier = Notifier(ntfy_topic="test", config={})
        notifier.send_progress("task-1", 3, 10, "Configure DNS", "EXECUTE")

        call_data = mock_post.call_args[1].get("data", b"") if mock_post.call_args[1] else mock_post.call_args.kwargs.get("data", b"")
        message = call_data.decode() if isinstance(call_data, bytes) else call_data
        assert "Configure DNS" in message
        assert "EXECUTE" in message
