"""Tests for src.execution.story_executor — Workflow selection + retry logic."""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

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
        # Simulate failed workflow execution
        mock_graph.invoke.return_value = {
            "phase_outputs": [{"status": "failed", "exit_code": 1, "phase": "CODE"}],
            "verify_passed": False,
            "failure_context": "test failure",
        }

        with patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph), \
             patch("src.execution.story_executor.get_current_commit", return_value="abc123"), \
             patch("src.execution.story_executor.classify_failure") as mock_classify, \
             patch("asyncio.sleep", new_callable=AsyncMock):

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
