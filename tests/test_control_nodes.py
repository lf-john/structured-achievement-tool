"""Tests for src.workflows.control_nodes — NOTIFY and PAUSE LangGraph nodes."""

from unittest.mock import MagicMock, patch

from src.workflows.control_nodes import (
    _build_signal_content,
    _extract_human_response,
    _read_signal_file,
    notify_node,
    pause_decision,
    pause_node,
)
from src.workflows.state import StoryState


def _make_state(**overrides) -> StoryState:
    """Create a minimal StoryState for testing."""
    defaults = {
        "story": {"id": "S-001", "title": "Add login feature"},
        "task_id": "task-42",
        "task_description": "Implement user authentication",
        "current_phase": "CODE",
        "phase_outputs": [
            {
                "phase": "CODE",
                "status": "complete",
                "output": "Implemented the login endpoint with bcrypt hashing.",
                "exit_code": 0,
                "provider_used": "claude",
                "duration_seconds": 12.5,
                "timestamp": "2026-02-26T10:00:00",
                "artifacts": {},
            }
        ],
        "phase_retry_count": 0,
        "verify_passed": None,
        "test_results": None,
        "failure_context": "",
        "story_attempt": 1,
        "max_attempts": 5,
        "mediator_verdict": None,
        "mediator_enabled": False,
        "working_directory": "/tmp/sat-test",
        "git_base_commit": None,
        "design_output": "",
        "test_files": "",
        "plan_output": "",
        "reproduction_status": None,
        "reproduction_details": None,
        "diagnosis_category": None,
        "diagnosis_reasoning": None,
    }
    defaults.update(overrides)
    return StoryState(**defaults)


def _make_notifier():
    """Create a mock Notifier."""
    notifier = MagicMock()
    notifier.send_ntfy.return_value = True
    notifier.send_email.return_value = True
    return notifier


# =============================================================================
# NOTIFY Node Tests
# =============================================================================


class TestNotifyNode:
    """Tests for the notify_node function."""

    def test_sends_to_ntfy_only(self):
        """NOTIFY with channel='ntfy' should call send_ntfy but not send_email."""
        state = _make_state(verify_passed=True)
        notifier = _make_notifier()

        result = notify_node(state, notifier, channel="ntfy")

        notifier.send_ntfy.assert_called_once()
        notifier.send_email.assert_not_called()
        assert result is not None

    def test_sends_to_email_only(self):
        """NOTIFY with channel='email' should call send_email but not send_ntfy."""
        state = _make_state(verify_passed=True)
        notifier = _make_notifier()

        result = notify_node(state, notifier, channel="email")

        notifier.send_email.assert_called_once()
        notifier.send_ntfy.assert_not_called()
        assert result is not None

    def test_sends_to_both_channels(self):
        """NOTIFY with channel='all' should call both send_ntfy and send_email."""
        state = _make_state(verify_passed=True)
        notifier = _make_notifier()

        notify_node(state, notifier, channel="all")

        notifier.send_ntfy.assert_called_once()
        notifier.send_email.assert_called_once()

    def test_ntfy_failure_does_not_raise(self):
        """If send_ntfy throws, NOTIFY should log but not crash."""
        state = _make_state(verify_passed=True)
        notifier = _make_notifier()
        notifier.send_ntfy.side_effect = ConnectionError("ntfy down")

        result = notify_node(state, notifier, channel="ntfy")

        # Should complete without raising
        assert "phase_outputs" in result

    def test_email_failure_does_not_raise(self):
        """If send_email throws, NOTIFY should log but not crash."""
        state = _make_state(verify_passed=False)
        notifier = _make_notifier()
        notifier.send_email.side_effect = ConnectionError("SMTP down")

        result = notify_node(state, notifier, channel="email")

        assert "phase_outputs" in result

    def test_extracts_story_id_and_title(self):
        """NOTIFY should include story ID and title in the notification."""
        state = _make_state(
            story={"id": "BUG-99", "title": "Fix null pointer"},
            verify_passed=False,
        )
        notifier = _make_notifier()

        notify_node(state, notifier, channel="ntfy")

        call_args = notifier.send_ntfy.call_args
        assert "BUG-99" in call_args.kwargs.get("title", call_args[1].get("title", ""))
        assert "Fix null pointer" in call_args.kwargs.get("message", call_args[1].get("message", ""))

    def test_success_status_in_notification(self):
        """When verify_passed=True, notification should indicate SUCCESS."""
        state = _make_state(verify_passed=True)
        notifier = _make_notifier()

        notify_node(state, notifier, channel="ntfy")

        call_args = notifier.send_ntfy.call_args
        title = call_args.kwargs.get("title", call_args[1].get("title", ""))
        assert "SUCCESS" in title

    def test_failure_status_uses_high_priority(self):
        """When verify_passed=False, notification should use high priority."""
        state = _make_state(verify_passed=False)
        notifier = _make_notifier()

        notify_node(state, notifier, channel="ntfy")

        call_args = notifier.send_ntfy.call_args
        priority = call_args.kwargs.get("priority", call_args[1].get("priority", ""))
        assert priority == "high"

    def test_in_progress_status_when_verify_none(self):
        """When verify_passed is None, status should be IN PROGRESS."""
        state = _make_state(verify_passed=None)
        notifier = _make_notifier()

        notify_node(state, notifier, channel="ntfy")

        call_args = notifier.send_ntfy.call_args
        title = call_args.kwargs.get("title", call_args[1].get("title", ""))
        assert "IN PROGRESS" in title

    def test_records_phase_output(self):
        """NOTIFY should append a NOTIFY phase output to the state."""
        state = _make_state()
        notifier = _make_notifier()
        original_count = len(state["phase_outputs"])

        result = notify_node(state, notifier, channel="all")

        assert len(result["phase_outputs"]) == original_count + 1
        last_output = result["phase_outputs"][-1]
        assert last_output["phase"] == "NOTIFY"
        assert last_output["status"] == "complete"

    def test_truncates_long_context(self):
        """Context from phase output should be truncated to 200 chars."""
        long_output = "A" * 500
        state = _make_state(
            phase_outputs=[{
                "phase": "CODE", "status": "complete", "output": long_output,
                "exit_code": 0, "provider_used": "claude",
                "duration_seconds": 1.0, "timestamp": "2026-02-26T10:00:00",
                "artifacts": {},
            }]
        )
        notifier = _make_notifier()

        notify_node(state, notifier, channel="ntfy")

        call_args = notifier.send_ntfy.call_args
        message = call_args.kwargs.get("message", call_args[1].get("message", ""))
        # The context portion should be truncated, ending with "..."
        assert "..." in message

    def test_empty_phase_outputs(self):
        """NOTIFY should handle empty phase_outputs gracefully."""
        state = _make_state(phase_outputs=[])
        notifier = _make_notifier()

        notify_node(state, notifier, channel="ntfy")

        notifier.send_ntfy.assert_called_once()
        # Message should not contain "Context:" since there's nothing
        call_args = notifier.send_ntfy.call_args
        message = call_args.kwargs.get("message", call_args[1].get("message", ""))
        assert "Context:" not in message


# =============================================================================
# PAUSE Node Tests
# =============================================================================


class TestPauseNode:
    """Tests for the pause_node function."""

    def test_creates_signal_file_with_correct_content(self):
        """PAUSE should write a signal file containing story context and # <Pending>."""
        state = _make_state()
        notifier = _make_notifier()

        written = {}

        def mock_write(path, content):
            written["path"] = path
            written["content"] = content

        # Respond immediately on first poll
        def mock_read(path):
            return "approved\n\n---\n\napproved\n<Pending>\n"

        pause_node(
            state, notifier,
            signal_dir="/tmp/test-sat",
            _sleep_fn=lambda x: None,
            _write_fn=mock_write,
            _read_fn=mock_read,
        )

        assert "approvals" in written["path"]
        assert "S-001_approval.md" in written["path"]
        assert "# <Pending>" in written["content"]
        assert "S-001" in written["content"]

    def test_sends_initial_notification(self):
        """PAUSE should send an ntfy notification when creating the signal file."""
        state = _make_state()
        notifier = _make_notifier()

        def mock_read(path):
            return "ok\n<Pending>\n"

        pause_node(
            state, notifier,
            signal_dir="/tmp/test-sat",
            _sleep_fn=lambda x: None,
            _write_fn=lambda p, c: None,
            _read_fn=mock_read,
        )

        # Should have been called at least once for the initial notification
        assert notifier.send_ntfy.call_count >= 1
        first_call = notifier.send_ntfy.call_args_list[0]
        title = first_call.kwargs.get("title", first_call[1].get("title", ""))
        assert "Approval Required" in title

    def test_detects_human_response(self):
        """PAUSE should detect when human removes # from # <Pending>."""
        state = _make_state()
        notifier = _make_notifier()
        poll_count = [0]

        def mock_read(path):
            poll_count[0] += 1
            if poll_count[0] >= 3:
                return "Some context\n\n---\n\nLooks good, approved!\n<Pending>\n"
            return None  # Still waiting

        result = pause_node(
            state, notifier,
            signal_dir="/tmp/test-sat",
            escalation_timeout=300,
            poll_interval=10,
            _sleep_fn=lambda x: None,
            _write_fn=lambda p, c: None,
            _read_fn=mock_read,
        )

        assert result["pause_response"] == "Looks good, approved!"
        assert result["pause_escalated"] is False

    def test_escalation_timeout_triggers_notification(self):
        """After first timeout, PAUSE should send an escalation notification."""
        state = _make_state()
        notifier = _make_notifier()
        poll_count = [0]

        def mock_read(path):
            poll_count[0] += 1
            # Respond during second timeout window (after escalation)
            if poll_count[0] > 5:
                return "ok\n<Pending>\n"
            return None

        result = pause_node(
            state, notifier,
            signal_dir="/tmp/test-sat",
            escalation_timeout=30,  # 3 polls of 10s each
            poll_interval=10,
            _sleep_fn=lambda x: None,
            _write_fn=lambda p, c: None,
            _read_fn=mock_read,
        )

        # Should have sent escalation notification (second send_ntfy call)
        assert notifier.send_ntfy.call_count >= 2
        escalation_call = notifier.send_ntfy.call_args_list[1]
        title = escalation_call.kwargs.get("title", escalation_call[1].get("title", ""))
        assert "ESCALATION" in title

        assert result["pause_escalated"] is True

    def test_auto_continues_after_double_timeout(self):
        """After double timeout with no response, PAUSE should auto-continue."""
        state = _make_state()
        notifier = _make_notifier()

        def mock_read(path):
            return None  # Never responds

        result = pause_node(
            state, notifier,
            signal_dir="/tmp/test-sat",
            escalation_timeout=20,
            poll_interval=10,
            _sleep_fn=lambda x: None,
            _write_fn=lambda p, c: None,
            _read_fn=mock_read,
        )

        assert result["pause_response"] == "no_response"
        assert result["pause_escalated"] is True

    def test_records_pause_phase_output(self):
        """PAUSE should record a PAUSE phase output in state."""
        state = _make_state()
        notifier = _make_notifier()
        original_count = len(state["phase_outputs"])

        def mock_read(path):
            return "approved\n<Pending>\n"

        result = pause_node(
            state, notifier,
            signal_dir="/tmp/test-sat",
            _sleep_fn=lambda x: None,
            _write_fn=lambda p, c: None,
            _read_fn=mock_read,
        )

        assert len(result["phase_outputs"]) == original_count + 1
        last_output = result["phase_outputs"][-1]
        assert last_output["phase"] == "PAUSE"
        assert last_output["status"] == "complete"

    def test_notification_failure_does_not_block_pause(self):
        """If ntfy fails during PAUSE, it should still write file and poll."""
        state = _make_state()
        notifier = _make_notifier()
        notifier.send_ntfy.side_effect = ConnectionError("ntfy down")

        def mock_read(path):
            return "Header\n\n---\n\napproved\n\n<Pending>\n"

        result = pause_node(
            state, notifier,
            signal_dir="/tmp/test-sat",
            _sleep_fn=lambda x: None,
            _write_fn=lambda p, c: None,
            _read_fn=mock_read,
        )

        assert result["pause_response"] == "approved"

    def test_signal_dir_tilde_expansion(self):
        """Signal dir with ~ should be expanded to full home path."""
        state = _make_state()
        notifier = _make_notifier()

        written = {}

        def mock_write(path, content):
            written["path"] = path

        def mock_read(path):
            return "ok\n<Pending>\n"

        pause_node(
            state, notifier,
            signal_dir="~/my-tasks",
            _sleep_fn=lambda x: None,
            _write_fn=mock_write,
            _read_fn=mock_read,
        )

        assert "~" not in written["path"]
        assert "/approvals/" in written["path"]


# =============================================================================
# Signal File Helper Tests
# =============================================================================


class TestSignalFileHelpers:
    """Tests for signal file content building and parsing."""

    def test_build_signal_content_includes_story_info(self):
        """Signal content should include story ID, title, and phase."""
        state = _make_state(
            story={"id": "FEAT-10", "title": "Add search"},
            current_phase="VERIFY",
        )

        content = _build_signal_content(state)

        assert "FEAT-10" in content
        assert "Add search" in content
        assert "VERIFY" in content
        assert "# <Pending>" in content

    def test_build_signal_content_includes_verification_status(self):
        """Signal content should show verification status."""
        state = _make_state(verify_passed=True)
        content = _build_signal_content(state)
        assert "passed" in content

        state = _make_state(verify_passed=False)
        content = _build_signal_content(state)
        assert "failed" in content

    def test_extract_response_approved(self):
        """Should extract approval text after separator."""
        content = (
            "# Approval Required: S-001\n\n"
            "Some context...\n\n"
            "---\n\n"
            "This looks great, ship it!\n\n"
            "<Pending>\n"
        )
        response = _extract_human_response(content)
        assert response == "This looks great, ship it!"

    def test_extract_response_rejection(self):
        """Should extract rejection text."""
        content = (
            "Header...\n\n---\n\n"
            "REJECTED: The approach is wrong, use a different algorithm.\n\n"
            "<Pending>\n"
        )
        response = _extract_human_response(content)
        assert response.startswith("REJECTED:")

    def test_extract_response_empty_defaults_to_approved(self):
        """If no text is added by user, default to 'approved'."""
        content = "Header...\n\n---\n\n<Pending>\n"
        response = _extract_human_response(content)
        assert response == "approved"

    def test_read_signal_file_pending(self):
        """File with '# <Pending>' should return None (not yet responded)."""
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            mock_open.return_value.read.return_value = "stuff\n# <Pending>\n"

            result = _read_signal_file("/tmp/test.md")
            assert result is None

    def test_read_signal_file_responded(self):
        """File with '<Pending>' (no #) should return content."""
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            mock_open.return_value.read.return_value = "response text\n<Pending>\n"

            result = _read_signal_file("/tmp/test.md")
            assert result is not None
            assert "response text" in result


# =============================================================================
# pause_decision Tests
# =============================================================================


class TestPauseDecision:
    """Tests for the pause_decision routing function."""

    def test_approved_response(self):
        """Normal response text should route to 'approved'."""
        state = _make_state()
        state["pause_response"] = "Looks good, continue"
        assert pause_decision(state) == "approved"

    def test_rejected_response(self):
        """Response starting with REJECTED: should route to 'rejected'."""
        state = _make_state()
        state["pause_response"] = "REJECTED: Wrong approach"
        assert pause_decision(state) == "rejected"

    def test_rejected_case_insensitive(self):
        """REJECTED: check should be case-insensitive."""
        state = _make_state()
        state["pause_response"] = "rejected: nope"
        assert pause_decision(state) == "rejected"

    def test_timeout_response(self):
        """'no_response' should route to 'timeout'."""
        state = _make_state()
        state["pause_response"] = "no_response"
        assert pause_decision(state) == "timeout"

    def test_missing_pause_response_defaults_to_timeout(self):
        """If pause_response is not set, should default to 'timeout'."""
        state = _make_state()
        # pause_response not in state — relies on .get() default
        assert pause_decision(state) == "timeout"
