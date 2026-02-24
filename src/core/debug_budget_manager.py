import json
import os

class DebugBudgetManager:
    def __init__(self, budget_file_path=".memory/debug_budgets.json"):
        self.budget_file_path = budget_file_path
        self.budgets = self._load_budgets()

    def _load_budgets(self):
        if os.path.exists(self.budget_file_path):
            with open(self.budget_file_path, 'r') as f:
                return json.load(f)
        return {}

    def _save_budgets(self):
        os.makedirs(os.path.dirname(self.budget_file_path), exist_ok=True)
        json_string = json.dumps(self.budgets, indent=4)
        with open(self.budget_file_path, 'w') as f:
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
        """
        Determines if a debug session can be initiated for a given task,
        based on the maximum allowed attempts.
        """
        current_attempts = self.get_debug_attempts(task_id)
        MAX_DEBUG_ATTEMPTS = 3
        return current_attempts < MAX_DEBUG_ATTEMPTS
