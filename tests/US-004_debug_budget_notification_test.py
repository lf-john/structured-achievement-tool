
"""
IMPLEMENTATION PLAN for US-004:

Components:
  - Notifier (class in src/notifications/notifier.py):
    - notify_debug_budget_exhausted(self, task_id: str, attempts: int, last_error_summary: str): New method to send the specific budget exhaustion notification.

Test Cases:
  1. [AC 1] -> test_notification_triggered_on_budget_exhaustion: Verifies that a call to notify_debug_budget_exhausted triggers the underlying ntfy send mechanism.
  2. [AC 2] -> test_notification_uses_correct_ntfy_topic: Ensures the ntfy notification is sent to the 'johnlane-claude-tasks' topic.
  3. [AC 3] -> test_notification_message_content: Checks that the notification message contains the task name, attempts made, and the last error summary.
  4. [AC 4] -> test_notification_triggered_on_budget_exhaustion, test_notification_uses_correct_ntfy_topic, test_notification_message_content: These tests collectively confirm trigger and content accuracy.

Edge Cases:
  - test_notification_with_empty_error_summary: Ensures the notification handles an empty string for the last error summary gracefully.
  - test_notification_failure_is_logged: Verifies that a warning is logged if the ntfy API call fails.
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock
import logging

# Assume Notifier will be in src/notifications/notifier.py
# This import will fail as the method does not exist, leading to a TDD-RED state.
from src.notifications.notifier import Notifier

class TestDebugBudgetNotification:
    @pytest.fixture
    def mock_requests_post(self):
        """Mocks requests.post to capture calls without actually sending data."""
        with patch("src.notifications.notifier.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            yield mock_post

    @pytest.fixture
    def mock_notifier(self, mock_requests_post):
        """Provides a Notifier instance with a mocked requests.post."""
        # Ensure NTFY_TOPIC is set for consistent testing
        os.environ["NTFY_TOPIC"] = "johnlane-claude-tasks"
        notifier = Notifier()
        yield notifier
        del os.environ["NTFY_TOPIC"] # Clean up

    def test_notification_triggered_on_budget_exhaustion(self, mock_notifier, mock_requests_post):
        """
        Verifies that calling notify_debug_budget_exhausted triggers an ntfy notification.
        """
        task_id = "test-task-1"
        attempts = 4
        last_error = "Mock error message"

        mock_notifier.notify_debug_budget_exhausted(task_id, attempts, last_error)

        mock_requests_post.assert_called_once()

    def test_notification_uses_correct_ntfy_topic(self, mock_notifier, mock_requests_post):
        """
        Ensures the ntfy notification is sent to the 'johnlane-claude-tasks' topic.
        """
        task_id = "test-task-2"
        attempts = 5
        last_error = "Another mock error"

        mock_notifier.notify_debug_budget_exhausted(task_id, attempts, last_error)

        expected_url = f"{mock_notifier.ntfy_server}/johnlane-claude-tasks"
        mock_requests_post.assert_called_once_with(
            expected_url,
            data=MagicMock(), # Data is checked in content test
            headers=MagicMock(), # Headers are checked in content test
            timeout=5
        )

    def test_notification_message_content(self, mock_notifier, mock_requests_post):
        """
        Checks that the notification message contains the task name, attempts made,
        and the last error summary.
        """
        task_id = "test-task-3"
        attempts = 3
        last_error = "Final attempt failed due to memory leak."

        mock_notifier.notify_debug_budget_exhausted(task_id, attempts, last_error)

        call_args, call_kwargs = mock_requests_post.call_args
        message_data = call_kwargs['data'].decode('utf-8')
        headers = call_kwargs['headers']

        assert f"Task: {task_id}" in message_data
        assert f"Attempts: {attempts}" in message_data
        assert f"Last Error: {last_error}" in message_data
        assert headers["Title"] == f"SAT: Debug Budget Exhausted ({task_id})"
        assert headers["Priority"] == "urgent"
        assert "warning" in headers["Tags"]

    def test_notification_with_empty_error_summary(self, mock_notifier, mock_requests_post):
        """
        Ensures the notification handles an empty string for the last error summary gracefully.
        """
        task_id = "test-task-4"
        attempts = 1
        last_error = ""

        mock_notifier.notify_debug_budget_exhausted(task_id, attempts, last_error)

        call_args, call_kwargs = mock_requests_post.call_args
        message_data = call_kwargs['data'].decode('utf-8')

        assert f"Task: {task_id}" in message_data
        assert f"Attempts: {attempts}" in message_data
        assert "Last Error: (No summary provided)" in message_data # Expected default text

    def test_notification_failure_is_logged(self, mock_notifier, mock_requests_post):
        """
        Verifies that a warning is logged if the ntfy API call fails.
        """
        mock_requests_post.side_effect = Exception("Network error")
        task_id = "test-task-5"
        attempts = 1
        last_error = "Transient network issue"

        with patch("src.notifications.notifier.logger.warning") as mock_log_warning:
            result = mock_notifier.notify_debug_budget_exhausted(task_id, attempts, last_error)
            assert not result # Expect False due to failure
            mock_log_warning.assert_called_once_with(f"Failed to send ntfy notification: Network error")
