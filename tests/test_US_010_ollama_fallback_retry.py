"""
IMPLEMENTATION PLAN for US-010:

Components:
  - EmbeddingService (src/core/embedding_service.py):
      - Modify _call_ollama to return a specific status/raise custom exception (OllamaUnavailableError) on persistent Ollama unavailability (after retries/restart attempts).
      - Add is_ollama_available() method to provide external health check.
  - Notifier (src/notifications/notifier.py):
      - Add notify_ollama_unavailable(task_id: str) method to send ntfy notification.
  - OrchestratorV2 (src/orchestrator_v2.py):
      - Inject EmbeddingService or its health check method into relevant components (e.g., RoutingEngine that is passed to ClassifierAgent and StoryAgent).
      - Before critical steps like RAG context retrieval (vector_store.search) and task embedding (vector_store.add_document), check Ollama availability.
      - If Ollama is unavailable during `vector_store.search` (RAG context):
          - Catch OllamaUnavailableError.
          - Call `notifier.notify_ollama_unavailable`.
          - Return a specific status like `{"status": "pending_ollama_retry", "returncode": 1}` to signal the daemon to retry the task.
          - Prevent further processing (decomposition, execution).
      - If Ollama is unavailable during `vector_store.add_document` (final task embedding):
          - Catch OllamaUnavailableError.
          - Log a warning, but allow the task to complete if stories were otherwise successful. (This is a graceful degradation and might not trigger a full task retry, depending on criticality). However, the AC "Tasks are queued for retry when Ollama is unavailable" suggests a more aggressive retry for *any* unavailability during task processing. For this, I will assume a retry is desired for *any* critical Ollama interaction failure.
  - LLMRouter (src/llm/llm_router.py):
      - Inject EmbeddingService or its `is_ollama_available()` method into `LLMRouter`.
      - In `classify_and_route`, if Ollama is unavailable and the task is an 'ollama_task', return a specific status `'ollama_unavailable'` instead of defaulting to 'claude'.

Test Cases:
  1. AC 1: Tasks are queued for retry when Ollama is unavailable.
      - Test `OrchestratorV2.process_task_file` behavior when `EmbeddingService.generate_embedding` (simulated via `VectorStore.search`) raises `OllamaUnavailableError`.
      - Assert that `process_task_file` returns `{"status": "pending_ollama_retry", "returncode": 1}` and `mock_notifier.notify_ollama_unavailable` is called.
      - Assert that `ClassifierAgent.classify` and `StoryAgent.decompose` are NOT called if Ollama fails early during RAG.
  2. AC 2: Ntfy notification is sent when Ollama is unavailable.
      - Test that `mock_notifier.notify_ollama_unavailable` is called by `OrchestratorV2` when `EmbeddingService` reports Ollama is down and a critical operation fails.
  3. AC 3: No fallback to Claude for bulk classification occurs when Ollama is down.
      - Test `LLMRouter.classify_and_route` when `EmbeddingService.is_ollama_available()` returns `False`.
      - For a task description normally routed to Ollama, assert that `classify_and_route` returns `"ollama_unavailable"`.
      - Test that `OrchestratorV2` handles this `"ollama_unavailable"` status from `LLMRouter` by also returning `{"status": "pending_ollama_retry", "returncode": 1}` and notifying.

Edge Cases:
  - Ollama restart succeeds after initial failure (EmbeddingService internal logic, will be tested in EmbeddingService's own tests, not here).
  - Ollama restart fails persistently (covered by `OllamaUnavailableError`).
  - Task is not an "ollama_task": `LLMRouter` should still route correctly (e.g., to Claude) even if Ollama is down.
  - `vector_store` initialization fails: Orchestrator gracefully degrades (already existing).
  - Ollama is down, but task is for Claude: LLMRouter should still route to Claude.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import os
import json

# Assuming these will be the real modules in the src directory
from src.core.embedding_service import EmbeddingService, OllamaUnavailableError
from src.notifications.notifier import Notifier
from src.orchestrator_v2 import OrchestratorV2
from src.agents.classifier_agent import ClassifierAgent
from src.agents.story_agent import StoryAgent
from src.llm_router import LLMRouter

# Mock the entire ollama library calls from EmbeddingService
@pytest.fixture
def mock_ollama_api():
    with patch('src.core.embedding_service.ollama') as mock:
        yield mock

# Mock Notifier for isolation
@pytest.fixture
def mock_notifier():
    with patch('src.orchestrator_v2.Notifier') as mock:
        instance = mock.return_value
        instance.send_ntfy = MagicMock(return_value=True)
        instance.notify_ollama_unavailable = MagicMock() # New method to mock
        yield instance

# Mock EmbeddingService for controlled behavior in tests
@pytest.fixture
def mock_embedding_service():
    with patch('src.core.embedding_service.EmbeddingService') as mock_cls:
        instance = mock_cls.return_value
        instance.generate_embedding.return_value = [0.1] * 768
        instance.is_ollama_available.return_value = True # Default to available
        yield instance

# Mock VectorStore calls from OrchestratorV2
@pytest.fixture
def mock_vector_store():
    with patch('src.core.vector_store.VectorStore') as mock_cls:
        instance = mock_cls.return_value
        instance.search.return_value = [] # Default empty search results
        instance.add_document = MagicMock()
        yield instance

# Mock ClassifierAgent and StoryAgent to prevent actual LLM calls and focus on orchestrator flow
@pytest.fixture
def mock_agents():
    with patch('src.orchestrator_v2.ClassifierAgent') as mock_classifier_cls:
        mock_classifier_cls.return_value = AsyncMock(spec=ClassifierAgent)
        mock_classifier = mock_classifier_cls.return_value
        mock_classifier.classify.return_value = AsyncMock(task_type="feature", confidence=0.9)

        with patch('src.orchestrator_v2.StoryAgent') as mock_story_agent_cls:
            mock_story_agent_cls.return_value = AsyncMock(spec=StoryAgent)
            mock_story_agent = mock_story_agent_cls.return_value
            mock_story_agent.decompose.return_value = AsyncMock(stories=[]) # No stories decomposed by default
            yield mock_classifier, mock_story_agent

# Mock LLMRouter for isolation within OrchestratorV2 tests
@pytest.fixture
def mock_llm_router_orchestrator():
    """Mocks LLMRouter when used by OrchestratorV2 (via RoutingEngine)."""
    with patch('src.orchestrator_v2.RoutingEngine') as mock_routing_engine_cls:
        mock_routing_engine_instance = MagicMock()
        mock_routing_engine_cls.return_value = mock_routing_engine_instance
        mock_provider = MagicMock(name='mock_provider')
        mock_provider.name = 'mock_claude'
        mock_routing_engine_instance.select.return_value = mock_provider
        yield mock_routing_engine_instance

# Mock DatabaseManager for OrchestratorV2
@pytest.fixture
def mock_db_manager():
    with patch('src.db.database_manager.DatabaseManager') as mock:
        instance = mock.return_value
        instance.get_active_prd_session.return_value = None
        instance.create_task.return_value = 1
        instance.update_task_status = MagicMock()
        instance.create_prd_session.return_value = 1
        instance.update_prd_session = MagicMock()
        instance.log_event = MagicMock()
        yield instance

# Mock the execute_story to prevent actual execution and focus on orchestrator's behavior
@pytest.fixture
def mock_execute_story():
    with patch('src.orchestrator_v2.execute_story', new_callable=AsyncMock) as mock:
        # Default behavior: story passes
        mock.return_value = MagicMock(
            story_id="mock-story-1", success=True, reason=None, attempts=1, duration_seconds=1.0
        )
        yield mock

# --- Tests for AC 1 & 2 (OrchestratorV2 behavior) ---
@pytest.mark.asyncio
async def test_orchestrator_signals_retry_and_notifies_on_ollama_rag_failure(
    tmp_path, mock_notifier, mock_embedding_service, mock_vector_store,
    mock_llm_router_orchestrator, mock_db_manager, mock_agents
):
    """
    AC 1: Tasks are queued for retry when Ollama is unavailable during RAG context retrieval.
    AC 2: Ntfy notification is sent when Ollama is unavailable.
    OrchestratorV2 should signal for a task retry and send a notification if Ollama is unavailable
    during the critical RAG context retrieval phase (vector_store.search).
    Further processing (classification, decomposition, execution) should be prevented.
    """
    task_dir = tmp_path / "test_task_rag_failure"
    task_dir.mkdir()
    task_file = task_dir / "task.md"
    task_file.write_text("""<Pending>
User request requiring RAG context.""")

    # Simulate Ollama unavailability by making vector_store.search raise an error
    mock_vector_store.search.side_effect = OllamaUnavailableError("Ollama is down during RAG search")
    
    # Explicitly mock the static method check_ollama_health for any EmbeddingService instance
    with patch('src.core.embedding_service.EmbeddingService.check_ollama_health', return_value=False):
        orchestrator = OrchestratorV2(project_path=str(tmp_path))
        orchestrator._write_response = AsyncMock() # Prevent actual file writes

        with patch('src.execution.audit_journal.AuditJournal.log'):
            result = await orchestrator.process_task_file(str(task_file))

    # AC 1: Expect specific retry status and return code
    assert result == {"status": "pending_ollama_retry", "returncode": 1}

    # AC 2: Expect notification to be sent
    mock_notifier.notify_ollama_unavailable.assert_called_once_with(task_id=task_dir.name)

    # Ensure further processing (classification, decomposition) did not happen
    mock_agents[0].classify.assert_not_called()
    mock_agents[1].decompose.assert_not_called()
    orchestrator._write_response.assert_not_called() # Should not write any response files if failed early

@pytest.mark.asyncio
async def test_orchestrator_signals_retry_and_notifies_on_llm_router_ollama_unavailable(
    tmp_path, mock_notifier, mock_embedding_service, mock_vector_store,
    mock_llm_router_orchestrator, mock_db_manager, mock_agents, mock_execute_story
):
    """
    AC 1: Tasks are queued for retry when LLMRouter signals Ollama is unavailable.
    AC 2: Ntfy notification is sent when Ollama is unavailable.
    OrchestratorV2 should signal for a task retry and send a notification if LLMRouter
    returns 'ollama_unavailable' for a task.
    Further processing (decomposition, execution) should be prevented.
    """
    task_dir = tmp_path / "test_task_llm_router_fail"
    task_dir.mkdir()
    task_file = task_dir / "task.md"
    ollama_task_description = """<Pending>
User request for ollama specific classification."""
    task_file.write_text(ollama_task_description)

    # Mock the LLMRouter class that OrchestratorV2's ClassifierAgent uses
    # Note: OrchestratorV2 uses RoutingEngine, which in turn uses LLMRouter.
    # We need to mock the behavior of LLMRouter's classify_and_route directly if we want to
    # control what it returns. The existing mock_llm_router_orchestrator controls RoutingEngine.select.
    # To control LLMRouter's classification, we need to patch LLMRouter itself.
    with patch('src.llm_router.LLMRouter') as mock_actual_llm_router_cls:
        mock_actual_llm_router_instance = mock_actual_llm_router_cls.return_value
        # Configure LLMRouter to return "ollama_unavailable" for our specific task
        mock_actual_llm_router_instance.classify_and_route.return_value = "ollama_unavailable"

        # Even if mock_vector_store.search doesn't raise, LLMRouter's result should take precedence
        mock_vector_store.search.return_value = []
        
        # Explicitly mock the static method check_ollama_health for any EmbeddingService instance
        with patch('src.core.embedding_service.EmbeddingService.check_ollama_health', return_value=False):
            # Mock ClassifierAgent to ensure it gets the 'ollama_unavailable' status from LLMRouter
            mock_agents[0].classify.return_value = MagicMock(
                task_type="ollama_unavailable", confidence=1.0 # Simulate ClassifierAgent returning this from LLMRouter
            )

            orchestrator = OrchestratorV2(project_path=str(tmp_path))
            orchestrator._write_response = AsyncMock()

            with patch('src.execution.audit_journal.AuditJournal.log'):
                result = await orchestrator.process_task_file(str(task_file))

        # AC 1: Expect specific retry status and return code
        assert result == {"status": "pending_ollama_retry", "returncode": 1}

        # AC 2: Expect notification to be sent
        mock_notifier.notify_ollama_unavailable.assert_called_once_with(task_id=task_dir.name)

        # Ensure decomposition and execution did not happen
        mock_agents[1].decompose.assert_not_called()
        mock_execute_story.assert_not_called()
        orchestrator._write_response.assert_not_called()

# --- Tests for AC 3 (LLMRouter behavior) ---
class TestLLMRouterOllamaFallback:
    """Tests for LLMRouter when Ollama is unavailable."""

    @pytest.fixture(autouse=True)
    def setup_llm_router_test(self, mock_embedding_service):
        # We only need mock_embedding_service here to control Ollama health check
        self.mock_embedding_service = mock_embedding_service
        # Patch the EmbeddingService constructor that LLMRouter might use (if LLMRouter is modified to use it)
        with patch('src.core.embedding_service.EmbeddingService') as mock_llm_router_embedding_service_cls:
            mock_llm_router_embedding_service_instance = mock_llm_router_embedding_service_cls.return_value
            mock_llm_router_embedding_service_instance.is_ollama_available.return_value = False # Ollama is down for LLMRouter
            # Explicitly mock the static method check_ollama_health
            mock_llm_router_embedding_service_cls.check_ollama_health.return_value = False
            yield

    def test_llm_router_returns_ollama_unavailable_for_ollama_task_when_ollama_down(self):
        """
        AC 3: No fallback to Claude for bulk classification occurs when Ollama is down.
        When Ollama is unavailable, a task explicitly meant for Ollama should result in
        an 'ollama_unavailable' status from LLMRouter, not a fallback to Claude.
        """
        with patch('src.core.embedding_service.EmbeddingService.check_ollama_health', return_value=False):
            router = LLMRouter()
            ollama_task_description = "Classify industries using ollama"

            # Expect 'ollama_unavailable' because Ollama is mocked as down.
            result = router.classify_and_route(ollama_task_description)
            assert result == "ollama_unavailable"

    def test_llm_router_routes_claude_task_to_claude_even_if_ollama_down(self):
        """
        Tasks explicitly meant for Claude should still be routed to Claude,
        even if Ollama is unavailable.
        """
        router = LLMRouter()
        claude_task_description = "Generate personalized email body for prospect-facing content"

        # Ollama is down, but this is a Claude task, so it should route to Claude
        result = router.classify_and_route(claude_task_description)
        assert result == "claude"

    def test_llm_router_routes_ambiguous_task_to_claude_if_ollama_down(self):
        """
        Ambiguous tasks should still default to Claude if Ollama is down.
        This tests the current default behavior is maintained for non-ollama specific tasks.
        """
        router = LLMRouter()
        ambiguous_task_description = "Process this document for general insights"

        # Ollama is down, and this is an ambiguous task. It should still default to Claude.
        result = router.classify_and_route(ambiguous_task_description)
        assert result == "claude"

# This is an example of a successful path, demonstrating that other tasks proceed normally
@pytest.mark.asyncio
async def test_orchestrator_completes_task_if_ollama_available(
    tmp_path, mock_notifier, mock_embedding_service, mock_vector_store,
    mock_llm_router_orchestrator, mock_db_manager, mock_agents, mock_execute_story
):
    """
    Ensure that if Ollama is available, OrchestratorV2 processes tasks normally to completion.
    """
    task_dir = tmp_path / "test_task_ollama_available"
    task_dir.mkdir()
    task_file = task_dir / "task.md"
    task_file.write_text("""<Pending>
User request for a new feature.""")

    mock_embedding_service.is_ollama_available.return_value = True # Ollama is available
    mock_vector_store.search.return_value = [] # RAG returns nothing

    # Explicitly mock the static method check_ollama_health for any EmbeddingService instance
    with patch('src.core.embedding_service.EmbeddingService.check_ollama_health', return_value=True):
        # Mock decompose to return a story, so execute_story is called
        mock_agents[1].decompose.return_value = MagicMock(stories=[
            MagicMock(model_dump=lambda: {"id": "story-1", "title": "Implement feature", "type": "code"})
        ])
        orchestrator = OrchestratorV2(project_path=str(tmp_path))
        orchestrator._write_response = AsyncMock()

        with patch('src.execution.audit_journal.AuditJournal.log'):
            result = await orchestrator.process_task_file(str(task_file))

    # Expect successful completion
    assert result == {"status": "complete", "returncode": 0}
    mock_notifier.notify_task_complete.assert_called_once()
    mock_notifier.notify_ollama_unavailable.assert_not_called()
    mock_agents[0].classify.assert_called_once()
    mock_agents[1].decompose.assert_called_once()
    mock_execute_story.assert_called_once()
    assert orchestrator._write_response.call_count >= 2 # Initial and final response
