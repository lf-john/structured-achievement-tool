"""
IMPLEMENTATION PLAN for US-002:

Components:
  - execute_story (in src/execution/story_executor.py): Will be modified to call write_checkpoint.
  - src.core.checkpoint_manager: Provides checkpoint storage logic.

Test Cases:
  1. [AC 1] -> test_should_write_checkpoint_after_successful_story_execution
     - Execute a story successfully.
     - Verify write_checkpoint was called.
  2. [AC 2] -> test_checkpoint_should_reflect_completed_and_pending_stories
     - Mock read_checkpoint to return an existing checkpoint.
     - Execute a new story.
     - Verify write_checkpoint was called with updated completed/pending lists.

Edge Cases:
  - Story execution fails: Verify write_checkpoint is NOT called.
  - Checkpoint manager error: Verify execution continues (graceful degradation).
  - Checkpoint doesn't exist: Verify a new one is created.
"""

import sys
import os
import asyncio
import pytest
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.execution.story_executor import execute_story
from src.core.checkpoint_manager import Checkpoint

@pytest.mark.asyncio
async def test_should_write_checkpoint_after_successful_story_execution():
    """AC 1: Checkpoints are persisted immediately after each story in a workflow."""
    working_dir = "/tmp/sat_test_us_002_level_ac1"
    os.makedirs(working_dir, exist_ok=True)
    
    story = {"id": "STORY-AC1", "title": "Test Story", "type": "development"}
    task_id = "TASK-AC1"
    
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"phase_outputs": [{"status": "complete"}], "verify_passed": True}
    mock_graph.get_state.return_value = MagicMock(values=None)
    
    # We patch the functions in story_executor where they SHOULD be imported
    with (
        patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph),
        patch("src.execution.story_executor.get_current_commit", return_value="hash123"),
        patch("src.execution.story_executor.RoutingEngine"),
        patch("src.execution.story_executor.Notifier"),
        patch("src.execution.story_executor.write_checkpoint") as mock_write_checkpoint,
        patch("src.execution.story_executor.read_checkpoint") as mock_read_checkpoint
    ):
        mock_read_checkpoint.return_value = None
        
        await execute_story(
            story=story,
            task_id=task_id,
            task_description="desc",
            working_directory=working_dir,
            max_attempts=1
        )
        
        # Verify write_checkpoint was called
        mock_write_checkpoint.assert_called()
        checkpoint = mock_write_checkpoint.call_args[0][1]
        assert checkpoint.task_id == task_id
        assert "STORY-AC1" in checkpoint.completed_stories

@pytest.mark.asyncio
async def test_checkpoint_should_reflect_completed_and_pending_stories():
    """AC 2: The state accurately reflects completed and pending stories."""
    working_dir = "/tmp/sat_test_us_002_level_ac2"
    os.makedirs(working_dir, exist_ok=True)
    
    story = {"id": "STORY-2", "title": "Test Story 2", "type": "development"}
    task_id = "TASK-2"
    
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"phase_outputs": [{"status": "complete"}], "verify_passed": True}
    mock_graph.get_state.return_value = MagicMock(values=None)
    
    # Existing checkpoint
    existing_checkpoint = Checkpoint(
        task_id=task_id,
        current_phase="EXECUTION",
        completed_stories=["STORY-1"],
        pending_stories=["STORY-2", "STORY-3"]
    )
    
    with (
        patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph),
        patch("src.execution.story_executor.get_current_commit", return_value="hash123"),
        patch("src.execution.story_executor.RoutingEngine"),
        patch("src.execution.story_executor.Notifier"),
        patch("src.execution.story_executor.write_checkpoint") as mock_write_checkpoint,
        patch("src.execution.story_executor.read_checkpoint") as mock_read_checkpoint
    ):
        mock_read_checkpoint.return_value = existing_checkpoint
        
        await execute_story(
            story=story,
            task_id=task_id,
            task_description="desc",
            working_directory=working_dir,
            max_attempts=1
        )
        
        # Verify write_checkpoint was called with updated state
        mock_write_checkpoint.assert_called()
        checkpoint = mock_write_checkpoint.call_args[0][1]
        
        assert "STORY-1" in checkpoint.completed_stories
        assert "STORY-2" in checkpoint.completed_stories
        assert "STORY-2" not in checkpoint.pending_stories
        assert "STORY-3" in checkpoint.pending_stories

@pytest.mark.asyncio
async def test_should_not_write_checkpoint_on_failure():
    """Edge Case: Checkpoint is NOT updated on failure."""
    working_dir = "/tmp/sat_test_us_002_level_fail"
    os.makedirs(working_dir, exist_ok=True)
    
    story = {"id": "STORY-FAIL", "title": "Failed Story", "type": "development"}
    task_id = "TASK-FAIL"
    
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"phase_outputs": [{"status": "failed"}], "verify_passed": False}
    mock_graph.get_state.return_value = MagicMock(values=None)
    
    with (
        patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph),
        patch("src.execution.story_executor.get_current_commit", return_value="hash123"),
        patch("src.execution.story_executor.RoutingEngine"),
        patch("src.execution.story_executor.Notifier"),
        patch("src.execution.story_executor.write_checkpoint") as mock_write_checkpoint,
        patch("src.execution.story_executor.read_checkpoint") as mock_read_checkpoint
    ):
        mock_read_checkpoint.return_value = None
        
        await execute_story(
            story=story,
            task_id=task_id,
            task_description="desc",
            working_directory=working_dir,
            max_attempts=1
        )
        
        # Verify write_checkpoint was NOT called
        mock_write_checkpoint.assert_not_called()

@pytest.mark.asyncio
async def test_should_handle_checkpoint_manager_errors_gracefully():
    """Edge Case: If checkpoint writing fails, the story execution should still succeed."""
    working_dir = "/tmp/sat_test_us_002_level_graceful"
    os.makedirs(working_dir, exist_ok=True)
    
    story = {"id": "STORY-OK", "title": "Successful Story", "type": "development"}
    task_id = "TASK-OK"
    
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"phase_outputs": [{"status": "complete"}], "verify_passed": True}
    mock_graph.get_state.return_value = MagicMock(values=None)
    
    with (
        patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph),
        patch("src.execution.story_executor.get_current_commit", return_value="hash123"),
        patch("src.execution.story_executor.RoutingEngine"),
        patch("src.execution.story_executor.Notifier"),
        patch("src.execution.story_executor.write_checkpoint", side_effect=Exception("DB Error")) as mock_write_checkpoint,
        patch("src.execution.story_executor.read_checkpoint") as mock_read_checkpoint
    ):
        mock_read_checkpoint.return_value = None
        
        result = await execute_story(
            story=story,
            task_id=task_id,
            task_description="desc",
            working_directory=working_dir,
            max_attempts=1
        )
        
        # Story should still be marked as success
        assert result.success is True
        # write_checkpoint was called but failed
        mock_write_checkpoint.assert_called()

if __name__ == "__main__":
    import pytest
    fail_count = pytest.main([__file__, "--import-mode=importlib"])
    sys.exit(1 if fail_count > 0 else 0)
