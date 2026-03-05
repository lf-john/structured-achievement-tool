"""
pytest configuration for the project.
This file ensures that the src directory is in the Python path.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the project root directory to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Create a mock default_api module if it doesn't exist (Ralph Pro dependency)
if "default_api" not in sys.modules:
    mock_module = types.ModuleType("default_api")
    mock_module.run_shell_command = MagicMock(return_value={"output": "(mocked output)", "exit_code": 0})
    mock_module.read_file = MagicMock(return_value={"output": "(mocked file content)"})
    mock_module.write_file = MagicMock(return_value={"output": "Successfully wrote to mocked file."})
    mock_module.replace = MagicMock(return_value={"output": "Successfully replaced in mocked file."})
    mock_module.list_directory = MagicMock(return_value={"output": "mocked_dir_listing"})
    mock_module.grep_search = MagicMock(return_value={"output": "mocked_grep_output"})
    mock_module.glob = MagicMock(return_value={"output": ["mocked_file1", "mocked_file2"]})
    mock_module.web_fetch = MagicMock(return_value={"output": "mocked_web_fetch_output"})
    mock_module.save_memory = MagicMock(return_value={"output": "mocked_save_memory_output"})
    mock_module.google_web_search = MagicMock(return_value={"output": "mocked_google_web_search_output"})
    mock_module.write_todos = MagicMock(return_value={"output": "mocked_write_todos_output"})
    mock_module.codebase_investigator = MagicMock(return_value={"output": "mocked_codebase_investigator_output"})
    mock_module.cli_help = MagicMock(return_value={"output": "mocked_cli_help_output"})
    mock_module.activate_skill = MagicMock(return_value={"output": "mocked_activate_skill_output"})
    sys.modules["default_api"] = mock_module


@pytest.fixture(autouse=True)
def mock_default_api_tools():
    """
    Globally mocks default_api tools to prevent actual calls during tests.
    """
    with (
        patch("default_api.run_shell_command") as mock_run_shell_command,
        patch("default_api.read_file") as mock_read_file,
        patch("default_api.write_file") as mock_write_file,
        patch("default_api.replace") as mock_replace,
        patch("default_api.list_directory") as mock_list_directory,
        patch("default_api.grep_search") as mock_grep_search,
        patch("default_api.glob") as mock_glob,
        patch("default_api.web_fetch") as mock_web_fetch,
        patch("default_api.save_memory") as mock_save_memory,
        patch("default_api.google_web_search") as mock_google_web_search,
        patch("default_api.write_todos") as mock_write_todos,
        patch("default_api.codebase_investigator") as mock_codebase_investigator,
        patch("default_api.cli_help") as mock_cli_help,
        patch("default_api.activate_skill") as mock_activate_skill,
    ):
        mock_run_shell_command.return_value = {"output": "(mocked output)", "exit_code": 0}
        mock_read_file.return_value = {"output": "(mocked file content)"}
        mock_write_file.return_value = {"output": "Successfully wrote to mocked file."}
        mock_replace.return_value = {"output": "Successfully replaced in mocked file."}
        mock_list_directory.return_value = {"output": "mocked_dir_listing"}
        mock_grep_search.return_value = {"output": "mocked_grep_output"}
        mock_glob.return_value = {"output": ["mocked_file1", "mocked_file2"]}
        mock_web_fetch.return_value = {"output": "mocked_web_fetch_output"}
        mock_save_memory.return_value = {"output": "mocked_save_memory_output"}
        mock_google_web_search.return_value = {"output": "mocked_google_web_search_output"}
        mock_write_todos.return_value = {"output": "mocked_write_todos_output"}
        mock_codebase_investigator.return_value = {"output": "mocked_codebase_investigator_output"}
        mock_cli_help.return_value = {"output": "mocked_cli_help_output"}
        mock_activate_skill.return_value = {"output": "mocked_activate_skill_output"}

        yield
