"""
Tests for DebugBudgetManager — debug budget tracking, persistence, enforcement, and session locking.
Consolidates US-001, US-002, and US-004 tests.
"""

import pytest
import json
import os

from src.core.debug_budget_manager import DebugBudgetManager, MAX_DEBUG_ATTEMPTS


class TestDebugBudgetTracking:
    """Track debug attempts per task, persist to JSON."""

    @pytest.fixture
    def budget_path(self, tmp_path):
        return str(tmp_path / "debug_budgets.json")

    def test_track_debug_attempts_for_single_task(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        assert manager.get_debug_attempts("task-123") == 0
        manager.increment_debug_attempt("task-123")
        assert manager.get_debug_attempts("task-123") == 1
        manager.increment_debug_attempt("task-123")
        assert manager.get_debug_attempts("task-123") == 2

    def test_track_attempts_independently_per_task(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        manager.increment_debug_attempt("task-1")
        manager.increment_debug_attempt("task-1")
        manager.increment_debug_attempt("task-2")
        assert manager.get_debug_attempts("task-1") == 2
        assert manager.get_debug_attempts("task-2") == 1

    def test_persist_and_reload_budgets(self, budget_path):
        manager1 = DebugBudgetManager(budget_path)
        manager1.increment_debug_attempt("task-A")
        manager1.increment_debug_attempt("task-A")
        manager1.increment_debug_attempt("task-B")

        # Simulate restart by creating new instance
        manager2 = DebugBudgetManager(budget_path)
        assert manager2.get_debug_attempts("task-A") == 2
        assert manager2.get_debug_attempts("task-B") == 1

    def test_handle_missing_budget_file(self, tmp_path):
        path = str(tmp_path / "nonexistent" / "budgets.json")
        manager = DebugBudgetManager(path)
        assert manager.get_debug_attempts("task-X") == 0
        manager.increment_debug_attempt("task-X")
        assert manager.get_debug_attempts("task-X") == 1
        assert os.path.exists(path)

    def test_reset_debug_budget(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        manager.increment_debug_attempt("task-reset")
        manager.increment_debug_attempt("task-reset")
        assert manager.get_debug_attempts("task-reset") == 2

        manager.reset_debug_budget("task-reset")
        assert manager.get_debug_attempts("task-reset") == 0

    def test_reset_nonexistent_task_no_error(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        manager.reset_debug_budget("no-such-task")  # Should not raise
        assert manager.get_debug_attempts("no-such-task") == 0


class TestDebugBudgetEnforcement:
    """Enforce max 3 debug attempts per task."""

    @pytest.fixture
    def budget_path(self, tmp_path):
        return str(tmp_path / "debug_budgets.json")

    def test_allow_debug_for_new_task(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        assert manager.can_initiate_debug_session("new-task") is True

    def test_allow_debug_when_under_budget(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        manager.increment_debug_attempt("task-1")
        manager.increment_debug_attempt("task-1")
        assert manager.can_initiate_debug_session("task-1") is True  # 2 < 3

    def test_reject_debug_when_budget_exhausted(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        for _ in range(MAX_DEBUG_ATTEMPTS):
            manager.increment_debug_attempt("task-1")
        assert manager.can_initiate_debug_session("task-1") is False

    def test_reject_debug_when_over_budget(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        for _ in range(MAX_DEBUG_ATTEMPTS + 1):
            manager.increment_debug_attempt("task-1")
        assert manager.can_initiate_debug_session("task-1") is False

    def test_reset_restores_budget(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        for _ in range(MAX_DEBUG_ATTEMPTS):
            manager.increment_debug_attempt("task-1")
        assert manager.can_initiate_debug_session("task-1") is False
        manager.reset_debug_budget("task-1")
        assert manager.can_initiate_debug_session("task-1") is True


class TestDebugSessionLock:
    """Enforce max 1 active debug session at a time via flock."""

    @pytest.fixture
    def budget_path(self, tmp_path):
        return str(tmp_path / "debug_budgets.json")

    def test_acquire_and_release_lock(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        assert manager.acquire_debug_lock() is True
        manager.release_debug_lock()

    def test_second_lock_fails_while_first_held(self, budget_path):
        manager1 = DebugBudgetManager(budget_path)
        manager2 = DebugBudgetManager(budget_path)

        assert manager1.acquire_debug_lock() is True
        assert manager2.acquire_debug_lock() is False  # Should fail

        manager1.release_debug_lock()
        assert manager2.acquire_debug_lock() is True  # Now should succeed
        manager2.release_debug_lock()

    def test_release_without_acquire_no_error(self, budget_path):
        manager = DebugBudgetManager(budget_path)
        manager.release_debug_lock()  # Should not raise
