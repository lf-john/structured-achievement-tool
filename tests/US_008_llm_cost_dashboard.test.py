"""
IMPLEMENTATION PLAN for US-008:

Components:
  - src/llm_dashboard_reporter.py:
    - LLMDashboardReporter class: Aggregates LLM cost and GPU utilization data and formats it into a report.
      - __init__(cost_tracker: LLMCostTracker, gpu_monitor: OllamaGPUMonitor): Initializes with dependencies.
      - generate_report() -> dict: Collects data and returns a structured report.
      - _get_daily_metrics() -> dict: Retrieves daily cost metrics.
      - _get_weekly_metrics() -> dict: Retrieves weekly cost metrics.
      - _get_monthly_metrics() -> dict: Retrieves monthly cost metrics.
      - _get_cost_per_lead() -> dict: Calculates cost per lead scored/emailed.
  - src/ollama_gpu_monitor.py:
    - OllamaGPUMonitor class: Monitors Ollama GPU utilization.
      - __init__(): Initializes the monitor.
      - get_gpu_utilization() -> float: Returns current GPU utilization (0.0-1.0).

Test Cases:
  1. [AC 1] -> test_should_display_total_api_calls_per_day: Verifies the report includes total API calls per day.
  2. [AC 1] -> test_should_display_estimated_claude_cost_daily_weekly_monthly: Verifies the report includes estimated Claude API cost for daily, weekly, and monthly periods.
  3. [AC 1] -> test_should_display_cost_per_lead_scored_emailed: Verifies the report includes cost per lead scored/emailed.
  4. [AC 2] -> test_should_display_ollama_gpu_utilization: Verifies the report includes Ollama GPU utilization.
  5. [AC 2] -> test_ollama_gpu_monitor_should_parse_nvidia_smi_output: Tests OllamaGPUMonitor's ability to parse GPU utilization.

Edge Cases:
  - test_should_handle_no_llm_calls_recorded: Report gracefully handles no LLM calls.
  - test_ollama_gpu_monitor_should_handle_nvidia_smi_error: OllamaGPUMonitor handles `nvidia-smi` errors gracefully.
  - test_should_handle_zero_cost_per_lead_when_no_leads: Report handles zero cost per lead when no leads are available.
"""
import pytest
from unittest.mock import MagicMock, patch
import sys

# These imports will fail because the modules/classes do not exist yet
from src.llm_dashboard_reporter import LLMDashboardReporter
from src.ollama_gpu_monitor import OllamaGPUMonitor
from src.llm_cost_tracker import LLMCostTracker # Assuming this exists from US-007

class TestLLMDashboardReporter:

    @pytest.fixture
    def mock_cost_tracker(self):
        mock = MagicMock(spec=LLMCostTracker)
        mock.get_total_api_calls_for_day.return_value = {"claude": 10, "ollama": 5}
        mock.get_daily_cost_summary.return_value = {"claude": 1.50, "ollama": 0.05}
        mock.get_weekly_cost_summary.return_value = {"claude": 10.50, "ollama": 0.35}
        mock.get_monthly_cost_summary.return_value = {"claude": 45.00, "ollama": 1.50}
        # Assuming a method for cost per lead, to be implemented in LLMCostTracker or another module
        mock.get_cost_per_lead.return_value = {"scored": 0.25, "emailed": 0.15}
        return mock

    @pytest.fixture
    def mock_gpu_monitor(self):
        mock = MagicMock(spec=OllamaGPUMonitor)
        mock.get_gpu_utilization.return_value = 0.75 # 75% utilization
        return mock

    @pytest.fixture
    def reporter(self, mock_cost_tracker, mock_gpu_monitor):
        return LLMDashboardReporter(cost_tracker=mock_cost_tracker, gpu_monitor=mock_gpu_monitor)

    # AC 1: Dashboard/report displays specified cost metrics.
    def test_should_display_total_api_calls_per_day(self, reporter):
        report = reporter.generate_report()
        assert "api_calls_per_day" in report
        assert report["api_calls_per_day"]["claude"] == 10
        assert report["api_calls_per_day"]["ollama"] == 5

    def test_should_display_estimated_claude_cost_daily_weekly_monthly(self, reporter):
        report = reporter.generate_report()
        assert "estimated_claude_cost" in report
        assert report["estimated_claude_cost"]["daily"] == 1.50
        assert report["estimated_claude_cost"]["weekly"] == 10.50
        assert report["estimated_claude_cost"]["monthly"] == 45.00

    def test_should_display_cost_per_lead_scored_emailed(self, reporter):
        report = reporter.generate_report()
        assert "cost_per_lead" in report
        assert report["cost_per_lead"]["scored"] == 0.25
        assert report["cost_per_lead"]["emailed"] == 0.15

    # AC 2: Ollama GPU utilization is tracked and displayed.
    def test_should_display_ollama_gpu_utilization(self, reporter):
        report = reporter.generate_report()
        assert "ollama_gpu_utilization" in report
        assert report["ollama_gpu_utilization"] == 0.75

    # Edge Cases for LLMDashboardReporter
    def test_should_handle_no_llm_calls_recorded(self, mock_cost_tracker, mock_gpu_monitor, reporter):
        mock_cost_tracker.get_total_api_calls_for_day.return_value = {"claude": 0, "ollama": 0}
        mock_cost_tracker.get_daily_cost_summary.return_value = {"claude": 0.0, "ollama": 0.0}
        mock_cost_tracker.get_weekly_cost_summary.return_value = {"claude": 0.0, "ollama": 0.0}
        mock_cost_tracker.get_monthly_cost_summary.return_value = {"claude": 0.0, "ollama": 0.0}
        mock_cost_tracker.get_cost_per_lead.return_value = {"scored": 0.0, "emailed": 0.0}
        mock_gpu_monitor.get_gpu_utilization.return_value = 0.0 # No utilization

        report = reporter.generate_report()
        assert report["api_calls_per_day"]["claude"] == 0
        assert report["estimated_claude_cost"]["daily"] == 0.0
        assert report["cost_per_lead"]["scored"] == 0.0
        assert report["ollama_gpu_utilization"] == 0.0

    def test_should_handle_zero_cost_per_lead_when_no_leads(self, mock_cost_tracker, mock_gpu_monitor, reporter):
        mock_cost_tracker.get_cost_per_lead.return_value = {"scored": 0.0, "emailed": 0.0}
        report = reporter.generate_report()
        assert report["cost_per_lead"]["scored"] == 0.0
        assert report["cost_per_lead"]["emailed"] == 0.0

class TestOllamaGPUMonitor:

    @pytest.fixture
    def gpu_monitor(self):
        return OllamaGPUMonitor()

    # AC 2: Ollama GPU utilization is tracked and displayed. (testing monitor directly)
    @patch('default_api.run_shell_command')
    def test_ollama_gpu_monitor_should_parse_nvidia_smi_output(self, mock_run_shell_command, gpu_monitor):
        # Simulate nvidia-smi output
        mock_run_shell_command.return_value = {
            "output": """
            +---------------------------------------------------------------------------------------+
            | NVIDIA-SMI 535.154.05             Driver Version: 535.154.05   CUDA Version: 12.2     |
            |-----------------------------------------+----------------------+----------------------+
            | GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
            | Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
            |                                         |                      |               MIG M. |
            |=========================================+======================+======================|
            |   0  NVIDIA GeForce RTX 3090        Off | 00000000:01:00.0 Off |                  N/A |
            | 30%   45C    P2             100W / 350W |   10000MiB / 24576MiB |     75%      Default |
            |                                         |                      |                  N/A |
            +-----------------------------------------+----------------------+----------------------+
            """
        }
        utilization = gpu_monitor.get_gpu_utilization()
        mock_run_shell_command.assert_called_once_with(command="nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits", description="Get Ollama GPU utilization")
        assert utilization == 0.75 # 75% as float

    @patch('default_api.run_shell_command')
    def test_ollama_gpu_monitor_should_handle_nvidia_smi_error(self, mock_run_shell_command, gpu_monitor):
        mock_run_shell_command.return_value = {
            "error": "Command failed",
            "exit_code": 1
        }
        utilization = gpu_monitor.get_gpu_utilization()
        assert utilization == 0.0 # Should return 0.0 on error or parsing failure

    @patch('default_api.run_shell_command')
    def test_ollama_gpu_monitor_should_handle_empty_nvidia_smi_output(self, mock_run_shell_command, gpu_monitor):
        mock_run_shell_command.return_value = {
            "output": ""
        }
        utilization = gpu_monitor.get_gpu_utilization()
        assert utilization == 0.0 # Should return 0.0 on empty output

# No explicit sys.exit needed, pytest handles exit codes.
