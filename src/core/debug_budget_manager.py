import fcntl
import json
import logging
import os

logger = logging.getLogger(__name__)

MAX_DEBUG_ATTEMPTS = 3


class DebugBudgetManager:
    def __init__(self, budget_file_path=".memory/debug_budgets.json"):
        self.budget_file_path = str(budget_file_path)
        self._lock_path = self.budget_file_path + ".lock"
        self.budgets = self._load_budgets()

    def _load_budgets(self):
        if os.path.exists(self.budget_file_path):
            with open(self.budget_file_path) as f:
                return json.load(f)
        return {}

    def _save_budgets(self):
        os.makedirs(os.path.dirname(self.budget_file_path), exist_ok=True)
        json_string = json.dumps(self.budgets, indent=4)
        with open(self.budget_file_path, "w") as f:
            f.write(json_string)

    def increment_debug_attempt(self, task_id: str):
        self.budgets[task_id] = self.budgets.get(task_id, 0) + 1
        self._save_budgets()

    def reset_debug_budget(self, task_id: str):
        if task_id in self.budgets:
            del self.budgets[task_id]
            self._save_budgets()

    def get_debug_attempts(self, task_id: str) -> int:
        return self.budgets.get(task_id, 0)

    def can_initiate_debug_session(self, task_id: str) -> bool:
        """Check if a debug session can be initiated (budget not exhausted)."""
        return self.get_debug_attempts(task_id) < MAX_DEBUG_ATTEMPTS

    def acquire_debug_lock(self) -> bool:
        """Acquire exclusive debug session lock. Returns True if acquired, False if another session is active."""
        os.makedirs(os.path.dirname(self._lock_path), exist_ok=True)
        try:
            self._lock_fd = open(self._lock_path, "w")
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
            return True
        except OSError:
            logger.warning("Another debug session is already active")
            if hasattr(self, "_lock_fd"):
                self._lock_fd.close()
                self._lock_fd = None
            return False

    def release_debug_lock(self):
        """Release the debug session lock."""
        if hasattr(self, "_lock_fd") and self._lock_fd:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                self._lock_fd.close()
            except OSError:
                pass
            self._lock_fd = None
            try:
                os.unlink(self._lock_path)
            except OSError:
                pass
