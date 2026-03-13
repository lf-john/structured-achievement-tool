"""
RAG Summary Layer — Phase 3 item 3.6.

Summarizes top-K RAG search results using local Qwen3 0.6B before feeding
to the main LLM, reducing token consumption by condensing verbose results
into a focused Context Brief.
"""

import logging
import subprocess

logger = logging.getLogger(__name__)

# Maximum characters to include per RAG result in the summarization prompt.
# Keeps prompt size bounded even when individual results are very long.
_MAX_CHARS_PER_RESULT = 1500


class RAGSummarizer:
    """Summarizes top-K RAG results using local Qwen3 0.6B before feeding to main LLM.

    Reduces token consumption by condensing verbose RAG results into a focused
    Context Brief. Uses Ollama's qwen3:0.6b model (already installed locally).
    """

    def __init__(self, model: str = "qwen3:0.6b", max_brief_tokens: int = 500):
        """Initialize the RAG summarizer.

        Args:
            model: Ollama model name for summarization.
            max_brief_tokens: Target maximum tokens for the Context Brief output.
        """
        self.model = model
        self.max_brief_tokens = max_brief_tokens

    def summarize(self, rag_results: list[dict], query: str) -> str:
        """Summarize RAG results into a Context Brief.

        Args:
            rag_results: List of dicts with 'text' and 'score' keys
                         (from VectorStore.search).
            query: The original search query for context.

        Returns:
            Context Brief string suitable for injection into main LLM prompt.
            Returns empty string when there are no results.
        """
        if not rag_results:
            return ""

        prompt = self._build_summarization_prompt(rag_results, query)
        summary = self._invoke_ollama(prompt)

        if not summary:
            # Fallback: simple truncation when Ollama is unavailable
            summary = self._fallback_truncation(rag_results)
            logger.warning("Ollama unavailable for RAG summarization; using truncation fallback")

        return self._format_context_brief(summary, len(rag_results))

    def _build_summarization_prompt(self, rag_results: list[dict], query: str) -> str:
        """Build the prompt for Qwen3 to summarize RAG results.

        Args:
            rag_results: List of RAG result dicts.
            query: The original search query.

        Returns:
            A prompt string ready to send to Ollama.
        """
        parts = [
            "You are a concise technical summarizer. A user searched for context ",
            f'related to: "{query}"\n\n',
            f"Below are {len(rag_results)} relevant document(s) retrieved from memory. ",
            "Summarize the key insights, decisions, and relevant context into a ",
            f"brief of at most {self.max_brief_tokens} tokens. ",
            "Focus on information directly useful for the query. ",
            "Omit boilerplate and redundant details. ",
            "Do NOT include any thinking tags or reasoning traces.\n\n",
        ]

        for i, result in enumerate(rag_results, 1):
            text = result.get("text", "")
            score = result.get("score", 0.0)
            # Truncate very long results to keep prompt bounded
            if len(text) > _MAX_CHARS_PER_RESULT:
                text = text[:_MAX_CHARS_PER_RESULT] + "..."
            parts.append(f"--- Result {i} (similarity: {score:.3f}) ---\n")
            parts.append(text)
            parts.append("\n\n")

        parts.append("--- End of results ---\n\n")
        parts.append("Provide a concise summary now:")

        return "".join(parts)

    def _invoke_ollama(self, prompt: str) -> str:
        """Call Ollama qwen3:0.6b via subprocess.

        Uses stdin pipe to pass the prompt, avoiding shell escaping issues
        with long prompts.

        Args:
            prompt: The full prompt string.

        Returns:
            Response text from Ollama, or empty string on failure.
        """
        try:
            res = subprocess.run(
                ["ollama", "run", self.model],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0:
                response = res.stdout.strip()
                # Strip any <think>...</think> blocks Qwen3 may emit
                response = self._strip_think_tags(response)
                return response
            logger.warning("Ollama returned exit code %d: %s", res.returncode, res.stderr)
            return ""
        except subprocess.TimeoutExpired:
            logger.error("Ollama timed out during RAG summarization (30s)")
            return ""
        except OSError as e:
            logger.error("Failed to invoke ollama: %s", e)
            return ""

    def _strip_think_tags(self, text: str) -> str:
        """Remove <think>...</think> blocks that Qwen3 may emit.

        Args:
            text: Raw model output.

        Returns:
            Text with thinking traces removed.
        """
        import re

        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def _fallback_truncation(self, rag_results: list[dict]) -> str:
        """Simple truncation fallback when Ollama is unavailable.

        Concatenates the first 500 characters of each result.

        Args:
            rag_results: List of RAG result dicts.

        Returns:
            Concatenated truncated text.
        """
        parts = []
        for result in rag_results:
            text = result.get("text", "")
            if text:
                parts.append(text[:500])
        return "\n\n".join(parts)

    def _format_context_brief(self, summary: str, result_count: int) -> str:
        """Format the summary as a structured Context Brief.

        Args:
            summary: The summarized text.
            result_count: Number of RAG results that were summarized.

        Returns:
            Formatted Context Brief string.
        """
        return f"## Context Brief (from {result_count} similar task{'s' if result_count != 1 else ''})\n\n{summary}"
