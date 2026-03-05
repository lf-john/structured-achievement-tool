"""Tests for src.execution.story_executor — Workflow selection + retry logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.execution.story_executor import (
    WORKFLOW_MAP,
    StoryResult,
    execute_story,
    get_workflow_for_story,
)


class TestWorkflowSelection:
    def test_development_story(self):
        story = {"type": "development", "tdd": True}
        graph = get_workflow_for_story(story, MagicMock())
        assert graph is not None

    def test_config_story(self):
        story = {"type": "config"}
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

    def test_unknown_type_raises_error(self):
        story = {"type": "unknown_type"}
        with pytest.raises(ValueError, match="No workflow for story type"):
            get_workflow_for_story(story, MagicMock())

    def test_all_workflow_types_in_map(self):
        expected = {"development", "config", "maintenance", "debug", "research", "review",
                    "conversation", "content",
                    "assignment", "qa_feedback", "escalation"}
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

        with patch("src.execution.story_executor.get_current_commit", return_value="abc123"):
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

    @pytest.mark.asyncio
    async def test_max_attempts_exhausted(self):
        """Test that exhausting attempts returns failure."""
        story = {"id": "US-001", "title": "Test", "type": "development"}

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "phase_outputs": [{"status": "failed", "exit_code": 1, "phase": "CODE", "llm_provider": "Claude"}],
            "verify_passed": False,
            "failure_context": "test failure",
        }

        with patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph), \
             patch("src.execution.story_executor.get_current_commit", return_value="abc123"), \
             patch("src.execution.story_executor.classify_failure") as mock_classify, \
             patch("asyncio.sleep", new_callable=AsyncMock):

            from src.agents.failure_classifier import FailureSeverity
            mock_classify.return_value = MagicMock(
                severity=FailureSeverity.PERSISTENT,
                message="test failure",
            )

            result = await execute_story(
                story=story,
                task_id="task-1",
                task_description="test",
                working_directory="/tmp",
                max_attempts=2,
            )

        assert not result.success
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful story execution returns proper result."""
        story = {"id": "US-002", "title": "Successful Story", "type": "development"}

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "phase_outputs": [{"status": "complete", "exit_code": 0, "phase": "CODE"}],
            "verify_passed": True,
        }

        # AMENDED BY US-002: Patch checkpoint manager to avoid side effects
        with patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph), \
             patch("src.execution.story_executor.get_current_commit", return_value="def456"), \
             patch("src.execution.story_executor.read_checkpoint", return_value=None), \
             patch("src.execution.story_executor.write_checkpoint"), \
             patch("asyncio.sleep", new_callable=AsyncMock):

            result = await execute_story(
                story=story,
                task_id="task-2",
                task_description="successful test",
                working_directory="/tmp",
                max_attempts=1,
            )

        assert result.success
        assert result.attempts == 1
        assert result.story_id == "US-002"

