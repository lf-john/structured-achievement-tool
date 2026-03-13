import logging

from src.llm.cli_runner import CLIRunner, LLMCLIExecutionError
from src.llm.providers import get_provider
from src.llm_cost_tracker import LLMCostTracker
from src.notifications.notifier import Notifier

logger = logging.getLogger(__name__)


class LLMGenerationService:
    CLAUDE_EMAIL_COST_ESTIMATE = 0.01  # Placeholder cost, adjust as needed based on actual Claude pricing for emails

    def __init__(self, llm_cost_tracker: LLMCostTracker, notifier: Notifier, cli_runner: CLIRunner = None):
        self.llm_cost_tracker = llm_cost_tracker
        self.notifier = notifier
        self.cli_runner = cli_runner or CLIRunner()

    def generate_email(self, agent_name: str, task_description: str) -> tuple[str, bool]:
        """
        Generates email content using Claude with fallback to Qwen3 8B.
        Returns a tuple: (generated_content, requires_human_review)
        """
        requires_human_review = False
        generated_content = ""

        claude_provider_config = get_provider("opus")  # Assuming 'opus' is the default Claude model
        get_provider("qwen3_8b")

        try:
            # Check Claude budget
            if not self.llm_cost_tracker.can_afford_claude(self.CLAUDE_EMAIL_COST_ESTIMATE):
                reason = f"Claude budget exhausted for {agent_name}"
                logger.warning(f"{reason}. Falling back to Qwen3 8B for email generation.")
                self._send_fallback_notification(agent_name, reason)
                return self._fallback_to_qwen3(task_description)

            # Attempt to generate with Claude
            generated_content = self.cli_runner.execute_llm_command(
                provider_config=claude_provider_config, prompt=task_description
            )
            return generated_content, requires_human_review
        except LLMCLIExecutionError as e:
            reason = f"Claude API unavailable or failed for {agent_name}. Reason: {e}"
            logger.warning(f"{reason}. Falling back to Qwen3 8B for email generation.")
            self._send_fallback_notification(agent_name, reason)
            return self._fallback_to_qwen3(task_description)
        except Exception as e:
            reason = f"An unexpected error occurred with Claude for {agent_name}: {e}"
            logger.error(f"{reason}. Falling back to Qwen3 8B for email generation.")
            self._send_fallback_notification(agent_name, reason)
            return self._fallback_to_qwen3(task_description)

    def _fallback_to_qwen3(self, prompt: str) -> tuple[str, bool]:
        """Handles fallback to Qwen3 8B."""
        requires_human_review = True
        qwen3_provider_config = get_provider("qwen3_8b")
        generated_content = self.cli_runner.execute_llm_command(provider_config=qwen3_provider_config, prompt=prompt)
        logger.info("Content generated with Qwen3 8B. Flagged for human review.")
        return f"[HUMAN REVIEW REQUIRED] {generated_content}", requires_human_review

    def _send_fallback_notification(self, agent_name: str, reason: str):
        """Sends an ntfy notification about the fallback event."""
        title = "SAT: LLM Fallback Triggered"
        message = f"{reason}. Falling back to Qwen3 8B."
        self.notifier.send_ntfy(title=title, message=message, priority="high", tags="warning")
