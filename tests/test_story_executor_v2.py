"""Tests for src.execution.story_executor — Workflow selection + retry logic."""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

from src.execution.story_executor import (
    get_workflow_for_story,
    execute_story,
    StoryResult,
    WORKFLOW_MAP,
)
from src.workflows.dev_tdd_workflow import DevTDDWorkflow
from src.workflows.config_tdd_workflow import ConfigTDDWorkflow
from src.workflows.debug_workflow import DebugWorkflow
from src.workflows.research_workflow import ResearchWorkflow

# Imports for Audit Journaling - expected to fail in TDD-RED
from src.execution.audit_journal import AuditJournal, AuditRecord


class TestWorkflowSelection:
    def test_development_story(self):
        story = {"type": "development", "tdd": True}
        graph = get_workflow_for_story(story, MagicMock())
        assert graph is not None

    def test_config_story(self):
        story = {"type": "config", "tdd": True}
        graph = get_workflow_for_story(story, MagicMock())
        assert graph is not None

    def test_debug_story(self):
        story = {"type": "debug"}
        graph = get_workflow_for_story(story, MagicMock())
        assert graph is not None

    def test_research_story(self):
        story = {"type": "research"}
        graph = get_workflow_for_story(story, MagicMock())
        assert graph is not None

    def test_unknown_type_defaults_to_dev(self):
        story = {"type": "unknown_type"}
        graph = get_workflow_for_story(story, MagicMock())
        assert graph is not None

    def test_all_workflow_types_in_map(self):
        expected = {"development", "config", "maintenance", "debug", "research", "review"}
        assert set(WORKFLOW_MAP.keys()) == expected


class TestStoryResult:
    def test_successful_result(self):
        result = StoryResult(story_id="US-001", success=True, attempts=1)
        assert result.success
        assert result.attempts == 1

    def test_failed_result(self):
        result = StoryResult(
            story_id="US-001", success=False, attempts=5,
            reason="Exhausted retries"
        )
        assert not result.success
        assert result.reason == "Exhausted retries"


class TestExecuteStory:
    @pytest.mark.asyncio
    async def test_cancellation(self):
        """Test that cancellation event stops execution."""
        cancel_event = asyncio.Event()
        cancel_event.set()  # Pre-cancelled

        story = {"id": "US-001", "title": "Test", "type": "development"}

        with patch("src.execution.story_executor.get_current_commit", return_value="abc123") as mock_get_commit, \
             patch("src.execution.story_executor.AuditJournal") as MockAuditJournal, \
             patch("src.execution.story_executor.AuditRecord") as MockAuditRecord:
            
            result = await execute_story(
                story=story,
                task_id="task-1",
                task_description="test",
                working_directory="/tmp",
                max_attempts=1,
                cancellation_event=cancel_event,
            )

        assert not result.success
        assert "Cancelled" in result.reason
        MockAuditJournal.return_value.log_record.assert_called_once()
        MockAuditRecord.assert_called_once()
        logged_record_kwargs = MockAuditRecord.call_args.kwargs
        assert logged_record_kwargs["story_id"] == "US-001"
        assert logged_record_kwargs["success"] is False
        assert logged_record_kwargs["error_summary"] == "Cancelled by user"


    @pytest.mark.asyncio
    async def test_max_attempts_exhausted(self):
        """Test that exhausting attempts returns failure."""
        story = {"id": "US-001", "title": "Test", "type": "development"}

        mock_graph = MagicMock()
        # Simulate failed workflow execution
        mock_graph.invoke.return_value = {
            "phase_outputs": [{"status": "failed", "exit_code": 1, "phase": "CODE", "llm_provider": "Claude"}],
            "verify_passed": False,
            "failure_context": "test failure",
            "llm_provider_used_per_phase": {"plan": "Gemini", "code": "Claude"}
        }

        with patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph), \
             patch("src.execution.story_executor.get_current_commit", return_value="abc123"), \
             patch("src.execution.story_executor.classify_failure") as mock_classify, \
             patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("src.execution.story_executor.AuditJournal") as MockAuditJournal, \
             patch("src.execution.story_executor.AuditRecord") as MockAuditRecord:

            mock_classify.return_value = MagicMock(
                severity=MagicMock(value="persistent"),
                message="test failure",
            )
            # Make severity comparison work
            from src.agents.failure_classifier import FailureSeverity
            mock_classify.return_value.severity = FailureSeverity.PERSISTENT

            result = await execute_story(
                story=story,
                task_id="task-1",
                task_description="test",
                working_directory="/tmp",
                max_attempts=2,
            )

        assert not result.success
        assert result.attempts == 2
        
        MockAuditJournal.return_value.log_record.assert_called_once()
        MockAuditRecord.assert_called_once()
        logged_record_kwargs = MockAuditRecord.call_args.kwargs
        assert logged_record_kwargs["story_id"] == "US-001"
        assert logged_record_kwargs["success"] is False
        assert logged_record_kwargs["total_turns"] == 2 # Max attempts
        assert logged_record_kwargs["llm_provider_used_per_phase"] == {"plan": "Gemini", "code": "Claude"}
        assert "test failure" in logged_record_kwargs["error_summary"]
        assert "Exhausted" in logged_record_kwargs["error_summary"]
        assert "test failure" in logged_record_kwargs["error_summary"]

    @pytest.mark.asyncio
    async def test_execute_story_logs_audit_record_on_success(self):
        """
        AC: Every story execution produces exactly one audit JSONL record.
        Test that execute_story logs an audit record on successful completion.
        """
        story = {"id": "US-002", "title": "Successful Story", "type": "development"}
        
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "phase_outputs": [{"status": "complete", "exit_code": 0, "phase": "CODE", "llm_provider": "Gemini"}],
            "verify_passed": True,
            "llm_provider_used_per_phase": {"plan": "Claude", "code": "Gemini", "verify": "Claude"}
        }

        with patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph), \
             patch("src.execution.story_executor.get_current_commit", return_value="def456"), \
             patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("src.execution.story_executor.AuditJournal") as MockAuditJournal, \
             patch("src.execution.story_executor.AuditRecord") as MockAuditRecord, \
             patch("time.time", side_effect=[1000, 1100]): # Simulate 100 seconds duration

            result = await execute_story(
                story=story,
                task_id="task-2",
                task_description="successful test",
                working_directory="/tmp",
                max_attempts=1,
            )

        assert result.success
        assert result.attempts == 1

        MockAuditJournal.return_value.log_record.assert_called_once()
        MockAuditRecord.assert_called_once()
        logged_record_kwargs = MockAuditRecord.call_args.kwargs
        assert logged_record_kwargs["story_id"] == "US-002"
        assert logged_record_kwargs["story_title"] == "Successful Story"
        assert logged_record_kwargs["task_file"] == "task-2"
        assert logged_record_kwargs["success"] is True
        assert logged_record_kwargs["duration_seconds"] == 100
        assert logged_record_kwargs["llm_provider_used_per_phase"] == {"plan": "Claude", "code": "Gemini", "verify": "Claude"}
        assert logged_record_kwargs["error_summary"] is None
        assert "CODE" in logged_record_kwargs["phases_completed"]
        
    @pytest.mark.asyncio
    async def test_execute_story_logs_audit_record_on_failure(self):
        """
        AC: Every story execution produces exactly one audit JSONL record.
        Test that execute_story logs an audit record on failed completion.
        """
        story = {"id": "US-003", "title": "Failed Story", "type": "development"}
        
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "phase_outputs": [{"status": "failed", "exit_code": 1, "phase": "TDD_RED", "llm_provider": "Claude"}],
            "verify_passed": False,
            "failure_context": "TDD_RED phase failed",
            "llm_provider_used_per_phase": {"plan": "Gemini", "tdd_red": "Claude"}
        }

        with patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph), \
             patch("src.execution.story_executor.get_current_commit", return_value="ghi789"), \
             patch("src.execution.story_executor.classify_failure") as mock_classify, \
             patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("src.execution.story_executor.AuditJournal") as MockAuditJournal, \
             patch("src.execution.story_executor.AuditRecord") as MockAuditRecord, \
             patch("time.time", side_effect=[2000, 2070]): # Simulate 70 seconds duration

            mock_classify.return_value = MagicMock(
                severity=MagicMock(value="transient"),
                message="test failure",
            )
            from src.agents.failure_classifier import FailureSeverity
            mock_classify.return_value.severity = FailureSeverity.TRANSIENT


            result = await execute_story(
                story=story,
                task_id="task-3",
                task_description="failed test",
                working_directory="/tmp",
                max_attempts=1,
            )

        assert not result.success
        assert result.attempts == 1

        MockAuditJournal.return_value.log_record.assert_called_once()
        MockAuditRecord.assert_called_once()
        logged_record_kwargs = MockAuditRecord.call_args.kwargs
        assert logged_record_kwargs["story_id"] == "US-003"
        assert logged_record_kwargs["story_title"] == "Failed Story"
        assert logged_record_kwargs["task_file"] == "task-3"
        assert logged_record_kwargs["success"] is False
        assert logged_record_kwargs["duration_seconds"] == 70
        assert logged_record_kwargs["llm_provider_used_per_phase"] == {"plan": "Gemini", "tdd_red": "Claude"}
        assert "TDD_RED phase failed" in logged_record_kwargs["error_summary"]
        assert "TDD_RED" in logged_record_kwargs["phases_completed"]

