"""
IMPLEMENTATION PLAN for US-001:

Components:
  - DebugBudgetManager (class): Manages debug attempt counts per task, including persistence and loading.
    - __init__(self, storage_path): Initializes with path to persistence file. Loads existing budgets.
    - increment_debug_attempt(self, task_id: str): Increments the debug count for a given task_id and persists.
    - reset_debug_budget(self, task_id: str): Resets the debug count for a given task_id to 0 and persists.
    - get_debug_attempts(self, task_id: str) -> int: Returns the current debug count for a task_id.
    - _load_budgets(self): Internal method to load budgets from the storage file.
    - _persist_budgets(self): Internal method to persist current budgets to the storage file.

Test Cases:
  1. [AC 1] -> test_should_accurately_track_debug_attempts_for_single_task: Verifies that incrementing the budget for a single task works correctly.
  2. [AC 1] -> test_should_track_debug_attempts_for_multiple_tasks_independently: Ensures that different tasks have independent debug budgets.
  3. [AC 2] -> test_should_persist_and_load_debug_budgets_correctly: Simulates application restart by re-initializing the manager and checking if counts are preserved.
  4. [AC 2] -> test_should_handle_missing_budget_file_on_startup: Ensures the manager starts with no budgets if the file doesn't exist.
  5. [AC 3] -> test_should_reset_debug_budget_for_a_specific_task: Verifies that the reset mechanism sets a task's budget to zero.
  6. [AC 4] -> This is a meta-criterion, covered by the successful execution of the other tests.

Edge Cases:
  - Attempting to get the budget for a non-existent task should return 0.
  - Resetting a non-existent task should not raise an error and set its budget to 0.
  - Incrementing a non-existent task should start its budget at 1.
"""

import pytest
import json
import os
from unittest.mock import patch, mock_open

# Assume DebugBudgetManager will be in src/core/debug_budget_manager.py
# This import will fail as the file does not exist, leading to a TDD-RED state.
from src.core.debug_budget_manager import DebugBudgetManager

class TestDebugBudgetManager:
    @pytest.fixture
    def mock_storage_path(self, tmp_path):
        """Provides a temporary file path for budget storage."""
        return tmp_path / "debug_budgets.json"

    def test_should_accurately_track_debug_attempts_for_single_task(self, mock_storage_path):
        """Verifies that incrementing the budget for a single task works correctly."""
        manager = DebugBudgetManager(mock_storage_path)
        task_id = "task-123"

        assert manager.get_debug_attempts(task_id) == 0

        manager.increment_debug_attempt(task_id)
        assert manager.get_debug_attempts(task_id) == 1

        manager.increment_debug_attempt(task_id)
        assert manager.get_debug_attempts(task_id) == 2

    def test_should_track_debug_attempts_for_multiple_tasks_independently(self, mock_storage_path):
        """Ensures that different tasks have independent debug budgets."""
        manager = DebugBudgetManager(mock_storage_path)
        task_id_1 = "task-1"
        task_id_2 = "task-2"

        manager.increment_debug_attempt(task_id_1)
        manager.increment_debug_attempt(task_id_1)
        manager.increment_debug_attempt(task_id_2)

        assert manager.get_debug_attempts(task_id_1) == 2
        assert manager.get_debug_attempts(task_id_2) == 1

    @patch("builtins.open", new_callable=mock_open, read_data=json.dumps({"task-persisted": 5}))
    @patch("os.path.exists", return_value=True)
    def test_should_persist_and_load_debug_budgets_correctly(self, mock_exists, mock_file_open, mock_storage_path):
        """Simulates application restart by re-initializing the manager and checking if counts are preserved."""
        # Initial manager state, not relevant for this test but for context
        manager_initial = DebugBudgetManager(mock_storage_path)
        manager_initial.increment_debug_attempt("task-persisted-new") # This will trigger _persist_budgets

        # The mock_file_open's read_data is used when the second manager is created
        manager_reloaded = DebugBudgetManager(mock_storage_path)

        assert manager_reloaded.get_debug_attempts("task-persisted") == 5
        assert manager_reloaded.get_debug_attempts("task-persisted-new") == 0 # Should not be in mock_file_open data

        # Test persistence on increment
        manager_reloaded.increment_debug_attempt("task-persisted")
        mock_file_open.assert_called_with(mock_storage_path, 'w')
        written_data = json.loads(mock_file_open().write.call_args[0][0])
        assert written_data["task-persisted"] == 6

    @patch("os.path.exists", return_value=False)
    def test_should_handle_missing_budget_file_on_startup(self, mock_exists, mock_storage_path):
        """Ensures the manager starts with no budgets if the file doesn't exist."""
        manager = DebugBudgetManager(mock_storage_path)
        assert manager.get_debug_attempts("non-existent-task") == 0
        manager.increment_debug_attempt("new-task")
        assert manager.get_debug_attempts("new-task") == 1
        mock_exists.assert_called_with(mock_storage_path) # Ensure exists was checked

    def test_should_reset_debug_budget_for_a_specific_task(self, mock_storage_path):
        """Verifies that the reset mechanism sets a task's budget to zero."""
        manager = DebugBudgetManager(mock_storage_path)
        task_id = "task-to-reset"

        manager.increment_debug_attempt(task_id)
        manager.increment_debug_attempt(task_id)
        assert manager.get_debug_attempts(task_id) == 2

        manager.reset_debug_budget(task_id)
        assert manager.get_debug_attempts(task_id) == 0

        # Resetting a non-existent task
        manager.reset_debug_budget("non-existent-task")
        assert manager.get_debug_attempts("non-existent-task") == 0
