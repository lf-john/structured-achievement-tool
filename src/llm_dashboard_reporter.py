import logging
from src.llm_cost_tracker import LLMCostTracker
from src.ollama_gpu_monitor import OllamaGPUMonitor

logger = logging.getLogger(__name__)

class LLMDashboardReporter:
    def __init__(self, cost_tracker: LLMCostTracker, gpu_monitor: OllamaGPUMonitor):
        self.cost_tracker = cost_tracker
        self.gpu_monitor = gpu_monitor

    def generate_report(self) -> dict:
        report = {
            "api_calls_per_day": self._get_daily_metrics(),
            "estimated_claude_cost": {
                "daily": self._get_daily_claude_cost(),
                "weekly": self._get_weekly_claude_cost(),
                "monthly": self._get_monthly_claude_cost(),
            },
            "cost_per_lead": self._get_cost_per_lead(),
            "ollama_gpu_utilization": self.gpu_monitor.get_gpu_utilization()
        }
        return report

    def _get_daily_metrics(self) -> dict:
        return self.cost_tracker.get_total_api_calls_for_day()

    def _get_daily_claude_cost(self) -> float:
        daily_summary = self.cost_tracker.get_daily_cost_summary()
        return daily_summary.get("claude", 0.0)

    def _get_weekly_claude_cost(self) -> float:
        weekly_summary = self.cost_tracker.get_weekly_cost_summary()
        return weekly_summary.get("claude", 0.0)

    def _get_monthly_claude_cost(self) -> float:
        monthly_summary = self.cost_tracker.get_monthly_cost_summary()
        return monthly_summary.get("claude", 0.0)

    def _get_cost_per_lead(self) -> dict:
        # Assuming LLMCostTracker has a method get_cost_per_lead
        return self.cost_tracker.get_cost_per_lead()
