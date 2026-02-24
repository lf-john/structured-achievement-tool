import json
import os
from typing import Dict

class DebugBudgetManager:
    """
    Manages the debug attempt budget for tasks, persisting counts to a JSON file.
    """
    def __init__(self, budget_file: str = ".memory/debug_budgets.json"):
        self.budget_file = budget_file
        self.budgets: Dict[str, int] = {}
        self._load_budgets()

    def _load_budgets(self):
        """Loads debug budgets from the JSON file."""
        if os.path.exists(self.budget_file):
            try:
                with open(self.budget_file, 'r') as f:
                    self.budgets = json.load(f)
            except json.JSONDecodeError:
                # Handle corrupted JSON file by initializing with empty budgets
                self.budgets = {}
        else:
            # Ensure the directory exists if the file doesn't
            os.makedirs(os.path.dirname(self.budget_file), exist_ok=True)

    def _persist_budgets(self):
        """Persists current debug budgets to the JSON file."""
        with open(self.budget_file, 'w') as f:
            json.dump(self.budgets, f, indent=4)

    def increment_debug_attempt(self, task_id: str):
        """Increments the debug attempt count for a given task."""
        self.budgets[task_id] = self.budgets.get(task_id, 0) + 1
        self._persist_budgets()

    def reset_debug_budget(self, task_id: str):
        """Resets the debug attempt count for a given task."""
        if task_id in self.budgets:
            del self.budgets[task_id]
            self._persist_budgets()

    def get_debug_attempts(self, task_id: str) -> int:
        """Returns the current debug attempt count for a given task."""
        return self.budgets.get(task_id, 0)

