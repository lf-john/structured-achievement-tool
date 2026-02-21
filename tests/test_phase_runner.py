import pytest
from unittest.mock import patch, MagicMock
from src.core.phase_runner import PhaseRunner

def test_runner_initialization():
    runner = PhaseRunner(project_path="/tmp/project")
    assert runner.project_path == "/tmp/project"

@patch("subprocess.run")
def test_execute_phase_claude(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Claude output", stderr="")
    
    runner = PhaseRunner(project_path="/tmp/project")
    result = runner.execute_cli(
        provider="anthropic",
        prompt="Hello",
        task_dir="/tmp/task"
    )
    
    assert result["stdout"] == "Claude output"
    assert result["exit_code"] == 0
    # Verify the correct command was called
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0][0] == "claude"
    assert "-p" in args[0]

@patch("subprocess.run")
def test_execute_phase_gemini(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Gemini output", stderr="")
    
    runner = PhaseRunner(project_path="/tmp/project")
    result = runner.execute_cli(
        provider="google",
        prompt="Hello",
        task_dir="/tmp/task"
    )
    
    assert result["stdout"] == "Gemini output"
    
    # Precise check
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0][0] == "gemini"

def test_dynamic_phases_config():
    # Verify that we can pass a custom list of phases
    story = {
        "id": "US-001",
        "phases": ["PLAN", "EXECUTE", "VERIFY-SCRIPT"]
    }
    runner = PhaseRunner(project_path="/tmp/project")
    phases = runner.get_phases(story)
    assert phases == ["PLAN", "EXECUTE", "VERIFY-SCRIPT"]

def test_default_tdd_phases():
    story = {
        "id": "US-002",
        "tdd": True
    }
    runner = PhaseRunner(project_path="/tmp/project")
    phases = runner.get_phases(story)
    assert "TDD-RED" in phases
    assert "CODE" in phases
