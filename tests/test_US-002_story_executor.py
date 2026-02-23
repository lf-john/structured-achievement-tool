"""
IMPLEMENTATION PLAN for US-002:

Components:
  - src/execution/story_executor.py: The primary file to be modified.
  - AuditJournal class: Will be imported and instantiated within execute_story.
  - AuditRecord dataclass: Will be used to construct the audit log entry.
  - execute_story function: Will be enhanced to:
    1. Instantiate AuditJournal.
    2. Capture relevant story state (story_id, task_id, task_description, working_directory, final_state details).
    3. Extract LLM provider usage per phase from final_state.
    4. Construct an AuditRecord instance with all required fields.
    5. Call audit_journal.append_record() exactly once before returning StoryResult.

Test Cases:
  1. AC1 & AC2: test_execute_story_logs_audit_record_on_success
     - Verifies AuditJournal is instantiated and append_record is called once when a story succeeds.
  2. AC2: test_execute_story_logs_audit_record_on_fatal_failure
     - Verifies append_record is called once when a story fails due to a fatal error.
  3. AC2: test_execute_story_logs_audit_record_on_cancellation
     - Verifies append_record is called once when a story is cancelled.
  4. AC3 & AC4: test_audit_record_captures_llm_providers_on_success
     - Mocks a successful story execution with specific LLM provider data in phase_outputs and asserts the AuditRecord captures this correctly.
  5. AC4: test_audit_record_populates_all_fields_on_success
     - Verifies all fields of AuditRecord are correctly populated for a successful story.
  6. AC4: test_audit_record_populates_fields_on_failure_with_retry
     - Verifies AuditRecord fields (especially attempts, success, reason) are correct after a story fails after multiple retries.
  7. Edge Case: test_audit_record_handles_missing_llm_provider_in_phase_output
     - Ensures that if 'llm_provider' is missing in phase_outputs, the system handles it gracefully (e.g., defaults to 'unknown' or an empty dict).
  8. Edge Case: test_audit_record_when_phase_outputs_is_empty
     - Ensures no errors and correct default values when phase_outputs is empty.

Edge Cases:
  - Story success on first attempt.
  - Story failure (fatal) on first attempt.
  - Story cancellation.
  - Story failure after transient retries (ensuring final attempt count is correct).
  - Missing 'llm_provider' in phase_outputs.
  - Empty 'phase_outputs'.
  - Story duration calculation (needs to be mocked or faked).
  - Session ID generation (needs to be mocked or faked).
  - Total turns calculation (needs to be mocked or faked).
  - `task_file` extraction (will be based on `task_id`).
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# Assume these will be imported by story_executor.py after modification
from src.execution.audit_journal import AuditJournal, AuditRecord
from src.workflows.state import StoryState

# The module under test
from src.execution.story_executor import execute_story, StoryResult, WORKFLOW_MAP, get_workflow_for_story

# Mock data for a typical story
MOCK_STORY = {
    "id": "US-002-story-1",
    "title": "Implement AuditJournal Logging",
    "type": "development",
    "tdd": True,
}
MOCK_TASK_ID = "task-123"
MOCK_TASK_DESCRIPTION = "Integrate audit logging for US-002"
MOCK_WORKING_DIRECTORY = "/tmp/test_dir"
MOCK_SESSION_ID = "session-abc"

@pytest.fixture
def mock_audit_journal():
    """Fixture for a mocked AuditJournal instance."""
    with patch('src.execution.story_executor.AuditJournal') as mock_journal_cls:
        mock_journal = MagicMock(spec=AuditJournal)
        mock_journal_cls.return_value = mock_journal
        yield mock_journal

@pytest.fixture
def mock_routing_engine():
    """Fixture for a mocked RoutingEngine."""
    with patch('src.execution.story_executor.RoutingEngine') as mock_routing_cls:
        mock_engine = MagicMock()
        mock_routing_cls.return_value = mock_engine
        yield mock_engine

@pytest.fixture
def mock_notifier():
    """Fixture for a mocked Notifier."""
    with patch('src.execution.story_executor.Notifier') as mock_notifier_cls:
        mock_notifier_instance = MagicMock()
        mock_notifier_cls.return_value = mock_notifier_instance
        yield mock_notifier_instance

@pytest.fixture
def mock_workflow_graph():
    """Fixture for a mocked LangGraph workflow graph."""
    mock_graph = AsyncMock()
    # Patch get_workflow_for_story to return our mock_graph directly
    with patch('src.execution.story_executor.get_workflow_for_story', return_value=mock_graph):
        yield mock_graph

# Mocking common external dependencies that story_executor uses
@pytest.fixture(autouse=True)
def mock_external_dependencies():
    with patch('src.execution.story_executor.get_current_commit', return_value="mock_commit_hash"):
        with patch('src.execution.story_executor.reset_to_commit', return_value=None):
            with patch('src.execution.story_executor.classify_failure', side_effect=lambda **kwargs: MagicMock(severity=MagicMock(value="FATAL"), message="Mock fatal failure")):
                with patch('src.execution.story_executor.create_initial_state', side_effect=lambda **kwargs: StoryState(
                    story=kwargs['story'],
                    task_id=kwargs['task_id'],
                    task_description=kwargs['task_description'],
                    working_directory=kwargs['working_directory'],
                    max_attempts=kwargs.get('max_attempts', 1),
                    mediator_enabled=kwargs.get('mediator_enabled', False),
                    story_attempt=1,
                    failure_context="",
                    session_id=MOCK_SESSION_ID, # Inject mock session ID
                    start_time=datetime.now() # Inject start time
                )):
                    yield

@pytest.mark.asyncio
class TestStoryExecutorAuditJournal:

    # AC1 & AC2: Verify AuditJournal is instantiated and append_record is called once on success
    async def test_execute_story_logs_audit_record_on_success(self, mock_audit_journal, mock_workflow_graph, mock_routing_engine, mock_notifier):
        mock_workflow_graph.invoke.return_value = {
            "phase_outputs": [{"phase": "plan", "status": "complete", "llm_provider": "Claude"}, {"phase": "code", "status": "complete", "llm_provider": "Gemini"}],
            "verify_passed": True,
            "session_id": MOCK_SESSION_ID,
            "start_time": datetime.now() - timedelta(seconds=10), # Duration 10s
            "total_turns": 5,
            "exit_code": 0,
        }

        result = await execute_story(
            story=MOCK_STORY,
            task_id=MOCK_TASK_ID,
            task_description=MOCK_TASK_DESCRIPTION,
            working_directory=MOCK_WORKING_DIRECTORY,
            routing_engine=mock_routing_engine,
            notifier=mock_notifier
        )

        assert result.success is True
        mock_audit_journal.append_record.assert_called_once()
        args, _ = mock_audit_journal.append_record.call_args
        audit_record = args[0]
        assert isinstance(audit_record, AuditRecord)
        assert audit_record.success is True

    # AC2: Verify append_record is called once on fatal failure
    async def test_execute_story_logs_audit_record_on_fatal_failure(self, mock_audit_journal, mock_workflow_graph, mock_routing_engine, mock_notifier):
        with patch('src.execution.story_executor.classify_failure', return_value=MagicMock(severity=MagicMock(value="FATAL"), message="Mock fatal failure")):
            mock_workflow_graph.invoke.return_value = {
                "phase_outputs": [{"phase": "plan", "status": "failed"}],
                "verify_passed": False,
                "failure_context": "Mock fatal error",
                "session_id": MOCK_SESSION_ID,
                "start_time": datetime.now() - timedelta(seconds=5), # Duration 5s
                "total_turns": 3,
                "exit_code": 1,
            }

            result = await execute_story(
                story=MOCK_STORY,
                task_id=MOCK_TASK_ID,
                task_description=MOCK_TASK_DESCRIPTION,
                working_directory=MOCK_WORKING_DIRECTORY,
                routing_engine=mock_routing_engine,
                notifier=mock_notifier
            )

            assert result.success is False
            mock_audit_journal.append_record.assert_called_once()
            args, _ = mock_audit_journal.append_record.call_args
            audit_record = args[0]
            assert isinstance(audit_record, AuditRecord)
            assert audit_record.success is False
            assert "fatal error" in audit_record.error_summary.lower()


    # AC2: Verify append_record is called once on cancellation
    async def test_execute_story_logs_audit_record_on_cancellation(self, mock_audit_journal, mock_routing_engine, mock_notifier):
        cancellation_event = asyncio.Event()
        cancellation_event.set() # Set the event immediately to trigger cancellation

        # Since workflow.invoke won't be called, we need to ensure create_initial_state is mocked for the audit record
        # and that the audit record is logged BEFORE the cancellation return.
        # This test checks if the audit record is logged AT ALL, even with cancellation.
        # The current execute_story returns *before* an audit record is logged on cancellation.
        # This will fail initially, which is correct for TDD-RED.
        result = await execute_story(
            story=MOCK_STORY,
            task_id=MOCK_TASK_ID,
            task_description=MOCK_TASK_DESCRIPTION,
            working_directory=MOCK_WORKING_DIRECTORY,
            routing_engine=mock_routing_engine,
            notifier=mock_notifier,
            cancellation_event=cancellation_event
        )

        assert result.success is False
        assert result.reason == "Cancelled by user"
        # This assertion is expected to fail initially as the current code returns before logging on cancellation.
        # This is the TDD-RED state.
        mock_audit_journal.append_record.assert_called_once()


    # AC3 & AC4: Verify audit record captures LLM providers and other fields on success
    async def test_audit_record_captures_llm_providers_on_success(self, mock_audit_journal, mock_workflow_graph, mock_routing_engine):
        mock_workflow_graph.invoke.return_value = {
            "phase_outputs": [
                {"phase": "plan", "status": "complete", "llm_provider": "Claude"},
                {"phase": "code", "status": "complete", "llm_provider": "Gemini"},
                {"phase": "verify", "status": "complete", "llm_provider": "Claude"}
            ],
            "verify_passed": True,
            "session_id": MOCK_SESSION_ID,
            "start_time": datetime.now() - timedelta(seconds=25),
            "total_turns": 8,
            "exit_code": 0,
        }

        await execute_story(
            story=MOCK_STORY,
            task_id=MOCK_TASK_ID,
            task_description=MOCK_TASK_DESCRIPTION,
            working_directory=MOCK_WORKING_DIRECTORY,
            routing_engine=mock_routing_engine
        )

        mock_audit_journal.append_record.assert_called_once()
        args, _ = mock_audit_journal.append_record.call_args
        audit_record = args[0]

        assert audit_record.llm_provider_per_phase == {
            "plan": "Claude",
            "code": "Gemini",
            "verify": "Claude"
        }
        assert audit_record.story_id == MOCK_STORY["id"]
        assert audit_record.story_title == MOCK_STORY["title"]
        assert audit_record.task_file == MOCK_TASK_ID # Assuming task_file maps to task_id for simplicity in mock
        assert audit_record.session_id == MOCK_SESSION_ID
        assert audit_record.total_turns == 8
        assert audit_record.exit_code == 0
        assert audit_record.duration_seconds == pytest.approx(25.0, rel=1e-3)
        assert audit_record.success is True
        assert audit_record.phases_completed == ["plan", "code", "verify"]
        assert audit_record.error_summary is None

    # AC4: Verify all fields of AuditRecord are correctly populated for a successful story.
    async def test_audit_record_populates_all_fields_on_success(self, mock_audit_journal, mock_workflow_graph, mock_routing_engine):
        start_time = datetime.now() - timedelta(seconds=15)
        mock_workflow_graph.invoke.return_value = {
            "phase_outputs": [
                {"phase": "design", "status": "complete", "llm_provider": "Claude"},
                {"phase": "tdd_red", "status": "complete", "llm_provider": "Gemini"}
            ],
            "verify_passed": True,
            "session_id": MOCK_SESSION_ID,
            "start_time": start_time,
            "total_turns": 6,
            "exit_code": 0,
        }

        await execute_story(
            story=MOCK_STORY,
            task_id=MOCK_TASK_ID,
            task_description=MOCK_TASK_DESCRIPTION,
            working_directory=MOCK_WORKING_DIRECTORY,
            routing_engine=mock_routing_engine
        )

        mock_audit_journal.append_record.assert_called_once()
        args, _ = mock_audit_journal.append_record.call_args
        audit_record = args[0]

        assert isinstance(audit_record.timestamp, datetime)
        assert audit_record.task_file == MOCK_TASK_ID
        assert audit_record.story_id == MOCK_STORY["id"]
        assert audit_record.story_title == MOCK_STORY["title"]
        assert audit_record.llm_provider_per_phase == {"design": "Claude", "tdd_red": "Gemini"}
        assert audit_record.session_id == MOCK_SESSION_ID
        assert audit_record.total_turns == 6
        assert audit_record.exit_code == 0
        assert audit_record.duration_seconds == pytest.approx(15.0, rel=1e-3)
        assert audit_record.success is True
        assert audit_record.phases_completed == ["design", "tdd_red"]
        assert audit_record.error_summary is None

    # AC4: Verify AuditRecord fields (especially attempts, success, reason) are correct after a story fails after multiple retries.
    async def test_audit_record_populates_fields_on_failure_with_retry(self, mock_audit_journal, mock_workflow_graph, mock_routing_engine):
        # First attempt: transient failure
        mock_workflow_graph.invoke.side_effect = [
            {
                "phase_outputs": [{"phase": "plan", "status": "failed", "llm_provider": "Claude"}],
                "verify_passed": False,
                "failure_context": "Transient error",
                "session_id": MOCK_SESSION_ID,
                "start_time": datetime.now() - timedelta(seconds=5),
                "total_turns": 2,
                "exit_code": 1,
            },
            # Second attempt: fatal failure
            {
                "phase_outputs": [{"phase": "plan", "status": "complete", "llm_provider": "Claude"}, {"phase": "code", "status": "failed", "llm_provider": "Gemini"}],
                "verify_passed": False,
                "failure_context": "Fatal error on code phase",
                "session_id": MOCK_SESSION_ID,
                "start_time": datetime.now() - timedelta(seconds=12),
                "total_turns": 4,
                "exit_code": 1,
            }
        ]

        with patch('src.execution.story_executor.classify_failure') as mock_classify_failure:
            with patch('asyncio.sleep', new=AsyncMock()): # Mock sleep to speed up test
                mock_classify_failure.side_effect = [
                    MagicMock(severity=MagicMock(value="TRANSIENT"), message="Transient error"),
                    MagicMock(severity=MagicMock(value="FATAL"), message="Fatal error")
                ]

            result = await execute_story(
                story=MOCK_STORY,
                task_id=MOCK_TASK_ID,
                task_description=MOCK_TASK_DESCRIPTION,
                working_directory=MOCK_WORKING_DIRECTORY,
                routing_engine=mock_routing_engine,
                max_attempts=2 # Limit to 2 attempts for this test
            )

            assert result.success is False
            assert result.attempts == 2
            mock_audit_journal.append_record.assert_called_once()
            args, _ = mock_audit_journal.append_record.call_args
            audit_record = args[0]

            assert audit_record.success is False
            assert audit_record.total_turns == 4 # Last attempt's turns
            assert "fatal error" in audit_record.error_summary.lower()
            assert audit_record.llm_provider_per_phase == {"plan": "Claude", "code": "Gemini"}
            assert audit_record.exit_code == 1

    # Edge Case: Ensures that if 'llm_provider' is missing in phase_outputs, the system handles it gracefully.
    async def test_audit_record_handles_missing_llm_provider_in_phase_output(self, mock_audit_journal, mock_workflow_graph):
        mock_workflow_graph.invoke.return_value = {
            "phase_outputs": [
                {"phase": "plan", "status": "complete"}, # Missing llm_provider
                {"phase": "code", "status": "complete", "llm_provider": "Gemini"}
            ],
            "verify_passed": True,
            "session_id": MOCK_SESSION_ID,
            "start_time": datetime.now() - timedelta(seconds=10),
            "total_turns": 5,
            "exit_code": 0,
        }

        await execute_story(
            story=MOCK_STORY,
            task_id=MOCK_TASK_ID,
            task_description=MOCK_TASK_DESCRIPTION,
            working_directory=MOCK_WORKING_DIRECTORY
        )

        mock_audit_journal.append_record.assert_called_once()
        args, _ = mock_audit_journal.append_record.call_args
        audit_record = args[0]

        assert audit_record.llm_provider_per_phase == {
            "plan": "unknown", # Expect default to 'unknown' or be absent
            "code": "Gemini"
        }
        assert audit_record.success is True

    # Edge Case: Ensures no errors and correct default values when phase_outputs is empty.
    async def test_audit_record_when_phase_outputs_is_empty(self, mock_audit_journal, mock_workflow_graph):
        mock_workflow_graph.invoke.return_value = {
            "phase_outputs": [],
            "verify_passed": True,
            "session_id": MOCK_SESSION_ID,
            "start_time": datetime.now() - timedelta(seconds=1),
            "total_turns": 1,
            "exit_code": 0,
        }

        await execute_story(
            story=MOCK_STORY,
            task_id=MOCK_TASK_ID,
            task_description=MOCK_TASK_DESCRIPTION,
            working_directory=MOCK_WORKING_DIRECTORY
        )

        mock_audit_journal.append_record.assert_called_once()
        args, _ = mock_audit_journal.append_record.call_args
        audit_record = args[0]

        assert audit_record.llm_provider_per_phase == {}
        assert audit_record.phases_completed == []
        assert audit_record.success is True


