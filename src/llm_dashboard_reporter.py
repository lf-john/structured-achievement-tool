import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging for the module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import LLMCostTracker from its dedicated module
from src.llm_cost_tracker import LLMCostTracker
# Import the actual OllamaGPUMonitor
from src.ollama_gpu_monitor import OllamaGPUMonitor

class LLMDashboardReporter:
    """
    Aggregates LLM cost and GPU utilization data and formats it into a report.
    """
    def __init__(self, cost_tracker: LLMCostTracker, gpu_monitor: OllamaGPUMonitor):
        self.cost_tracker = cost_tracker
        self.gpu_monitor = gpu_monitor
        self.logger = logging.getLogger(__name__)

    def generate_report(self) -> Dict[str, Any]:
        """
        Collects data and returns a structured report of LLM costs and GPU utilization.
        """
        report = {}
        today = datetime.now()

        # Total API Calls Per Day
        try:
            report["api_calls_per_day"] = self.cost_tracker.get_total_api_calls_for_day(date=today)
        except Exception as e:
            self.logger.error(f"Error retrieving API calls per day: {e}")
            report["api_calls_per_day"] = {"claude": 0, "ollama": 0}

        # Estimated Claude Cost (Daily, Weekly, Monthly)
        try:
            daily_cost = self.cost_tracker.get_daily_cost_summary(date=today).get("claude", 0.0)
            weekly_cost = self.cost_tracker.get_weekly_cost_summary(end_date=today).get("claude", 0.0)
            monthly_cost = self.cost_tracker.get_monthly_cost_summary(end_date=today).get("claude", 0.0)
            report["estimated_claude_cost"] = {
                "daily": daily_cost,
                "weekly": weekly_cost,
                "monthly": monthly_cost
            }
        except Exception as e:
            self.logger.error(f"Error retrieving estimated Claude cost: {e}")
            report["estimated_claude_cost"] = {"daily": 0.0, "weekly": 0.0, "monthly": 0.0}

        # Cost per Lead Scored/Emailed
        try:
            report["cost_per_lead"] = self.cost_tracker.get_cost_per_lead()
        except Exception as e:
            self.logger.error(f"Error retrieving cost per lead: {e}")
            report["cost_per_lead"] = {"scored": 0.0, "emailed": 0.0}

        # Ollama GPU Utilization
        try:
            report["ollama_gpu_utilization"] = self.gpu_monitor.get_gpu_utilization()
        except Exception as e:
            self.logger.error(f"Error retrieving Ollama GPU utilization: {e}")
            report["ollama_gpu_utilization"] = 0.0

        return report
