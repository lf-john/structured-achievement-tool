import logging
from src.notifications.notifier import Notifier
from src.llm_cost_tracker import LLMCostTracker
from src.llm.cli_runner import execute_llm_command, LLMCLIExecutionError
from src.llm.providers import get_provider

# Configure logging for the module
logger = logging.getLogger(__name__)

class LLMGenerationService:
    CLAUDE_EMAIL_COST_ESTIMATE = 0.01  # Placeholder cost estimate for Claude email generation

    def __init__(self, llm_cost_tracker: LLMCostTracker, notifier: Notifier):
        self.llm_cost_tracker = llm_cost_tracker
        self.notifier = notifier

    def generate_email(self, agent_name: str, task_description: str) -> str:
        claude_provider = get_provider("opus") # Assuming opus is the default Claude
        qwen3_provider = get_provider("qwen3_8b")

        # 1. Check Claude budget
        if not self._check_claude_budget(agent_name):
            reason = f"Claude budget exhausted for {agent_name}."
            self._log_fallback_event(agent_name, reason)
            self._send_fallback_notification(agent_name, reason)
            return self._call_qwen3(task_description)

        # 2. Attempt to call Claude
        try:
            claude_output = self._call_claude(task_description, agent_name)
            self.llm_cost_tracker.record_cost("claude", self.CLAUDE_EMAIL_COST_ESTIMATE)
            return claude_output
        except LLMCLIExecutionError as e:
            reason = f"Claude API unavailable or failed. Reason: {e}"
            self._log_fallback_event(agent_name, reason)
            self._send_fallback_notification(agent_name, reason)
            return self._call_qwen3(task_description)
        except Exception as e:
            # Catch any other unexpected errors during Claude call
            reason = f"Unexpected error during Claude API call: {e}"
            self._log_fallback_event(agent_name, reason)
            self._send_fallback_notification(agent_name, reason)
            return self._call_qwen3(task_description)

    def _call_claude(self, prompt: str, agent_name: str) -> str:
        # This method attempts to call the Claude API.
        # It's separated for clarity and potential future specific Claude error handling.
        claude_provider = get_provider("opus")
        return execute_llm_command(provider_config=claude_provider, prompt=prompt)

    def _call_qwen3(self, prompt: str) -> str:
        # This method calls the Qwen3 8B API and flags content for human review.
        qwen3_provider = get_provider("qwen3_8b")
        qwen3_output = execute_llm_command(provider_config=qwen3_provider, prompt=prompt)
        return f"[HUMAN REVIEW REQUIRED] {qwen3_output}"

    def _check_claude_budget(self, agent_name: str) -> bool:
        # Check if there's enough budget for Claude for this specific email generation
        if not self.llm_cost_tracker.has_budget_for_model("claude", self.CLAUDE_EMAIL_COST_ESTIMATE):
            # Differentiate between exhausted and insufficient for current request
            if self.llm_cost_tracker.get_current_budget("claude") <= 0:
                logger.warning(f"Claude budget exhausted for {agent_name}. Falling back to Qwen3 8B for email generation.")
                return False
            else:
                logger.warning(f"Claude budget insufficient for current request for {agent_name}. Falling back to Qwen3 8B for email generation.")
                return False
        return True

    def _log_fallback_event(self, agent_name: str, reason: str):
        logger.warning(f"Claude API unavailable or failed. Falling back to Qwen3 8B for email generation. Reason: {reason}.")

    def _send_fallback_notification(self, agent_name: str, reason: str):
        try:
            self.notifier.send_ntfy(
                title="SAT: LLM Fallback Triggered",
                message=f"Claude API unavailable or failed for {agent_name}. Falling back to Qwen3 8B. {reason}",
                priority="high",
                tags="warning"
            )
        except Exception as e:
            logger.error(f"Failed to send ntfy notification about LLM fallback: {e}")
