import os
from datetime import datetime, timedelta

from src.llm_budget_config import LLMBudgetConfig
from src.db.llm_cost_db import LLMCostDB

class LLMCostTracker:
    def __init__(self, budget_config: LLMBudgetConfig, cost_db: LLMCostDB):
        self.budget_config = budget_config
        self.cost_db = cost_db
        self._fallback_triggered_daily = False
        self._fallback_triggered_monthly = False

    def _get_estimated_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = self.budget_config.get_model_pricing()
        model_pricing = pricing.get(model_name)

        if not model_pricing:
            # In a real app, this should log a warning or raise a more specific error
            raise KeyError(f"Pricing information not found for model: {model_name}")

        input_cost_per_million = model_pricing.get('input_cost_per_million_tokens', 0.0)
        output_cost_per_million = model_pricing.get('output_cost_per_million_tokens', 0.0)

        cost = (
            (prompt_tokens / 1_000_000) * input_cost_per_million +
            (completion_tokens / 1_000_000) * output_cost_per_million
        )
        return cost

    def log_api_call(self, model_name: str, prompt_tokens: int, completion_tokens: int):
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("Token counts cannot be negative")

        try:
            cost = self._get_estimated_cost(model_name, prompt_tokens, completion_tokens)
            self.cost_db.add_log_entry(model_name, prompt_tokens, completion_tokens, cost)
        except KeyError as e:
            print(f"Error calculating cost for {model_name}: {e}. Log entry not added.")
        except Exception as e:
            print(f"Error logging API call to DB: {e}. Call was: model={model_name}, prompt={prompt_tokens}, completion={completion_tokens}")
            # Degrade gracefully - do not re-raise

    def _trigger_fallback(self, budget_type: str, current_cost: float, budget_limit: float):
        # In a real application, this would implement actual fallback logic
        # e.g., switch to a cheaper model, notify an admin, pause operations.
        # For now, we'll just print a message.
        print(f"[FALLBACK TRIGGERED] {budget_type.capitalize()} budget of ${budget_limit:.2f} approached/exceeded. Current cost: ${current_cost:.2f}")
        if budget_type == 'daily':
            self._fallback_triggered_daily = True
        elif budget_type == 'monthly':
            self._fallback_triggered_monthly = True


    def check_budget_exceeded(self) -> bool:
        daily_budget = self.budget_config.get_daily_budget()
        monthly_budget = self.budget_config.get_monthly_budget()

        daily_warning_threshold = self.budget_config.get_daily_warning_threshold()
        monthly_warning_threshold = self.budget_config.get_monthly_warning_threshold()

        current_daily_cost = self.cost_db.get_daily_cost()
        current_monthly_cost = self.cost_db.get_monthly_cost()

        exceeded = False

        if daily_budget > 0:
            if current_daily_cost >= daily_budget:
                if not self._fallback_triggered_daily:
                    self._trigger_fallback('daily', current_daily_cost, daily_budget)
                exceeded = True
            elif daily_warning_threshold > 0 and current_daily_cost >= daily_budget * daily_warning_threshold:
                if not self._fallback_triggered_daily:
                    self._trigger_fallback('daily', current_daily_cost, daily_budget)

        if monthly_budget > 0:
            if current_monthly_cost >= monthly_budget:
                if not self._fallback_triggered_monthly:
                    self._trigger_fallback('monthly', current_monthly_cost, monthly_budget)
                exceeded = True
            elif monthly_warning_threshold > 0 and current_monthly_cost >= monthly_budget * monthly_warning_threshold:
                if not self._fallback_triggered_monthly:
                    self._trigger_fallback('monthly', current_monthly_cost, monthly_budget)

        return exceeded
