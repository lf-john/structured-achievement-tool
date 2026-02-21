import pytest
import os
import json
from unittest.mock import patch, MagicMock
from src.orchestrator import Orchestrator

@pytest.fixture
def mock_workspace(tmp_path):
    # Create a mock Obsidian task file
    task_dir = tmp_path / "task-integration-test"
    task_dir.mkdir()
    task_file = task_dir / "001.md"
    task_file.write_text("Test request")
    return str(task_file)

@patch("src.core.story_agent.StoryAgent.classify")
@patch("src.core.story_agent.StoryAgent.decompose")
@patch("src.core.phase_runner.PhaseRunner.execute_cli")
def test_full_orchestration_flow(mock_execute, mock_decompose, mock_classify, mock_workspace):
    # Setup mocks
    mock_classify.return_value = {"task_type": "research", "confidence": 1.0}
    mock_decompose.return_value = {
        "stories": [
            {
                "id": "US-001",
                "title": "Mock Story",
                "description": "Mock Description",
                "phases": ["PLAN", "EXECUTE"]
            }
        ]
    }
    mock_execute.return_value = {"stdout": "Success", "stderr": "", "exit_code": 0}

    # Run orchestrator
    orch = Orchestrator(project_path="/tmp", api_key="fake")
    report = orch.process_task_file(mock_workspace)

    # Assertions
    assert report["classification"]["task_type"] == "research"
    assert len(report["execution"]) == 1
    assert report["execution"][0]["story_id"] == "US-001"
    assert len(report["execution"][0]["results"]) == 2 # PLAN and EXECUTE
    assert report["execution"][0]["results"][0]["phase"] == "PLAN"
    
    # Verify CLI was called correctly
    assert mock_execute.call_count == 2
