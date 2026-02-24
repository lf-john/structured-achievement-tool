"""
IMPLEMENTATION PLAN for US-003:

Components:
  - src/core/debug_session_manager.py: A new module containing a `DebugSessionManager` class.
    - Responsibilities:
      - `start_session(session_id: str)`: Attempts to start a debug session. Returns `True` if successful, `False` otherwise. Sets the internal active session ID.
      - `end_session(session_id: str)`: Ends the debug session only if the `session_id` matches the active one. Returns `True` on success, `False` on mismatch or no active session. Clears the internal active session ID.
      - `is_active()`: Returns `True` if a session is active, `False` otherwise.
      - `get_active_session_id()`: Returns the ID of the active session or `None`.
    - Internal State: A private instance variable `_active_session_id: str | None` to store the ID of the currently active session.

Data Flow:
  - Callers (e.g., `orchestrator`, `debug_workflow`) will invoke `DebugSessionManager.start_session()` before starting a debug task.
  - Callers will invoke `DebugSessionManager.end_session()` upon completion or termination of a debug task.
  - `is_active()` and `get_active_session_id()` provide status checks.

Integration Points:
  - src/orchestrator.py: The main orchestrator will likely instantiate and use the `DebugSessionManager` to gate debug workflow execution.
  - src/workflows/debug_workflow.py: The debug workflow might query the manager for session status before proceeding.

Edge Cases:
  - Attempting to start a session when one is already active (should be rejected).
  - Attempting to end a session when none is active.
  - Attempting to end a session with an ID that does not match the active one.
  - Multiple rapid concurrent calls to `start_session` (only the first should succeed).

Test Cases:
  1. [AC 1, 2] -> `test_should_allow_single_session_to_start_when_no_active_session`: Verify `start_session` succeeds and sets the session as active.
  2. [AC 1, 2] -> `test_should_report_session_as_active_after_start`: Verify `is_active` returns `True`.
  3. [AC 1, 2] -> `test_should_return_active_session_id_after_start`: Verify `get_active_session_id` returns the correct ID.
  4. [AC 1, 2] -> `test_should_reject_second_session_when_one_is_active`: Verify `start_session` returns `False` when a session is already active.
  5. [AC 1, 2] -> `test_should_allow_session_to_end_when_active`: Verify `end_session` succeeds for the active session.
  6. [AC 1, 2] -> `test_should_report_session_as_inactive_after_end`: Verify `is_active` returns `False` after a session ends.
  7. [AC 1, 2] -> `test_should_return_none_for_active_session_id_after_end`: Verify `get_active_session_id` returns `None` after a session ends.
  8. [AC 1, 2] -> `test_should_reject_ending_non_existent_session`: Verify `end_session` returns `False` when no session is active.
  9. [AC 1, 2] -> `test_should_reject_ending_different_session_id`: Verify `end_session` returns `False` if `session_id` does not match the active one.

Edge Case Tests:
  - `test_should_handle_multiple_rapid_start_attempts_only_first_succeeds`: Simulate quick successive calls to `start_session` and ensure only the first succeeds.
  - `test_should_handle_start_end_start_cycle`: Test a full cycle of starting, ending, and restarting a session.
"""

import pytest
from unittest.mock import MagicMock, patch

# CRITICAL: This import is expected to fail initially as the module does not exist yet.
from src.core.debug_session_manager import DebugSessionManager

class TestDebugSessionManager:

    def setup_method(self):
        # Ensure a clean state before each test
        DebugSessionManager._active_session_id = None

    def test_should_allow_single_session_to_start_when_no_active_session(self):
        """
        [AC 1, 2] Verify `start_session` succeeds and sets the session as active when no session is active.
        """
        session_id = "debug-session-1"
        assert DebugSessionManager.start_session(session_id) is True
        assert DebugSessionManager.is_active() is True
        assert DebugSessionManager.get_active_session_id() == session_id

    def test_should_report_session_as_active_after_start(self):
        """
        [AC 1, 2] Verify `is_active` returns `True` after a session starts.
        """
        session_id = "debug-session-2"
        DebugSessionManager.start_session(session_id)
        assert DebugSessionManager.is_active() is True

    def test_should_return_active_session_id_after_start(self):
        """
        [AC 1, 2] Verify `get_active_session_id` returns the correct ID after a session starts.
        """
        session_id = "debug-session-3"
        DebugSessionManager.start_session(session_id)
        assert DebugSessionManager.get_active_session_id() == session_id

    def test_should_reject_second_session_when_one_is_active(self):
        """
        [AC 1, 2] Verify `start_session` returns `False` when a session is already active.
        """
        session_id_1 = "debug-session-4a"
        session_id_2 = "debug-session-4b"

        DebugSessionManager.start_session(session_id_1)
        assert DebugSessionManager.start_session(session_id_2) is False
        assert DebugSessionManager.get_active_session_id() == session_id_1 # First session remains active

    def test_should_allow_session_to_end_when_active(self):
        """
        [AC 1, 2] Verify `end_session` succeeds for the active session.
        """
        session_id = "debug-session-5"
        DebugSessionManager.start_session(session_id)
        assert DebugSessionManager.end_session(session_id) is True
        assert DebugSessionManager.is_active() is False
        assert DebugSessionManager.get_active_session_id() is None

    def test_should_report_session_as_inactive_after_end(self):
        """
        [AC 1, 2] Verify `is_active` returns `False` after a session ends.
        """
        session_id = "debug-session-6"
        DebugSessionManager.start_session(session_id)
        DebugSessionManager.end_session(session_id)
        assert DebugSessionManager.is_active() is False

    def test_should_return_none_for_active_session_id_after_end(self):
        """
        [AC 1, 2] Verify `get_active_session_id` returns `None` after a session ends.
        """
        session_id = "debug-session-7"
        DebugSessionManager.start_session(session_id)
        DebugSessionManager.end_session(session_id)
        assert DebugSessionManager.get_active_session_id() is None

    def test_should_reject_ending_non_existent_session(self):
        """
        [AC 1, 2] Verify `end_session` returns `False` when no session is active.
        """
        session_id = "debug-session-8"
        assert DebugSessionManager.end_session(session_id) is False
        assert DebugSessionManager.is_active() is False

    def test_should_reject_ending_different_session_id(self):
        """
        [AC 1, 2] Verify `end_session` returns `False` if `session_id` does not match the active one.
        """
        session_id_active = "debug-session-9a"
        session_id_wrong = "debug-session-9b"
        DebugSessionManager.start_session(session_id_active)
        assert DebugSessionManager.end_session(session_id_wrong) is False
        assert DebugSessionManager.is_active() is True # Session should still be active
        assert DebugSessionManager.get_active_session_id() == session_id_active

    def test_should_handle_multiple_rapid_start_attempts_only_first_succeeds(self):
        """
        Edge Case: Simulate quick successive calls to `start_session` and ensure only the first succeeds.
        """
        session_id_1 = "debug-session-10a"
        session_id_2 = "debug-session-10b"
        session_id_3 = "debug-session-10c"

        assert DebugSessionManager.start_session(session_id_1) is True
        assert DebugSessionManager.start_session(session_id_2) is False
        assert DebugSessionManager.start_session(session_id_3) is False

        assert DebugSessionManager.is_active() is True
        assert DebugSessionManager.get_active_session_id() == session_id_1

    def test_should_handle_start_end_start_cycle(self):
        """
        Edge Case: Test a full cycle of starting, ending, and restarting a session.
        """
        session_id_1 = "debug-session-11a"
        session_id_2 = "debug-session-11b"

        # Start 1
        assert DebugSessionManager.start_session(session_id_1) is True
        assert DebugSessionManager.is_active() is True
        assert DebugSessionManager.get_active_session_id() == session_id_1

        # End 1
        assert DebugSessionManager.end_session(session_id_1) is True
        assert DebugSessionManager.is_active() is False
        assert DebugSessionManager.get_active_session_id() is None

        # Start 2
        assert DebugSessionManager.start_session(session_id_2) is True
        assert DebugSessionManager.is_active() is True
        assert DebugSessionManager.get_active_session_id() == session_id_2

        # End 2
        assert DebugSessionManager.end_session(session_id_2) is True
        assert DebugSessionManager.is_active() is False
        assert DebugSessionManager.get_active_session_id() is None


# At the END of your test file, ALWAYS include:
import sys
# Pytest handles exit codes automatically. We expect import errors or assertion failures initially.
# This ensures that if run without pytest, it would also signal failure.
if __name__ == "__main__":
    pytest.main([__file__])
    # The DebugSessionManager will not exist yet, causing an ImportError.
    # Pytest will exit with a non-zero code for the failed test collection.
    # If for some reason pytest succeeds (e.g., if the module was somehow created),
    # this explicit exit(1) would ensure the TDD-RED phase correctly fails.
    sys.exit(1)
