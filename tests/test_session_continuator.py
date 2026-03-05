"""Tests for SessionContinuator — auto-continuation on max turns."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.execution.session_continuator import (
    MAX_CONTINUATIONS,
    ContinuationResult,
    SessionContinuator,
)


@pytest.fixture
def continuator():
    return SessionContinuator()


# ---------------------------------------------------------------------------
# Max turns detection
# ---------------------------------------------------------------------------
class TestDetectMaxTurns:
    """Test pattern matching for max-turns indicators."""

    @pytest.mark.parametrize("text", [
        "Error: maximum turns reached",
        "Maximum turn reached, stopping.",
        "max turns limit exceeded",
        "Max turn limit hit",
        "conversation turn limit reached",
        "Conversation Turn Limit — please retry",
        "reached maximum messages allowed",
        "We've reached maximum messages for this session",
    ])
    def test_detects_max_turns(self, continuator, text):
        assert continuator.detect_max_turns(text) is True

    @pytest.mark.parametrize("text", [
        "Task completed successfully",
        "All tests pass",
        "turn left at the next intersection",
        "the maximum value is 42",
        "",
        "Here is your output:\n\nDone.",
    ])
    def test_no_false_positives(self, continuator, text):
        assert continuator.detect_max_turns(text) is False

    def test_exit_code_param_accepted(self, continuator):
        """exit_code parameter exists but detection is pattern-based."""
        assert continuator.detect_max_turns("maximum turns reached", exit_code=1) is True
        assert continuator.detect_max_turns("all good", exit_code=1) is False


# ---------------------------------------------------------------------------
# Session ID extraction
# ---------------------------------------------------------------------------
class TestExtractSessionId:
    """Test session ID extraction from Claude CLI output."""

    @pytest.mark.parametrize("text,expected", [
        ("session_id: abc-123_XYZ", "abc-123_XYZ"),
        ("session id: sess-00ff", "sess-00ff"),
        ("sessionid: mySession42", "mySession42"),
        ("Session_Id: UPPER-case", "UPPER-case"),
        ("blah blah session_id: id99 blah", "id99"),
    ])
    def test_extracts_session_id(self, continuator, text, expected):
        assert continuator.extract_session_id(text) == expected

    def test_returns_none_when_missing(self, continuator):
        assert continuator.extract_session_id("no session here") is None

    def test_returns_none_on_empty(self, continuator):
        assert continuator.extract_session_id("") is None


# ---------------------------------------------------------------------------
# Continuation limit enforcement
# ---------------------------------------------------------------------------
class TestContinuationLimits:
    """Test the 3-max continuation guard."""

    def test_can_continue_initially(self, continuator):
        assert continuator.can_continue("task-1") is True

    def test_cannot_continue_after_max(self, continuator):
        for _ in range(MAX_CONTINUATIONS):
            continuator._continuation_counts["task-1"] = (
                continuator._continuation_counts.get("task-1", 0) + 1
            )
        assert continuator.can_continue("task-1") is False

    def test_counts_are_per_task(self, continuator):
        continuator._continuation_counts["task-A"] = MAX_CONTINUATIONS
        assert continuator.can_continue("task-A") is False
        assert continuator.can_continue("task-B") is True

    def test_get_count_returns_zero_initially(self, continuator):
        assert continuator.get_count("unknown") == 0

    def test_get_count_tracks_increments(self, continuator):
        continuator._continuation_counts["t1"] = 2
        assert continuator.get_count("t1") == 2

    def test_custom_max_continuations(self):
        c = SessionContinuator(max_continuations=5)
        c._continuation_counts["t"] = 4
        assert c.can_continue("t") is True
        c._continuation_counts["t"] = 5
        assert c.can_continue("t") is False


# ---------------------------------------------------------------------------
# Reset count
# ---------------------------------------------------------------------------
class TestResetCount:
    """Test reset_count clears the counter for a task."""

    def test_reset_existing(self, continuator):
        continuator._continuation_counts["task-1"] = 3
        continuator.reset_count("task-1")
        assert continuator.get_count("task-1") == 0
        assert continuator.can_continue("task-1") is True

    def test_reset_nonexistent_is_noop(self, continuator):
        continuator.reset_count("never-existed")  # should not raise


# ---------------------------------------------------------------------------
# Continue session (mocked subprocess)
# ---------------------------------------------------------------------------
class TestContinueSession:
    """Test continue_session with mocked subprocess.run."""

    @patch("src.execution.session_continuator.subprocess.run")
    def test_successful_continuation(self, mock_run, continuator):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Resumed output", stderr=""
        )
        result = continuator.continue_session("sess-1", "task-1", "/tmp")

        assert result.success is True
        assert result.session_id == "sess-1"
        assert result.continuation_count == 1
        assert result.output == "Resumed output"
        assert result.error == ""
        mock_run.assert_called_once_with(
            ["claude", "--resume", "sess-1"],
            capture_output=True, text=True,
            cwd="/tmp", timeout=600,
        )

    @patch("src.execution.session_continuator.subprocess.run")
    def test_failed_continuation(self, mock_run, continuator):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error occurred"
        )
        result = continuator.continue_session("sess-2", "task-2", "/tmp")

        assert result.success is False
        assert result.error == "Error occurred"
        assert result.continuation_count == 1

    @patch("src.execution.session_continuator.subprocess.run")
    def test_timeout(self, mock_run, continuator):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=600)
        result = continuator.continue_session("sess-3", "task-3", "/tmp")

        assert result.success is False
        assert "timed out" in result.error.lower()
        assert result.continuation_count == 1

    @patch("src.execution.session_continuator.subprocess.run")
    def test_unexpected_exception(self, mock_run, continuator):
        mock_run.side_effect = OSError("No such command")
        result = continuator.continue_session("sess-4", "task-4", "/tmp")

        assert result.success is False
        assert "No such command" in result.error

    @patch("src.execution.session_continuator.subprocess.run")
    def test_continuation_increments_count(self, mock_run, continuator):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        continuator.continue_session("s", "task-5", "/tmp")
        assert continuator.get_count("task-5") == 1

        continuator.continue_session("s", "task-5", "/tmp")
        assert continuator.get_count("task-5") == 2

    @patch("src.execution.session_continuator.subprocess.run")
    def test_count_increments_even_on_failure(self, mock_run, continuator):
        """Count goes up even when the continuation fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fail")

        continuator.continue_session("s", "task-6", "/tmp")
        assert continuator.get_count("task-6") == 1


# ---------------------------------------------------------------------------
# ContinuationResult dataclass
# ---------------------------------------------------------------------------
class TestContinuationResult:
    """Test ContinuationResult dataclass defaults and fields."""

    def test_defaults(self):
        r = ContinuationResult(success=True)
        assert r.success is True
        assert r.session_id is None
        assert r.continuation_count == 0
        assert r.output == ""
        assert r.error == ""

    def test_all_fields(self):
        r = ContinuationResult(
            success=False, session_id="s1",
            continuation_count=2, output="out", error="err",
        )
        assert r.success is False
        assert r.session_id == "s1"
        assert r.continuation_count == 2
        assert r.output == "out"
        assert r.error == "err"
