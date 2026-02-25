"""
IMPLEMENTATION PLAN for US-002:

Components:
  - DebugBudgetManager (class in src/core/debug_budget_manager.py):
    - can_initiate_debug_session(self, task_id: str) -> bool: A new method to determine if a debug session can be started for a task, based on the maximum allowed attempts.

Test Cases:
  1. [AC 1] -> test_should_reject_debug_session_when_budget_is_exhausted: Verifies that a debug session is rejected when the task has reached exactly 3 attempts.
  2. [AC 2] -> test_should_allow_debug_session_when_budget_is_available: Ensures that a debug session is allowed when the task has fewer than 3 attempts.
  3. [AC 2] -> test_should_allow_debug_session_for_new_task: Confirms that a new task (with 0 attempts) is allowed to initiate a debug session.
  4. [AC 1] -> test_should_reject_debug_session_when_budget_exceeds_max_attempts: Verifies that a debug session is still rejected if the task has more than 3 attempts (e.g., due to a previous bug or manual intervention).

Edge Cases:
  - Task with 0 attempts: Should be allowed.
  - Task with 1 or 2 attempts: Should be allowed.
  - Task with exactly 3 attempts: Should be rejected.
  - Task with more than 3 attempts: Should be rejected.
"""

import pytest
import json
import os
from unittest.mock import patch, mock_open

# Assume DebugBudgetManager will be in src/core/debug_budget_manager.py
# This import is expected to fail initially as the method doesn't exist, leading to a TDD-RED state.
from src.core.debug_budget_manager import DebugBudgetManager

class TestDebugBudgetEnforcement:
    @pytest.fixture
    def mock_storage_path(self, tmp_path):
        """Provides a temporary file path for budget storage."""
        return tmp_path / "debug_budgets.json"

    @pytest.fixture
    def budget_manager(self, mock_storage_path):
        """Provides a fresh DebugBudgetManager instance for each test."""
        return DebugBudgetManager(mock_storage_path)

    def test_should_allow_debug_session_for_new_task(self, budget_manager):
        """Ensures that a new task (with 0 attempts) is allowed to initiate a debug session."""
        task_id = "new-task-001"
        assert budget_manager.can_initiate_debug_session(task_id) is True

    def test_should_allow_debug_session_when_budget_is_available(self, budget_manager):
        """Ensures that a debug session is allowed when the task has fewer than 3 attempts."""
        task_id = "task-under-budget"

        # 1 attempt
        budget_manager.increment_debug_attempt(task_id)
        assert budget_manager.can_initiate_debug_session(task_id) is True

        # 2 attempts
        budget_manager.increment_debug_attempt(task_id)
        assert budget_manager.can_initiate_debug_session(task_id) is True

    def test_should_reject_debug_session_when_budget_is_exhausted(self, budget_manager):
        """Verifies that a debug session is rejected when the task has reached exactly 3 attempts."""
        task_id = "task-at-limit"

        # 3 attempts
        for _ in range(3):
            budget_manager.increment_debug_attempt(task_id)
        
        assert budget_manager.get_debug_attempts(task_id) == 3
        assert budget_manager.can_initiate_debug_session(task_id) is False

    def test_should_reject_debug_session_when_budget_exceeds_max_attempts(self, budget_manager):
        """Verifies that a debug session is still rejected if the task has more than 3 attempts."""
        task_id = "task-over-limit"

        # More than 3 attempts (e.g., 4)
        for _ in range(4):
            budget_manager.increment_debug_attempt(task_id)

        assert budget_manager.get_debug_attempts(task_id) > 3
        assert budget_manager.can_initiate_debug_session(task_id) is False

# This is a placeholder for running pytest and capturing output.
# The actual execution will be handled by the orchestrator.
# For TDD-RED, we expect an import error or AttributeError because 'can_initiate_debug_session'
# does not yet exist on DebugBudgetManager.

