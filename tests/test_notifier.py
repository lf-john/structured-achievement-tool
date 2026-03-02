"""Tests for src.notifications.notifier — notification service."""

import pytest
from unittest.mock import patch, MagicMock

from src.notifications.notifier import Notifier


class TestSendEmail:
    @patch("src.notifications.notifier.smtplib.SMTP")
    def test_sends_to_default_recipient(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        notifier = Notifier(
            smtp_host="smtp.example.com",
            smtp_user="sat@example.com",
            smtp_password="secret",
            notify_email="admin@example.com",
        )
        result = notifier.send_email("Subject", "<p>Body</p>")
        assert result is True
        mock_server.sendmail.assert_called_once()
        args = mock_server.sendmail.call_args[0]
        assert args[1] == "admin@example.com"

    @patch("src.notifications.notifier.smtplib.SMTP")
    def test_sends_to_override_recipient(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        notifier = Notifier(
            smtp_host="smtp.example.com",
            smtp_user="sat@example.com",
            smtp_password="secret",
            notify_email="admin@example.com",
        )
        result = notifier.send_email("Subject", "<p>Body</p>", recipient="other@example.com")
        assert result is True
        args = mock_server.sendmail.call_args[0]
        assert args[1] == "other@example.com"

    def test_skips_when_no_smtp(self):
        notifier = Notifier()
        result = notifier.send_email("Subject", "<p>Body</p>")
        assert result is False


class TestSendNtfy:
    @patch("src.notifications.notifier.requests.post")
    def test_sends_notification(self, mock_post):
        mock_post.return_value.status_code = 200
        notifier = Notifier(ntfy_topic="test-topic", config={})
        result = notifier.send_ntfy("Title", "Message")
        assert result is True
        mock_post.assert_called_once()

    @patch("src.notifications.notifier.requests.post")
    def test_returns_false_on_failure(self, mock_post):
        mock_post.side_effect = Exception("Network error")
        notifier = Notifier(ntfy_topic="test-topic", config={})
        result = notifier.send_ntfy("Title", "Message")
        assert result is False


class TestHumanNotificationHelpers:
    @patch("src.notifications.notifier.requests.post")
    def test_notify_human_action_required(self, mock_post):
        mock_post.return_value.status_code = 200
        notifier = Notifier(ntfy_topic="test", config={})
        notifier.notify_human_action_required(
            "US-050", "Configure DNS", "assignment", "/path/to/signal"
        )
        mock_post.assert_called_once()
        call_headers = mock_post.call_args[1].get("headers", {}) if mock_post.call_args[1] else mock_post.call_args.kwargs.get("headers", {})
        assert "Assignment" in call_headers.get("Title", "")

    @patch("src.notifications.notifier.requests.post")
    def test_notify_human_response_received(self, mock_post):
        mock_post.return_value.status_code = 200
        notifier = Notifier(ntfy_topic="test", config={})
        notifier.notify_human_response_received("US-050", "assignment")
        mock_post.assert_called_once()

    @patch("src.notifications.notifier.requests.post")
    def test_notify_escalation_sends_ntfy(self, mock_post):
        mock_post.return_value.status_code = 200
        notifier = Notifier(ntfy_topic="test", config={})
        notifier.notify_escalation("US-050", "DNS Config", "ImportError")
        mock_post.assert_called_once()

    @patch("src.notifications.notifier.smtplib.SMTP")
    @patch("src.notifications.notifier.requests.post")
    def test_notify_escalation_sends_email(self, mock_post, mock_smtp):
        mock_post.return_value.status_code = 200
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        notifier = Notifier(
            ntfy_topic="test",
            smtp_host="smtp.example.com",
            smtp_user="sat@example.com",
            smtp_password="secret",
            notify_email="admin@example.com",
        )
        notifier.notify_escalation(
            "US-050", "DNS Config", "ImportError",
            recipient="ops@example.com",
        )
        mock_server.sendmail.assert_called_once()
        args = mock_server.sendmail.call_args[0]
        assert args[1] == "ops@example.com"
