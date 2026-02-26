import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging for the module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class LLMCostTracker:
    """
    Placeholder for LLMCostTracker, assumed to exist from US-007.
    Defines the interface expected by LLMDashboardReporter and its tests.
    """
    def get_total_api_calls_for_day(self, date: Optional[datetime] = None) -> Dict[str, int]:
        self.logger.info(f"Mocked get_total_api_calls_for_day called for date: {date}")
        return {"claude": 0, "ollama": 0}

    def get_daily_cost_summary(self, date: Optional[datetime] = None) -> Dict[str, float]:
        self.logger.info(f"Mocked get_daily_cost_summary called for date: {date}")
        return {"claude": 0.0, "ollama": 0.0}

    def get_weekly_cost_summary(self, end_date: Optional[datetime] = None) -> Dict[str, float]:
        self.logger.info(f"Mocked get_weekly_cost_summary called for end_date: {end_date}")
        return {"claude": 0.0, "ollama": 0.0}

    def get_monthly_cost_summary(self, end_date: Optional[datetime] = None) -> Dict[str, float]:
        self.logger.info(f"Mocked get_monthly_cost_summary called for end_date: {end_date}")
        return {"claude": 0.0, "ollama": 0.0}

    def get_cost_per_lead(self) -> Dict[str, float]:
        self.logger.info("Mocked get_cost_per_lead called.")
        return {"scored": 0.0, "emailed": 0.0}

    def __init__(self):
        self.logger = logging.getLogger(__name__)

