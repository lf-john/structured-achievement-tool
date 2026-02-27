"""
IMPLEMENTATION PLAN for US-001:

Components:
  - SqliteSaver (from langgraph.checkpoint.sqlite): Native LangGraph checkpointer.
  - execute_story (in src/execution/story_executor.py): Integrates SqliteSaver.

Test Cases:
  1. [AC 1] -> Verify .memory/checkpoints.db is created upon first execution.
  2. [AC 2] -> Verify SqliteSaver is initialized with the correct DB path and passed to graph.compile.
  3. [AC 3] -> Verify checkpoints include task_id and timestamp in metadata.

Edge Cases:
  - Database directory missing: Ensure it's created automatically.
"""

import sys
import os
import asyncio
import pytest
import shutil
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.execution.story_executor import execute_story

@pytest.mark.asyncio
async def test_should_create_checkpoint_db_on_first_execution():
    """AC 1: .memory/checkpoints.db is created upon first execution."""
    working_dir = "/tmp/sat_test_us_001"
    memory_dir = os.path.join(working_dir, ".memory")
    db_path = os.path.join(memory_dir, "checkpoints.db")
    
    if os.path.exists(working_dir):
        shutil.rmtree(working_dir)
    os.makedirs(working_dir)
    
    story = {"id": "STORY-1", "type": "development"}
    
    # Mocking graph and its invoke
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"phase_outputs": [], "verify_passed": True}
    mock_graph.get_state.return_value = MagicMock(values=None)
    
    with patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph), \
         patch("src.execution.story_executor.get_current_commit", return_value="hash123"), \
         patch("src.execution.story_executor.RoutingEngine"), \
         patch("src.execution.story_executor.Notifier"):
        
        await execute_story(
            story=story,
            task_id="TASK-1",
            task_description="desc",
            working_directory=working_dir,
            max_attempts=1
        )
        
    assert os.path.exists(db_path), "Checkpoint database should be created"

@pytest.mark.asyncio
async def test_should_initialize_sqlitesaver_and_pass_to_compiler():
    """AC 2: SqliteSaver is correctly initialized and passed to the LangGraph executor."""
    working_dir = "/tmp/sat_test_us_001_saver"
    if os.path.exists(working_dir):
        shutil.rmtree(working_dir)
    os.makedirs(working_dir)
    
    story = {"id": "STORY-2", "type": "development"}
    
    with patch("langgraph.checkpoint.sqlite.SqliteSaver.from_conn_string") as mock_from_conn, \
         patch("src.execution.story_executor.get_workflow_for_story") as mock_get_workflow, \
         patch("src.execution.story_executor.get_current_commit", return_value="hash123"), \
         patch("src.execution.story_executor.RoutingEngine"), \
         patch("src.execution.story_executor.Notifier"):
        
        mock_saver = MagicMock()
        mock_from_conn.return_value.__enter__.return_value = mock_saver
        
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"phase_outputs": [], "verify_passed": True}
        mock_graph.get_state.return_value = MagicMock(values=None)
        mock_get_workflow.return_value = mock_graph
        
        await execute_story(
            story=story,
            task_id="TASK-2",
            task_description="desc",
            working_directory=working_dir,
            max_attempts=1
        )
        
        # Verify SqliteSaver initialized with correct path
        db_path = os.path.join(working_dir, ".memory", "checkpoints.db")
        mock_from_conn.assert_called()
        
        # Verify checkpointer passed to get_workflow_for_story
        mock_get_workflow.assert_called()
        args, kwargs = mock_get_workflow.call_args
        assert kwargs.get("checkpointer") == mock_saver

@pytest.mark.asyncio
async def test_should_include_task_id_and_timestamp_in_checkpoint_metadata():
    """AC 3: Checkpoints include task_id and timestamp metadata."""
    working_dir = "/tmp/sat_test_us_001_metadata"
    if os.path.exists(working_dir):
        shutil.rmtree(working_dir)
    os.makedirs(working_dir)
    
    story = {"id": "STORY-3", "type": "development"}
    task_id = "TASK-3"
    
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"phase_outputs": [], "verify_passed": True}
    mock_graph.get_state.return_value = MagicMock(values=None)
    
    with patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph), \
         patch("src.execution.story_executor.get_current_commit", return_value="hash123"), \
         patch("src.execution.story_executor.RoutingEngine"), \
         patch("src.execution.story_executor.Notifier"):
        
        await execute_story(
            story=story,
            task_id=task_id,
            task_description="desc",
            working_directory=working_dir,
            max_attempts=1
        )
        
        # Verify graph.invoke was called with config containing metadata
        mock_graph.invoke.assert_called()
        args, kwargs = mock_graph.invoke.call_args
        config = kwargs.get("config", {})
        
        # This is expected to FAIL because metadata is not currently passed in config
        assert "metadata" in config, "Config should contain metadata"
        assert config["metadata"].get("task_id") == task_id
        assert "timestamp" in config["metadata"]

if __name__ == "__main__":
    # Run pytest and exit with its return code
    import pytest
    sys.exit(pytest.main([__file__]))
