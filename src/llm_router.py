
import logging

from src.core.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class LLMRouter:
    def __init__(self):
        self.embedding_service = EmbeddingService()

    def _is_ollama_task(self, task_description: str) -> bool:
        """Determines if a task should be routed to Ollama based on keywords."""
        ollama_keywords = [
            "lead scoring", "industry classification", "classify industries",
            "company size estimation", "estimate company sizes",
            "email subject line", "a/b testing", "subject line variant selection",
            "sentiment analysis",
            "contact deduplication", "deduplicate contact lists",
            "simple text summarization", "summarize", "summarization"
        ]
        task_description_lower = task_description.lower()
        return any(keyword in task_description_lower for keyword in ollama_keywords)

    def _is_claude_task(self, task_description: str) -> bool:
        """Determines if a task should be routed to Claude based on keywords."""
        claude_keywords = [
            "personalized email body generation", "multi-paragraph outreach sequences",
            "complex analysis", "prospect-facing content"
        ]
        task_description_lower = task_description.lower()
        return any(keyword in task_description_lower for keyword in claude_keywords)

    def classify_and_route(self, task_description: str) -> str:
        """
        Classifies an incoming task and routes it to either 'ollama' or 'claude'
        based on complexity and cost considerations.
        """
        if not task_description or not isinstance(task_description, str):
            logger.warning("Empty or invalid task description provided. Defaulting to Claude.")
            return "claude"

        is_ollama = self._is_ollama_task(task_description)
        is_claude = self._is_claude_task(task_description)

        if is_claude:
            return "claude"
        elif is_ollama:
            if not self.embedding_service.check_ollama_health():
                logger.warning("Ollama is unavailable, routing Ollama-bound task to 'ollama_unavailable'.")
                return "ollama_unavailable"
            return "ollama"
        else:
            # Default to Claude for ambiguous or complex tasks not explicitly matching Ollama
            logger.info(f"Ambiguous task description: '{task_description}'. Defaulting to Claude.")
            return "claude"
