import asyncio
import os
import shutil
from src.execution.story_executor import execute_story
from src.llm.routing_engine import RoutingEngine

async def run_test():
    working_directory = "/tmp/test_checkpoints"
    os.makedirs(working_directory, exist_ok=True)
    if os.path.exists(os.path.join(working_directory, ".memory")):
        shutil.rmtree(os.path.join(working_directory, ".memory"))
        
    story = {
        "id": "US-TEST-001",
        "title": "Test Story",
        "type": "development", # Will use DevTDDWorkflow
        "tdd": False
    }
    
    # Run the story (it might fail because no LLM, but it should create the checkpoint db)
    # Actually let's mock the compile or invoke so it doesn't need LLM
    from unittest.mock import patch, MagicMock
    
    with patch("src.execution.story_executor.get_workflow_for_story") as mock_get_workflow:
        mock_graph = MagicMock()
        mock_graph.get_state.return_value = MagicMock(values=None) # no existing state
        mock_graph.invoke.return_value = {
            "phase_outputs": [{"status": "complete", "phase": "test"}]
        }
        mock_get_workflow.return_value = mock_graph
        
        result = await execute_story(
            story=story,
            task_id="TASK-123",
            task_description="Test description",
            working_directory=working_directory,
            routing_engine=MagicMock(),
        )
        
    db_path = os.path.join(working_directory, ".memory", "checkpoints.db")
    if not os.path.exists(db_path):
        print("FAIL: Checkpoint db was not created.")
        exit(1)
        
    print("SUCCESS: Checkpoint db was created and execute_story ran successfully.")

if __name__ == "__main__":
    asyncio.run(run_test())
