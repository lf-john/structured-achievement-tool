import json
import os


class LLMBudgetConfig:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            print(f"Warning: Config file not found at {self.config_path}. Using default values.")
            return {}
        try:
            with open(self.config_path) as f:
                full_config = json.load(f)
            return full_config.get("llm_cost_tracker", {})
        except json.JSONDecodeError as e:
            print(f"Error decoding config file {self.config_path}: {e}. Using default values.")
            return {}
        except Exception as e:
            print(f"Unexpected error loading config file {self.config_path}: {e}. Using default values.")
            return {}

    def _get_setting(self, key: str, default):
        return self._config.get(key, default)

    def get_daily_budget(self) -> float:
        return self._get_setting("daily_budget", 0.0)

    def get_monthly_budget(self) -> float:
        return self._get_setting("monthly_budget", 0.0)

    def get_daily_warning_threshold(self) -> float:
        return self._get_setting("daily_warning_threshold", 0.0)

    def get_monthly_warning_threshold(self) -> float:
        return self._get_setting("monthly_warning_threshold", 0.0)

    def get_model_pricing(self) -> dict:
        return self._get_setting("model_pricing", {})
