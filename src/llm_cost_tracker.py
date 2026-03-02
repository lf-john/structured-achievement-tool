"""
LLM Cost Tracker — Records and queries LLM invocation costs.

Wraps LLMCostDB with token estimation and cost-per-model rates.
"""

import logging
import os
from typing import Dict, Optional
from datetime import datetime, timedelta

from src.db.llm_cost_db import LLMCostDB

logger = logging.getLogger(__name__)

# Approximate cost per 1K tokens (input/output averaged) by model.
# Local models are free. Cloud models use published pricing.
COST_PER_1K_TOKENS = {
    # Claude (Anthropic) — blended input/output estimate
    "claude-opus-4-6": 0.045,
    "claude-sonnet-4-6": 0.012,
    "claude-haiku-4-5-20251001": 0.003,
    # Gemini (Google)
    "gemini-2.5-pro": 0.005,
    "gemini-3.1-pro-preview": 0.005,
    "gemini-3-flash-preview": 0.001,
    "gemini-2.5-flash": 0.001,
    # GLM (z.ai proxy)
    "glm-4.7": 0.002,
    "glm-4.7-flash": 0.0005,
    # Local (Ollama) — free
    "qwen3:8b": 0.0,
    "deepseek-r1:8b": 0.0,
    "qwen2.5-coder:7b": 0.0,
    "nemotron-mini": 0.0,
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
    ):
        """Record a single LLM invocation with estimated cost.

        Args:
            model_id: The model identifier (e.g. 'claude-sonnet-4-6')
            provider_name: Provider name from routing engine (e.g. 'sonnet')
            prompt_chars: Approximate input character count
            output_chars: Output character count
            duration_seconds: Wall-clock time for the invocation
        """
        prompt_tokens = int(prompt_chars / CHARS_PER_TOKEN)
        completion_tokens = int(output_chars / CHARS_PER_TOKEN)
        rate = COST_PER_1K_TOKENS.get(model_id, 0.01)  # default to $0.01/1K if unknown
        estimated_cost = (prompt_tokens + completion_tokens) / 1000.0 * rate

        self.db.add_log_entry(
            model_name=f"{provider_name}/{model_id}",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=estimated_cost,
        )
        logger.debug(
            f"Cost logged: {provider_name}/{model_id} "
            f"~{prompt_tokens}+{completion_tokens} tokens "
            f"= ${estimated_cost:.4f} ({duration_seconds:.1f}s)"
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

    def get_cost_per_lead(self) -> Dict[str, float]:
        return {"scored": 0.0, "emailed": 0.0}

    def can_afford_claude(self, requested_budget: float) -> bool:
        return True
