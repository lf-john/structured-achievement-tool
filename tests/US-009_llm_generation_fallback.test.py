"""
IMPLEMENTATION PLAN for US-009:

Components:
  - src/llm/llm_generation_service.py (NEW):
    - LLMGenerationService class: Orchestrates LLM calls, handles fallback, budget, logging, and notifications.
    - generate_email(agent_name: str, task_description: str) -> str: Main method to generate email content.
    - _call_claude(prompt: str) -> str: Attempts to call the Claude API using cli_runner.
    - _call_qwen3(prompt: str) -> str: Calls the Qwen3 8B API using cli_runner.
    - _check_claude_budget(cost: float) -> bool: Checks budget via llm_cost_tracker.
    - _log_fallback_event(reason: str): Logs fallback.
    - _send_fallback_notification(reason: str): Sends ntfy notification.

Data Flow:
  - User requests email generation via LLMGenerationService.generate_email.
  - Service attempts to call _call_claude.
  - If _call_claude fails (API error, budget exhausted/insufficient), service logs, notifies, and calls _call_qwen3.
  - _call_qwen3 generates content, which is then flagged for human review.
  - Resulting flagged content is returned.

Integration Points:
  - New LLMGenerationService in src/llm/ will be the main entry.
  - src/llm/cli_runner.py: Will be used by LLMGenerationService to execute actual LLM CLI commands.
  - src/llm_cost_tracker.py: Will be used by LLMGenerationService for budget checks.
  - src/notifications/notifier.py: Will be used by LLMGenerationService to send ntfy notifications.
  - Python's built-in logging module.

Edge Cases:
  - Claude API is completely unavailable (connection error, CLI not found, or generic execution error).
  - Claude API returns an explicit error (e.g., authentication failure).
  - Claude budget is zero or insufficient for the current request.
  - Notification sending fails (should not prevent email generation).
  - Logging fails (should not prevent email generation).
  - Qwen3 8B also fails (though the story focuses on fallback *to* Qwen3, not what happens if Qwen3 itself fails). The current tests will assume Qwen3 will always succeed once fallback occurs.

Test Cases:
  1. AC: Fallback to Qwen3 8B for email generation is operational when Claude API is unavailable/budget exhausted.
     - test_should_fallback_to_qwen3_when_claude_cli_fails: Simulate Claude CLI raising an exception.
     - test_should_fallback_to_qwen3_when_claude_budget_exhausted: Simulate llm_cost_tracker indicating zero budget for Claude.
     - test_should_fallback_to_qwen3_when_claude_budget_insufficient_for_request: Simulate llm_cost_tracker indicating insufficient budget for a specific Claude request.
  2. AC: Fallback events are logged.
     - test_should_log_fallback_event_on_claude_cli_failure: Verify logging.warning is called.
     - test_should_log_fallback_event_on_claude_budget_exhaustion: Verify logging.warning is called.
  3. AC: Generated content is flagged for human review during fallback.
     - test_should_flag_qwen3_content_for_review_on_fallback: Assert returned string contains a review flag.
  4. AC: Ntfy notification is sent when fallback triggers.
     - test_should_send_ntfy_notification_on_claude_cli_failure: Verify notifier.send_ntfy is called.
     - test_should_send_ntfy_notification_on_claude_budget_exhaustion: Verify notifier.send_ntfy is called.

Edge Cases (continued):
  - test_should_use_claude_if_available_and_budget_sufficient: Verify happy path, no fallback.
  - test_notification_failure_does_not_stop_generation: Simulate ntfy failure, ensure generation continues.
"""
import pytest
import sys
from unittest.mock import MagicMock, patch

# These imports are expected to fail as the implementation does not exist yet.
from src.llm.llm_generation_service import LLMGenerationService
from src.llm.providers import get_provider
from src.notifications.notifier import Notifier # To mock
from src.llm_cost_tracker import LLMCostTracker # To mock
from src.llm.cli_runner import LLMCLIExecutionError # To simulate Claude API failure

class TestLLMGenerationFallback:

    @pytest.fixture
    def mock_cli_runner(self):
        # Mock cli_runner.py's execute_llm_command (or similar)
        with patch('src.llm.cli_runner.execute_llm_command') as mock_exec:
            yield mock_exec

    @pytest.fixture
    def mock_llm_cost_tracker(self):
        with patch('src.llm_cost_tracker.LLMCostTracker') as mock_tracker_cls:
            mock_tracker_instance = mock_tracker_cls.return_value
            # Default to sufficient budget
            mock_tracker_instance.has_budget_for_model.return_value = True
            yield mock_tracker_instance

    @pytest.fixture
    def mock_notifier(self):
        with patch('src.notifications.notifier.Notifier') as mock_notifier_cls:
            mock_notifier_instance = mock_notifier_cls.return_value
            mock_notifier_instance.send_ntfy.return_value = True # Default success
            yield mock_notifier_instance

    @pytest.fixture
    def mock_logging(self):
        with patch('logging.Logger.warning') as mock_warn:
            yield mock_warn

    @pytest.fixture
    def service(self, mock_cli_runner, mock_llm_cost_tracker, mock_notifier):
        # The LLMGenerationService will be instantiated, passing mocked dependencies.
        # It needs to know about providers, so we mock get_provider as well if it internally uses it.
        with patch('src.llm.llm_generation_service.get_provider', side_effect=get_provider):
            return LLMGenerationService(
                llm_cost_tracker=mock_llm_cost_tracker,
                notifier=mock_notifier
            )

    # --- AC 1: Fallback to Qwen3 8B operational when Claude API unavailable/budget exhausted. ---

    def test_should_fallback_to_qwen3_when_claude_cli_fails(self, service, mock_cli_runner, mock_logging, mock_notifier):
        # Simulate Claude CLI failing (e.g., connection error, CLI not found, generic error)
        mock_cli_runner.side_effect = LLMCLIExecutionError("Claude CLI failed") # Custom exception to simulate CLI failure

        # Mock Qwen3 to return expected content
        # We need to ensure that the mocked call specifically targets qwen3:8b
        def cli_runner_side_effect(*args, **kwargs):
            if 'qwen3:8b' in kwargs.get('model_id', ''):
                return "Generated email content by Qwen3."
            raise LLMCLIExecutionError("Claude CLI failed")

        mock_cli_runner.side_effect = cli_runner_side_effect

        task_description = "Generate a personalized email body."
        generated_content = service.generate_email("test_agent", task_description)

        # Assert Claude was attempted and failed
        assert mock_cli_runner.call_count >= 1 # At least one attempt for Claude
        # Check that Qwen3 was called (implicitly through the side_effect for mock_cli_runner)
        assert "Generated email content by Qwen3." in generated_content
        assert "[HUMAN REVIEW REQUIRED]" in generated_content # AC 3

        # AC 2: Fallback logged
        mock_logging.assert_called_with(
            "Claude API unavailable or failed. Falling back to Qwen3 8B for email generation. Reason: Claude CLI failed."
        )
        # AC 4: Notification sent
        mock_notifier.send_ntfy.assert_called_with(
            title="SAT: LLM Fallback Triggered",
            message="Claude API unavailable or failed for test_agent. Falling back to Qwen3 8B.",
            priority="high",
            tags="warning"
        )

    def test_should_fallback_to_qwen3_when_claude_budget_exhausted(self, service, mock_cli_runner, mock_llm_cost_tracker, mock_logging, mock_notifier):
        # Simulate Claude budget exhausted
        mock_llm_cost_tracker.has_budget_for_model.return_value = False

        # Mock Qwen3 to return expected content
        mock_cli_runner.return_value = "Generated email content by Qwen3."

        task_description = "Generate a personalized email body."
        generated_content = service.generate_email("test_agent", task_description)

        # Assert Claude was not called due to budget, but budget check happened
        mock_llm_cost_tracker.has_budget_for_model.assert_called_with("claude", pytest.approx(service.CLAUDE_EMAIL_COST_ESTIMATE))
        # Assert Qwen3 was called
        mock_cli_runner.assert_called_with(
            provider_config=get_provider("qwen3_8b"),
            prompt=task_description
        )
        assert "[HUMAN REVIEW REQUIRED]" in generated_content # AC 3

        # AC 2: Fallback logged
        mock_logging.assert_called_with(
            f"Claude budget exhausted for test_agent. Falling back to Qwen3 8B for email generation."
        )
        # AC 4: Notification sent
        mock_notifier.send_ntfy.assert_called_with(
            title="SAT: LLM Fallback Triggered",
            message="Claude budget exhausted for test_agent. Falling back to Qwen3 8B.",
            priority="high",
            tags="warning"
        )

    def test_should_fallback_to_qwen3_when_claude_budget_insufficient_for_request(self, service, mock_cli_runner, mock_llm_cost_tracker, mock_logging, mock_notifier):
        # Simulate Claude budget insufficient for this request
        mock_llm_cost_tracker.has_budget_for_model.side_effect = lambda model_name, cost: False if model_name == "claude" and cost > 0 else True

        # Mock Qwen3 to return expected content
        mock_cli_runner.return_value = "Generated email content by Qwen3."

        task_description = "Generate a personalized email body."
        generated_content = service.generate_email("test_agent", task_description)

        # Assert Claude budget check happened
        mock_llm_cost_tracker.has_budget_for_model.assert_called_with("claude", pytest.approx(service.CLAUDE_EMAIL_COST_ESTIMATE))
        # Assert Qwen3 was called
        mock_cli_runner.assert_called_with(
            provider_config=get_provider("qwen3_8b"),
            prompt=task_description
        )
        assert "[HUMAN REVIEW REQUIRED]" in generated_content # AC 3

        # AC 2: Fallback logged
        mock_logging.assert_called_with(
            f"Claude budget insufficient for current request for test_agent. Falling back to Qwen3 8B for email generation."
        )
        # AC 4: Notification sent
        mock_notifier.send_ntfy.assert_called_with(
            title="SAT: LLM Fallback Triggered",
            message="Claude budget insufficient for current request for test_agent. Falling back to Qwen3 8B.",
            priority="high",
            tags="warning"
        )

    # --- Edge Case: Happy Path (no fallback) ---

    def test_should_use_claude_if_available_and_budget_sufficient(self, service, mock_cli_runner, mock_llm_cost_tracker, mock_notifier, mock_logging):
        # Default mocks are set to allow Claude to succeed
        mock_cli_runner.return_value = "Generated email content by Claude."

        task_description = "Generate a personalized email body."
        generated_content = service.generate_email("test_agent", task_description)

        # Assert Claude was called
        mock_cli_runner.assert_called_with(
            provider_config=get_provider("opus"), # Assuming opus is the default Claude
            prompt=task_description
        )
        assert "Generated email content by Claude." == generated_content
        assert "[HUMAN REVIEW REQUIRED]" not in generated_content # Should not be flagged

        # Assert no fallback logging or notification
        mock_logging.assert_not_called()
        mock_notifier.send_ntfy.assert_not_called()

    # --- Edge Case: Notification failure does not stop generation ---
    def test_notification_failure_does_not_stop_generation(self, service, mock_cli_runner, mock_llm_cost_tracker, mock_notifier, mock_logging):
        # Simulate Claude CLI failing to trigger fallback
        mock_cli_runner.side_effect = LLMCLIExecutionError("Claude CLI failed")

        # Mock Qwen3 to return expected content
        def cli_runner_side_effect(*args, **kwargs):
            if 'qwen3:8b' in kwargs.get('model_id', ''):
                return "Generated email content by Qwen3."
            raise LLMCLIExecutionError("Claude CLI failed")
        mock_cli_runner.side_effect = cli_runner_side_effect

        # Simulate ntfy failure
        mock_notifier.send_ntfy.return_value = False

        task_description = "Generate a personalized email body."
        generated_content = service.generate_email("test_agent", task_description)

        # Assert generation still happened and content is flagged
        assert "Generated email content by Qwen3." in generated_content
        assert "[HUMAN REVIEW REQUIRED]" in generated_content
        mock_logging.assert_called() # Fallback logging should still happen
        mock_notifier.send_ntfy.assert_called_once() # Ntfy was attempted

# To ensure the script exits with a non-zero code if tests fail,
# we rely on pytest's default behavior when run from the command line.
# If this script were to be run directly and not via `pytest`,
# we would need to manually handle `sys.exit`. For CLI agent context,
# it's expected `pytest` will be used, which handles exit codes.
