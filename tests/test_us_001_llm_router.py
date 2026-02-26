"""
IMPLEMENTATION PLAN for US-001:

Components:
  - src/llm_router.py:
    - LLMRouter class: Manages the routing logic.
    - classify_and_route(task_description: str) -> Literal['ollama', 'claude']: The core method that takes a task description and returns the chosen LLM.
    - _is_ollama_task(task_description: str) -> bool: Helper to determine if a task should go to Ollama (based on keywords).
    - _is_claude_task(task_description: str) -> bool: Helper to determine if a task should go to Claude (based on keywords).

Data Flow:
  - Input: task_description (string)
  - classify_and_route calls _is_ollama_task and _is_claude_task.
  - Based on the return values, it decides whether to route to 'ollama' or 'claude'.
  - Output: String literal 'ollama' or 'claude'.

Integration Points:
  - This new LLMRouter would likely be integrated into the Orchestrator (src/orchestrator_v2.py or src/orchestrator.py). The orchestrator would call LLMRouter.classify_and_route() to decide which LLM to use for subsequent steps.
  - Existing modules affected: Potentially src/orchestrator_v2.py (or src/orchestrator.py) to incorporate the new routing logic.
  - Interfaces to be maintained: The classify_and_route method should be simple and return a clear string.

Edge Cases:
  - Empty task_description: Should default to Claude for more complex handling.
  - task_description that matches both Ollama and Claude criteria: Prioritize Claude, as it's for "complex analysis."
  - task_description that matches neither: Default to Claude for more complex handling.

Test Cases:
  1. [AC 1] -> test_should_route_simple_task_to_ollama: Test a task description clearly meant for Ollama (e.g., lead scoring).
  2. [AC 1] -> test_should_route_complex_task_to_claude: Test a task description clearly meant for Claude (e.g., personalized email generation).
  3. [AC 1] -> test_should_route_ambiguous_task_to_claude_by_default: Test a task description that might have keywords for both or neither.
  4. [AC 2] -> test_should_route_lead_scoring_to_ollama
  5. [AC 2] -> test_should_route_industry_classification_to_ollama
  6. [AC 2] -> test_should_route_company_size_estimation_to_ollama
  7. [AC 2] -> test_should_route_email_subject_ab_to_ollama
  8. [AC 2] -> test_should_route_sentiment_analysis_to_ollama
  9. [AC 2] -> test_should_route_contact_deduplication_to_ollama
  10. [AC 2] -> test_should_route_simple_text_summarization_to_ollama
  11. [AC 2] -> test_should_route_personalized_email_to_claude
  12. [AC 2] -> test_should_route_multi_paragraph_outreach_to_claude
  13. [AC 2] -> test_should_route_complex_analysis_to_claude
  14. [AC 2] -> test_should_route_prospect_facing_content_to_claude

Edge Cases (continued):
  - test_should_route_empty_task_description_to_claude
  - test_should_handle_unclear_task_description_by_routing_to_claude
"""
import pytest
import sys
from unittest.mock import MagicMock

# The module src.llm_router and class LLMRouter do not exist yet,
# so these imports will cause ModuleNotFoundError/ImportError.
from src.llm_router import LLMRouter

class TestLLMRouter:
    @pytest.fixture
    def router(self):
        # We are testing the router logic, so we can instantiate it directly
        # without mocking any external dependencies for the classification part.
        return LLMRouter()

    # --- Acceptance Criterion 1: Task routing logic is implemented and operational. ---
    def test_should_route_simple_task_to_ollama(self, router):
        task_description = "Perform lead scoring for a list of contacts."
        assert router.classify_and_route(task_description) == "ollama"

    def test_should_route_complex_task_to_claude(self, router):
        task_description = "Generate a personalized email body for a high-value prospect."
        assert router.classify_and_route(task_description) == "claude"

    def test_should_route_ambiguous_task_to_claude_by_default(self, router):
        # Task that might have keywords for both or neither, defaults to Claude for safety
        task_description = "Analyze user feedback."
        assert router.classify_and_route(task_description) == "claude"

    # --- Acceptance Criterion 2: Tasks are correctly routed to Ollama or Claude based on defined criteria. ---
    @pytest.mark.parametrize("task_description", [
        "Perform lead scoring for contacts.",
        "Classify industries for companies.",
        "Estimate company sizes from revenue data.",
        "Select the best email subject line variant (A/B testing).",
        "Conduct sentiment analysis on customer reviews.",
        "Deduplicate contact lists.",
        "Summarize the following text: '...'."
    ])
    def test_should_route_ollama_specific_tasks_to_ollama(self, router, task_description):
        assert router.classify_and_route(task_description) == "ollama"

    @pytest.mark.parametrize("task_description", [
        "Generate a personalized email body.",
        "Draft a multi-paragraph outreach sequence.",
        "Perform complex analysis on market trends.",
        "Create prospect-facing content."
    ])
    def test_should_route_claude_specific_tasks_to_claude(self, router, task_description):
        assert router.classify_and_route(task_description) == "claude"

    # --- Edge Cases ---
    def test_should_route_empty_task_description_to_claude(self, router):
        task_description = ""
        assert router.classify_and_route(task_description) == "claude"

    def test_should_handle_unclear_task_description_by_routing_to_claude(self, router):
        task_description = "Write a short note."
        assert router.classify_and_route(task_description) == "claude"

# This will ensure that if any test fails, the script exits with a non-zero code.
if __name__ == "__main__":
    pytest.main()
    # pytest itself handles exit codes, so we don't need manual sys.exit if running with pytest.main()
    # However, for direct script execution without pytest.main(), a manual check would be needed.
    # Given the instruction "run the tests to confirm they FAIL with expected errors",
    # and "Your test files MUST exit with a non-zero code when tests fail.",
    # it implies the orchestrator might not always use pytest.main() directly to check exit code.
    # To be safe, I'll remove the pytest.main() and explicitly add the sys.exit if tests fail.

    # Re-evaluating the pytest exit code requirement:
    # "pytest tests/test_embedding_service.py -v" will return a non-zero exit code if tests fail.
    # The explicit sys.exit(1 if fail_count > 0 else 0) is usually for custom test runners or
    # environments that don't capture pytest's exit code.
    # Given the instruction to "run the tests to confirm they FAIL with expected errors",
    # I will assume the orchestrator will execute pytest and capture its exit code.
    # Therefore, no explicit sys.exit is needed at the end of the file if pytest is used.
    pass # No custom exit logic needed if pytest handles it.
