import logging
from typing import Dict, Any

# Assuming LLMCostTracker and OllamaGPUMonitor are available in src
from src.llm_cost_tracker import LLMCostTracker
from src.ollama_gpu_monitor import OllamaGPUMonitor

logger = logging.getLogger(__name__)

class LLMDashboardReporter:
    def __init__(self, cost_tracker: LLMCostTracker, gpu_monitor: OllamaGPUMonitor):
        self.cost_tracker = cost_tracker
        self.gpu_monitor = gpu_monitor

    def generate_report(self) -> Dict[str, Any]:
        """
        Generates a comprehensive report including LLM API calls, estimated costs,
        cost per lead, and Ollama GPU utilization.
        """
        report = {}

        try:
            report["api_calls_per_day"] = self.cost_tracker.get_total_api_calls_for_day()
        except Exception as e:
            logger.error(f"Error getting total API calls per day: {e}")
            report["api_calls_per_day"] = {"claude": 0, "ollama": 0}

        try:
            report["estimated_claude_cost"] = {
                "daily": self.cost_tracker.get_daily_cost_summary().get("claude", 0.0),
                "weekly": self.cost_tracker.get_weekly_cost_summary().get("claude", 0.0),
                "monthly": self.cost_tracker.get_monthly_cost_summary().get("claude", 0.0)
            }
        except Exception as e:
            logger.error(f"Error getting estimated Claude cost: {e}")
            report["estimated_claude_cost"] = {"daily": 0.0, "weekly": 0.0, "monthly": 0.0}

        try:
            report["cost_per_lead"] = self.cost_tracker.get_cost_per_lead()
        except Exception as e:
            logger.error(f"Error getting cost per lead: {e}")
            report["cost_per_lead"] = {"scored": 0.0, "emailed": 0.0}

        try:
            report["ollama_gpu_utilization"] = self.gpu_monitor.get_gpu_utilization()
        except Exception as e:
            logger.error(f"Error getting Ollama GPU utilization: {e}")
            report["ollama_gpu_utilization"] = 0.0

        return report
