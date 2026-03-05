"""
LLM Cost Tracker — Records and queries LLM invocation costs.

Wraps LLMCostDB with:
- Token estimation (chars/4) when actual counts unavailable
- Split per-input and per-output pricing
- Actual token count recording when available from API responses
- Cached token estimation via actual vs estimated comparison
"""

import logging
import os
from typing import Dict, Optional
from datetime import datetime, timedelta

from src.db.llm_cost_db import LLMCostDB

logger = logging.getLogger(__name__)


# Per-million-token pricing (input/output split)
# Source: published API pricing as of 2026-03
COST_PER_MTOK: dict[str, dict[str, float]] = {
    # Claude (Anthropic)
    "claude-opus-4-6":           {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6":         {"input":  3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input":  0.80, "output":  4.00},
    # Gemini (Google)
    "gemini-2.5-pro":            {"input":  1.25, "output":  5.00},
    "gemini-3.1-pro-preview":    {"input":  1.25, "output":  5.00},
    "gemini-3-flash-preview":    {"input":  0.15, "output":  0.60},
    "gemini-2.5-flash":          {"input":  0.15, "output":  0.60},
    # GLM (z.ai proxy)
    "glm-4.7":                   {"input":  0.50, "output":  2.00},
    "glm-4.7-flash":             {"input":  0.10, "output":  0.40},
    # Local (Ollama) — free
    "qwen3:8b":                  {"input":  0.00, "output":  0.00},
    "deepseek-r1:8b":            {"input":  0.00, "output":  0.00},
    "qwen2.5-coder:7b":          {"input":  0.00, "output":  0.00},
    "nemotron-mini":             {"input":  0.00, "output":  0.00},
}

# Legacy blended rates for backward compatibility
COST_PER_1K_TOKENS = {
    model_id: (rates["input"] + rates["output"]) / 2000.0
    for model_id, rates in COST_PER_MTOK.items()
}

# Rough chars-per-token ratio for estimation
CHARS_PER_TOKEN = 4.0

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".memory", "llm_costs.db"
)


class LLMCostTracker:
    """Records LLM invocation costs and provides summaries."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db = LLMCostDB(db_path)

    def record_invocation(
        self,
        model_id: str,
        provider_name: str,
        prompt_chars: int,
        output_chars: int,
        duration_seconds: float = 0.0,
        actual_input_tokens: int = None,
        actual_output_tokens: int = None,
    ):
        """Record a single LLM invocation with estimated and actual cost.

        Args:
            model_id: The model identifier (e.g. 'claude-sonnet-4-6')
            provider_name: Provider name from routing engine (e.g. 'sonnet')
            prompt_chars: Approximate input character count
            output_chars: Output character count
            duration_seconds: Wall-clock time for the invocation
            actual_input_tokens: Actual input tokens from API response (if available)
            actual_output_tokens: Actual output tokens from API response (if available)
        """
        # Estimated tokens
        est_input = int(prompt_chars / CHARS_PER_TOKEN)
        est_output = int(output_chars / CHARS_PER_TOKEN)

        # Use actual if available, otherwise estimated
        input_tokens = actual_input_tokens if actual_input_tokens is not None else est_input
        output_tokens = actual_output_tokens if actual_output_tokens is not None else est_output

        # Calculate cost with split rates
        rates = COST_PER_MTOK.get(model_id, {"input": 5.0, "output": 15.0})
        input_cost = input_tokens / 1_000_000.0 * rates["input"]
        output_cost = output_tokens / 1_000_000.0 * rates["output"]
        estimated_cost = input_cost + output_cost

        # Estimate cached tokens by comparing actual vs estimated
        # If actual input is significantly less than estimated, the difference is likely cached
        cached_tokens = None
        if actual_input_tokens is not None and est_input > 0:
            diff = est_input - actual_input_tokens
            if diff > 100:  # Only count if meaningful difference
                cached_tokens = diff

        self.db.add_log_entry(
            model_name=f"{provider_name}/{model_id}",
            prompt_tokens=est_input,
            completion_tokens=est_output,
            estimated_cost=estimated_cost,
            actual_input_tokens=actual_input_tokens,
            actual_output_tokens=actual_output_tokens,
            cached_tokens=cached_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
        )
        logger.debug(
            f"Cost logged: {provider_name}/{model_id} "
            f"est={est_input}+{est_output} "
            f"{'actual=' + str(actual_input_tokens) + '+' + str(actual_output_tokens) + ' ' if actual_input_tokens else ''}"
            f"${estimated_cost:.4f} ({duration_seconds:.1f}s)"
        )

    def get_total_api_calls_for_day(self, date: Optional[datetime] = None) -> Dict[str, int]:
        """Count API calls by provider family for a given day."""
        d = date or datetime.now()
        date_str = d.strftime('%Y-%m-%d')
        import sqlite3
        counts: Dict[str, int] = {}
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT model_name, COUNT(*) FROM llm_costs "
                    "WHERE substr(timestamp, 1, 10) = ? GROUP BY model_name",
                    (date_str,)
                )
                for row in cursor.fetchall():
                    family = row[0].split("/")[0] if "/" in row[0] else row[0]
                    counts[family] = counts.get(family, 0) + row[1]
        except Exception as e:
            logger.warning(f"Error getting API call counts: {e}")
        return counts

    def get_daily_cost_summary(self, date: Optional[datetime] = None) -> Dict[str, float]:
        """Get cost breakdown by provider for a given day."""
        d = date or datetime.now()
        date_str = d.strftime('%Y-%m-%d')
        import sqlite3
        costs: Dict[str, float] = {}
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT model_name, SUM(estimated_cost) FROM llm_costs "
                    "WHERE substr(timestamp, 1, 10) = ? GROUP BY model_name",
                    (date_str,)
                )
                for row in cursor.fetchall():
                    family = row[0].split("/")[0] if "/" in row[0] else row[0]
                    costs[family] = costs.get(family, 0.0) + (row[1] or 0.0)
        except Exception as e:
            logger.warning(f"Error getting daily cost summary: {e}")
        return costs

    def get_weekly_cost_summary(self, end_date: Optional[datetime] = None) -> Dict[str, float]:
        """Get cost breakdown for the past 7 days."""
        end = end_date or datetime.now()
        start = end - timedelta(days=7)
        return self._cost_range(start, end)

    def get_monthly_cost_summary(self, end_date: Optional[datetime] = None) -> Dict[str, float]:
        """Get cost breakdown for the past 30 days."""
        end = end_date or datetime.now()
        start = end - timedelta(days=30)
        return self._cost_range(start, end)

    def _cost_range(self, start: datetime, end: datetime) -> Dict[str, float]:
        import sqlite3
        costs: Dict[str, float] = {}
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT model_name, SUM(estimated_cost) FROM llm_costs "
                    "WHERE timestamp >= ? AND timestamp <= ? GROUP BY model_name",
                    (start.isoformat(), end.isoformat())
                )
                for row in cursor.fetchall():
                    family = row[0].split("/")[0] if "/" in row[0] else row[0]
                    costs[family] = costs.get(family, 0.0) + (row[1] or 0.0)
        except Exception as e:
            logger.warning(f"Error getting cost range: {e}")
        return costs

    def get_token_accuracy_report(self) -> dict:
        """Get comparison of estimated vs actual token counts."""
        return self.db.get_token_accuracy_report()

    def get_cost_per_lead(self) -> Dict[str, float]:
        return {"scored": 0.0, "emailed": 0.0}

    def can_afford_claude(self, requested_budget: float) -> bool:
        return True
