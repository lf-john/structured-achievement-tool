import json
import os

class DebugBudgetManager:
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self.budgets = self._load_budgets()

    def _load_budgets(self):
        if not os.path.exists(self.storage_path):
            return {}
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _persist_budgets(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(self.budgets, f, indent=4)

    def increment_debug_attempt(self, task_id: str):
        self.budgets[task_id] = self.budgets.get(task_id, 0) + 1
        self._persist_budgets()

    def reset_debug_budget(self, task_id: str):
        self.budgets[task_id] = 0
        self._persist_budgets()

    def get_debug_attempts(self, task_id: str) -> int:
        return self.budgets.get(task_id, 0)
