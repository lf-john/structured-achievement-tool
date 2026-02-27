import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath("."))
from src.core.checkpoint_manager import init_db, read_checkpoint, Checkpoint, write_checkpoint
from src.execution.story_executor import _execute_story_inner
import shutil

async def main():
    working_dir = "/tmp/sat_test_us_002"
    if os.path.exists(working_dir):
        shutil.rmtree(working_dir)
    os.makedirs(working_dir)

    db_path = os.path.join(working_dir, ".memory", "checkpoints.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Init DB and initial checkpoint
    init_db(db_path)
    chk = Checkpoint(
        task_id="TASK-ABC",
        current_phase="EXECUTION",
        completed_stories=[],
        pending_stories=["STORY-XYZ", "STORY-123"]
    )
    write_checkpoint(db_path, chk)
    
    # Mock routing engine and graph
    mock_routing = MagicMock()
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"phase_outputs": [{"status": "complete"}], "verify_passed": True}
    mock_graph.get_state.return_value = MagicMock(values=None)

    with patch("src.execution.story_executor.get_workflow_for_story", return_value=mock_graph), \
         patch("src.execution.story_executor.get_current_commit", return_value="hash"):
         
         await _execute_story_inner(
             story={"id": "STORY-XYZ", "title": "Test Story"},
             task_id="TASK-ABC",
             task_description="test",
             working_directory=working_dir,
             routing_engine=mock_routing,
             max_attempts=1
         )
         
    # Verify
    updated_chk = read_checkpoint(db_path, "TASK-ABC")
    if updated_chk is None:
        print("Checkpoint not found!")
        sys.exit(1)
        
    if "STORY-XYZ" not in updated_chk.completed_stories:
        print(f"STORY-XYZ not in completed_stories. Current: {updated_chk.completed_stories}")
        sys.exit(1)
        
    if "STORY-XYZ" in updated_chk.pending_stories:
        print("STORY-XYZ still in pending_stories")
        sys.exit(1)
        
    print("Integration test passed!")
    
if __name__ == "__main__":
    asyncio.run(main())
