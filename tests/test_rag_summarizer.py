"""
Tests for RAGSummarizer — Phase 3 item 3.6 RAG Summary Layer.

Uses pytest + unittest.mock. All Ollama subprocess calls are mocked.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.core.rag_summarizer import _MAX_CHARS_PER_RESULT, RAGSummarizer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def summarizer():
    """Create a RAGSummarizer with default settings."""
    return RAGSummarizer()


@pytest.fixture
def summarizer_custom():
    """Create a RAGSummarizer with custom model and token limit."""
    return RAGSummarizer(model="qwen3:latest", max_brief_tokens=300)


@pytest.fixture
def single_result():
    """A single RAG search result."""
    return [
        {
            "text": "Task 001: Configured SuiteCRM email with SES SMTP relay. "
                    "Verified DKIM signatures and SPF records.",
            "score": 0.92,
            "id": 1,
            "metadata": {"task": "001"},
        }
    ]


@pytest.fixture
def multiple_results():
    """Multiple RAG search results with varying scores."""
    return [
        {
            "text": "Task 001: Set up SuiteCRM Docker container with MariaDB. "
                    "Configured reverse proxy on port 8088.",
            "score": 0.95,
            "id": 1,
            "metadata": {"task": "001"},
        },
        {
            "text": "Task 003: Integrated Mautic with SuiteCRM via API sync. "
                    "Contacts flow bidirectionally every 15 minutes.",
            "score": 0.88,
            "id": 3,
            "metadata": {"task": "003"},
        },
        {
            "text": "Task 005: Configured N8N LLM routing for lead enrichment. "
                    "Uses Qwen3 for classification, Claude for complex tasks.",
            "score": 0.72,
            "id": 5,
            "metadata": {"task": "005"},
        },
    ]


def _mock_ollama_success(summary_text="This is a summary of the RAG results."):
    """Return a mock subprocess.run result for a successful Ollama call."""
    return MagicMock(
        returncode=0,
        stdout=summary_text + "\n",
        stderr="",
    )


# ---------------------------------------------------------------------------
# Normal Summarization Flow
# ---------------------------------------------------------------------------

class TestSummarizeNormal:
    def test_summarize_returns_context_brief(self, summarizer, multiple_results):
        """summarize() returns a formatted Context Brief on success."""
        with patch("subprocess.run", return_value=_mock_ollama_success()):
            result = summarizer.summarize(multiple_results, "SuiteCRM setup")

        assert result.startswith("## Context Brief")
        assert "3 similar tasks" in result
        assert "This is a summary" in result

    def test_summarize_single_result(self, summarizer, single_result):
        """Context Brief uses singular 'task' for one result."""
        with patch("subprocess.run", return_value=_mock_ollama_success()):
            result = summarizer.summarize(single_result, "email config")

        assert "1 similar task)" in result
        assert "tasks)" not in result

    def test_summarize_passes_query_to_prompt(self, summarizer, single_result):
        """The query string is included in the prompt sent to Ollama."""
        with patch("subprocess.run", return_value=_mock_ollama_success()) as mock_run:
            summarizer.summarize(single_result, "DKIM configuration")

        call_args = mock_run.call_args
        prompt_input = call_args.kwargs.get("input") or call_args[1].get("input", "")
        assert "DKIM configuration" in prompt_input

    def test_summarize_pipes_prompt_via_stdin(self, summarizer, single_result):
        """Ollama is invoked with stdin pipe, not command-line prompt."""
        with patch("subprocess.run", return_value=_mock_ollama_success()) as mock_run:
            summarizer.summarize(single_result, "test query")

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        # Command should be just ["ollama", "run", "qwen3:8b"] without prompt in args
        assert cmd == ["ollama", "run", "qwen3:8b"]
        # Prompt is passed via input kwarg
        assert "input" in call_args.kwargs or "input" in (call_args[1] if len(call_args) > 1 else {})

    def test_summarize_uses_custom_model(self, summarizer_custom, single_result):
        """Custom model name is passed to the Ollama command."""
        with patch("subprocess.run", return_value=_mock_ollama_success()) as mock_run:
            summarizer_custom.summarize(single_result, "test")

        cmd = mock_run.call_args[0][0]
        assert cmd == ["ollama", "run", "qwen3:latest"]


# ---------------------------------------------------------------------------
# Empty Results Handling
# ---------------------------------------------------------------------------

class TestSummarizeEmpty:
    def test_empty_results_returns_empty_string(self, summarizer):
        """summarize() returns empty string for empty results list."""
        result = summarizer.summarize([], "any query")
        assert result == ""

    def test_empty_results_does_not_call_ollama(self, summarizer):
        """No Ollama invocation when results are empty."""
        with patch("subprocess.run") as mock_run:
            summarizer.summarize([], "any query")
        mock_run.assert_not_called()

    def test_results_with_empty_text(self, summarizer):
        """Results with empty text fields are handled gracefully."""
        results = [{"text": "", "score": 0.5}]
        with patch("subprocess.run", return_value=_mock_ollama_success()):
            result = summarizer.summarize(results, "query")
        assert "## Context Brief" in result


# ---------------------------------------------------------------------------
# Ollama Failure Fallback
# ---------------------------------------------------------------------------

class TestOllamaFallback:
    def test_nonzero_exit_code_uses_fallback(self, summarizer, single_result):
        """Non-zero Ollama exit code triggers truncation fallback."""
        mock_result = MagicMock(returncode=1, stdout="", stderr="model not found")
        with patch("subprocess.run", return_value=mock_result):
            result = summarizer.summarize(single_result, "test")

        assert "## Context Brief" in result
        # Fallback includes raw truncated text
        assert "SuiteCRM" in result

    def test_timeout_uses_fallback(self, summarizer, single_result):
        """Timeout triggers truncation fallback."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ollama", 30)):
            result = summarizer.summarize(single_result, "test")

        assert "## Context Brief" in result
        assert "SuiteCRM" in result

    def test_oserror_uses_fallback(self, summarizer, single_result):
        """OSError (e.g., ollama not installed) triggers truncation fallback."""
        with patch("subprocess.run", side_effect=OSError("No such file")):
            result = summarizer.summarize(single_result, "test")

        assert "## Context Brief" in result

    def test_fallback_truncates_to_500_chars(self, summarizer):
        """Fallback truncates each result to 500 characters."""
        long_text = "A" * 1000
        results = [{"text": long_text, "score": 0.9}]
        with patch("subprocess.run", side_effect=OSError("not found")):
            result = summarizer.summarize(results, "test")

        # The fallback text within the brief should be 500 A's, not 1000
        brief_body = result.split("\n\n", 1)[1]  # After the header
        assert len(brief_body) == 500

    def test_fallback_joins_multiple_results(self, summarizer, multiple_results):
        """Fallback concatenates truncated text from all results."""
        with patch("subprocess.run", side_effect=OSError("not found")):
            result = summarizer.summarize(multiple_results, "test")

        # All three results should appear in fallback
        assert "SuiteCRM Docker" in result
        assert "Mautic" in result
        assert "N8N" in result


# ---------------------------------------------------------------------------
# Prompt Building
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_prompt_contains_query(self, summarizer):
        """Prompt includes the original search query."""
        results = [{"text": "some text", "score": 0.8}]
        prompt = summarizer._build_summarization_prompt(results, "email setup")
        assert "email setup" in prompt

    def test_prompt_contains_result_count(self, summarizer, multiple_results):
        """Prompt mentions the number of results."""
        prompt = summarizer._build_summarization_prompt(multiple_results, "test")
        assert "3 relevant document" in prompt

    def test_prompt_contains_result_text(self, summarizer, single_result):
        """Prompt includes the text from each result."""
        prompt = summarizer._build_summarization_prompt(single_result, "test")
        assert "SuiteCRM email" in prompt
        assert "DKIM signatures" in prompt

    def test_prompt_contains_similarity_scores(self, summarizer, multiple_results):
        """Prompt includes similarity scores for each result."""
        prompt = summarizer._build_summarization_prompt(multiple_results, "test")
        assert "0.950" in prompt
        assert "0.880" in prompt
        assert "0.720" in prompt

    def test_prompt_includes_token_limit(self, summarizer):
        """Prompt instructs the model about the token limit."""
        results = [{"text": "text", "score": 0.5}]
        prompt = summarizer._build_summarization_prompt(results, "q")
        assert "500 tokens" in prompt

    def test_prompt_custom_token_limit(self, summarizer_custom):
        """Custom max_brief_tokens is reflected in prompt."""
        results = [{"text": "text", "score": 0.5}]
        prompt = summarizer_custom._build_summarization_prompt(results, "q")
        assert "300 tokens" in prompt

    def test_prompt_truncates_long_results(self, summarizer):
        """Results longer than _MAX_CHARS_PER_RESULT are truncated in the prompt."""
        long_text = "X" * (_MAX_CHARS_PER_RESULT + 500)
        results = [{"text": long_text, "score": 0.9}]
        prompt = summarizer._build_summarization_prompt(results, "test")

        # Should contain truncated text with ellipsis, not the full text
        assert "..." in prompt
        assert "X" * (_MAX_CHARS_PER_RESULT + 1) not in prompt


# ---------------------------------------------------------------------------
# Context Brief Formatting
# ---------------------------------------------------------------------------

class TestFormatContextBrief:
    def test_format_single_task(self, summarizer):
        """Singular 'task' for result_count=1."""
        brief = summarizer._format_context_brief("Summary text", 1)
        assert brief == "## Context Brief (from 1 similar task)\n\nSummary text"

    def test_format_multiple_tasks(self, summarizer):
        """Plural 'tasks' for result_count > 1."""
        brief = summarizer._format_context_brief("Summary text", 5)
        assert brief == "## Context Brief (from 5 similar tasks)\n\nSummary text"

    def test_format_preserves_summary_content(self, summarizer):
        """Summary text is included verbatim in the brief."""
        summary = "Key insight: SuiteCRM needs DKIM.\nAlso: SPF required."
        brief = summarizer._format_context_brief(summary, 2)
        assert "Key insight: SuiteCRM needs DKIM." in brief
        assert "Also: SPF required." in brief


# ---------------------------------------------------------------------------
# Think Tag Stripping
# ---------------------------------------------------------------------------

class TestStripThinkTags:
    def test_strips_think_blocks(self, summarizer):
        """Removes <think>...</think> blocks from model output."""
        raw = "<think>Let me reason about this...</think>Here is the summary."
        with patch("subprocess.run", return_value=MagicMock(
            returncode=0, stdout=raw, stderr=""
        )):
            result = summarizer.summarize(
                [{"text": "test", "score": 0.5}], "query"
            )
        assert "<think>" not in result
        assert "Let me reason" not in result
        assert "Here is the summary" in result

    def test_strips_multiline_think_blocks(self, summarizer):
        """Handles multi-line think blocks."""
        text = "<think>\nStep 1: analyze\nStep 2: summarize\n</think>\nFinal answer."
        cleaned = summarizer._strip_think_tags(text)
        assert cleaned == "Final answer."

    def test_no_think_tags_unchanged(self, summarizer):
        """Text without think tags is returned unchanged."""
        text = "Just a normal summary."
        cleaned = summarizer._strip_think_tags(text)
        assert cleaned == "Just a normal summary."


# ---------------------------------------------------------------------------
# Timeout Configuration
# ---------------------------------------------------------------------------

class TestTimeoutHandling:
    def test_subprocess_called_with_30s_timeout(self, summarizer, single_result):
        """Ollama subprocess is invoked with 30-second timeout."""
        with patch("subprocess.run", return_value=_mock_ollama_success()) as mock_run:
            summarizer.summarize(single_result, "test")

        call_kwargs = mock_run.call_args.kwargs if mock_run.call_args.kwargs else mock_run.call_args[1]
        assert call_kwargs.get("timeout") == 30

    def test_timeout_does_not_raise(self, summarizer, single_result):
        """TimeoutExpired is caught and does not propagate."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ollama", 30)):
            # Should not raise
            result = summarizer.summarize(single_result, "test")
        assert isinstance(result, str)
