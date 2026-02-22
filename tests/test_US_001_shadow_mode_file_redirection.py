"""
IMPLEMENTATION PLAN for US-001: Shadow Mode File Redirection in Orchestrator

This test file verifies that file write operations are actually redirected to _shadow/
when shadow_mode is enabled. These tests FAIL because the current implementation
calculates output_dir but doesn't actually use it for file operations.

Components:
  - Orchestrator.execute_story: Should use shadow_dir for file writes
    * Currently calculates output_dir but passes task_dir to execute_cli
    * Should pass output_dir (shadow_dir) to execute_cli when shadow_mode=True

  - Orchestrator.process_task_file: Should use shadow_dir for status file writes
    * Status files should be written to task_dir/_shadow when shadow_mode=True

Test Cases:
  1. Files written to shadow directory when shadow_mode=true
     -> test_execute_story_writes_to_shadow_dir
     -> test_process_task_file_writes_status_to_shadow_dir

  2. Files written to main directory when shadow_mode=false
     -> test_execute_story_writes_to_main_dir_when_shadow_mode_false

  3. Shadow directory is created before file writes
     -> test_shadow_dir_created_before_writes

Edge Cases:
  - Shadow mode with multiple story executions
  - Shadow mode with DAG executor
  - Shadow mode with nested directories
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, Mock, MagicMock, call
import sys

from src.orchestrator import Orchestrator


class TestExecuteStoryFileRedirection:
    """Test that execute_story actually redirects file writes to shadow directory."""

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    @patch('src.core.phase_runner.PhaseRunner.get_phases')
    def test_execute_story_passes_shadow_dir_to_cli_when_shadow_mode_true(self, mock_get_phases, mock_execute_cli):
        """Test that execute_story passes shadow_dir to execute_cli when shadow_mode=True."""
        # Setup mocks
        mock_get_phases.return_value = ['PLAN', 'CODE']
        mock_execute_cli.return_value = {
            'stdout': 'Phase completed',
            'stderr': '',
            'exit_code': 0
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            shadow_dir = os.path.join(task_dir, "_shadow")

            orchestrator = Orchestrator(
                project_path="/tmp/test",
                api_key="fake_key",
                shadow_mode=True
            )

            story = {
                "id": "US-001",
                "title": "Test Story",
                "description": "Test description",
            }

            import asyncio
            result = asyncio.run(orchestrator.execute_story(story, task_dir))

            # This test FAILS because execute_cli is called with task_dir, not shadow_dir
            # Verify execute_cli was called with shadow_dir
            assert mock_execute_cli.called
            calls = mock_execute_cli.call_args_list

            # Each call should have shadow_dir as the task_dir argument
            for call_item in calls:
                # Check both positional and keyword arguments
                actual_task_dir = None
                if len(call_item[0]) >= 3:
                    actual_task_dir = call_item[0][2]
                elif 'task_dir' in call_item[1]:
                    actual_task_dir = call_item[1]['task_dir']

                assert actual_task_dir is not None, "execute_cli should receive task_dir argument"
                assert actual_task_dir == shadow_dir, \
                    f"execute_cli should receive shadow_dir ({shadow_dir}), got {actual_task_dir}"

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    @patch('src.core.phase_runner.PhaseRunner.get_phases')
    def test_execute_story_passes_task_dir_to_cli_when_shadow_mode_false(self, mock_get_phases, mock_execute_cli):
        """Test that execute_story passes task_dir to execute_cli when shadow_mode=False."""
        mock_get_phases.return_value = ['PLAN']
        mock_execute_cli.return_value = {
            'stdout': 'Phase completed',
            'stderr': '',
            'exit_code': 0
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            orchestrator = Orchestrator(
                project_path="/tmp/test",
                api_key="fake_key",
                shadow_mode=False
            )

            story = {
                "id": "US-001",
                "title": "Test Story",
                "description": "Test description",
            }

            import asyncio
            result = asyncio.run(orchestrator.execute_story(story, task_dir))

            # Verify execute_cli was called with task_dir (not shadow_dir)
            assert mock_execute_cli.called
            call_args = mock_execute_cli.call_args

            # The task_dir argument should be the original task_dir
            actual_task_dir = None
            if len(call_args[0]) >= 3:
                actual_task_dir = call_args[0][2]
            elif 'task_dir' in call_args[1]:
                actual_task_dir = call_args[1]['task_dir']

            assert actual_task_dir is not None, "execute_cli should receive task_dir argument"
            assert actual_task_dir == task_dir, \
                f"execute_cli should receive task_dir ({task_dir}), got {actual_task_dir}"
            assert "_shadow" not in actual_task_dir, \
                "task_dir should not contain _shadow when shadow_mode=False"


class TestShadowDirCreationBeforeFileWrites:
    """Test that shadow directory is created before any file writes."""

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    @patch('src.core.phase_runner.PhaseRunner.get_phases')
    def test_shadow_dir_exists_before_first_cli_call(self, mock_get_phases, mock_execute_cli):
        """Test that shadow directory exists before the first CLI call."""
        mock_get_phases.return_value = ['PLAN', 'CODE']

        # Track when directory is created vs when CLI is called
        cli_call_count = [0]
        shadow_dir_path = [None]

        original_execute_cli = mock_execute_cli

        def side_effect_check_shadow(*args, **kwargs):
            cli_call_count[0] += 1
            task_dir_used = None
            if len(args) >= 3:
                task_dir_used = args[2]
            elif 'task_dir' in kwargs:
                task_dir_used = kwargs['task_dir']

            if task_dir_used:
                shadow_dir_path[0] = task_dir_used

                # Check if shadow_dir exists at this point
                if "_shadow" in task_dir_used:
                    # This test will FAIL because shadow_dir won't exist yet
                    assert os.path.exists(task_dir_used), \
                        f"Shadow directory should exist before CLI call, but {task_dir_used} doesn't exist"

            return {
                'stdout': 'Phase output',
                'stderr': '',
                'exit_code': 0
            }

        mock_execute_cli.side_effect = side_effect_check_shadow

        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            orchestrator = Orchestrator(
                project_path="/tmp/test",
                api_key="fake_key",
                shadow_mode=True
            )

            story = {
                "id": "US-001",
                "title": "Test Story",
                "description": "Test description",
            }

            import asyncio
            try:
                result = asyncio.run(orchestrator.execute_story(story, task_dir))

                # If we got here, verify that shadow_dir was passed to CLI
                # (This will fail until implementation is fixed)
                assert shadow_dir_path[0] is not None, "Shadow dir should have been passed to CLI"
                assert "_shadow" in shadow_dir_path[0], "Shadow dir should contain _shadow"
            except AssertionError as e:
                # Expected to fail until implementation is fixed
                raise


class TestProcessTaskFileShadowMode:
    """Test that process_task_file respects shadow_mode for status files."""

    @patch('src.core.story_agent.StoryAgent.classify')
    @patch('src.core.story_agent.StoryAgent.decompose')
    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    @patch('src.core.phase_runner.PhaseRunner.get_phases')
    def test_process_task_file_creates_shadow_dir(self, mock_get_phases, mock_execute_cli, mock_decompose, mock_classify):
        """Test that process_task_file creates shadow directory when shadow_mode=True."""
        mock_classify.return_value = {"task_type": "research", "confidence": 1.0}
        mock_decompose.return_value = {
            "stories": [
                {
                    "id": "US-001",
                    "title": "Mock Story",
                    "description": "Mock Description",
                    "phases": ["PLAN"]
                }
            ]
        }
        mock_get_phases.return_value = ['PLAN']
        mock_execute_cli.return_value = {"stdout": "Success", "stderr": "", "exit_code": 0}

        with tempfile.TemporaryDirectory() as tmp_dir:
            task_file = os.path.join(tmp_dir, "001.md")
            with open(task_file, "w") as f:
                f.write("Test request")

            task_dir = tmp_dir
            shadow_dir = os.path.join(task_dir, "_shadow")

            # Shadow dir shouldn't exist yet
            assert not os.path.exists(shadow_dir)

            orch = Orchestrator(project_path="/tmp", api_key="fake", shadow_mode=True)

            import asyncio
            result = asyncio.run(orch.process_task_file(task_file))

            # Shadow directory should be created
            # This test PASSES because _ensure_shadow_dir is called
            # BUT the actual file writes don't use it - that's tested elsewhere
            assert os.path.exists(shadow_dir), \
                "Shadow directory should be created when shadow_mode=True"

            # Now verify that execute_cli was called with shadow_dir
            # This will FAIL until the implementation is fixed
            assert mock_execute_cli.called
            calls = mock_execute_cli.call_args_list
            shadow_dir_used = False
            for call in calls:
                task_dir_used = None
                if len(call[0]) >= 3:
                    task_dir_used = call[0][2]
                elif 'task_dir' in call[1]:
                    task_dir_used = call[1]['task_dir']

                if task_dir_used == shadow_dir:
                    shadow_dir_used = True
                    break

            assert shadow_dir_used, \
                f"process_task_file should use shadow_dir ({shadow_dir}) when shadow_mode=True"

    @patch('src.core.story_agent.StoryAgent.classify')
    @patch('src.core.story_agent.StoryAgent.decompose')
    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    @patch('src.core.phase_runner.PhaseRunner.get_phases')
    def test_process_task_file_no_shadow_dir_when_shadow_mode_false(self, mock_get_phases, mock_execute_cli, mock_decompose, mock_classify):
        """Test that process_task_file doesn't create shadow directory when shadow_mode=False."""
        mock_classify.return_value = {"task_type": "research", "confidence": 1.0}
        mock_decompose.return_value = {
            "stories": [
                {
                    "id": "US-001",
                    "title": "Mock Story",
                    "description": "Mock Description",
                    "phases": ["PLAN"]
                }
            ]
        }
        mock_get_phases.return_value = ['PLAN']
        mock_execute_cli.return_value = {"stdout": "Success", "stderr": "", "exit_code": 0}

        with tempfile.TemporaryDirectory() as tmp_dir:
            task_file = os.path.join(tmp_dir, "001.md")
            with open(task_file, "w") as f:
                f.write("Test request")

            task_dir = tmp_dir
            shadow_dir = os.path.join(task_dir, "_shadow")

            orch = Orchestrator(project_path="/tmp", api_key="fake", shadow_mode=False)

            import asyncio
            result = asyncio.run(orch.process_task_file(task_file))

            # Shadow directory should NOT be created
            assert not os.path.exists(shadow_dir), \
                "Shadow directory should NOT be created when shadow_mode=False"


class TestIntegrationWithDAGExecutor:
    """Test that shadow_mode works correctly with DAG executor."""

    @patch('src.core.story_agent.StoryAgent.classify')
    @patch('src.core.story_agent.StoryAgent.decompose')
    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    @patch('src.core.phase_runner.PhaseRunner.get_phases')
    def test_dag_executor_receives_shadow_dir(self, mock_get_phases, mock_execute_cli, mock_decompose, mock_classify):
        """Test that DAG executor operations use shadow_dir when shadow_mode=True."""
        mock_classify.return_value = {"task_type": "research", "confidence": 1.0}
        mock_decompose.return_value = {
            "stories": [
                {
                    "id": "US-001",
                    "title": "Story 1",
                    "description": "Description 1",
                    "phases": ["PLAN"]
                },
                {
                    "id": "US-002",
                    "title": "Story 2",
                    "description": "Description 2",
                    "phases": ["PLAN"]
                }
            ]
        }
        mock_get_phases.return_value = ['PLAN']
        mock_execute_cli.return_value = {"stdout": "Success", "stderr": "", "exit_code": 0}

        with tempfile.TemporaryDirectory() as tmp_dir:
            task_file = os.path.join(tmp_dir, "001.md")
            with open(task_file, "w") as f:
                f.write("Test request")

            task_dir = tmp_dir
            shadow_dir = os.path.join(task_dir, "_shadow")

            orch = Orchestrator(project_path="/tmp", api_key="fake", shadow_mode=True)

            import asyncio
            result = asyncio.run(orch.process_task_file(task_file))

            # Verify CLI was called with shadow_dir
            assert mock_execute_cli.called
            calls = mock_execute_cli.call_args_list

            # At least one call should have been made with shadow_dir
            shadow_dir_used = False
            for call in calls:
                task_dir_used = None
                if len(call[0]) >= 3:
                    task_dir_used = call[0][2]
                elif 'task_dir' in call[1]:
                    task_dir_used = call[1]['task_dir']

                if task_dir_used == shadow_dir:
                    shadow_dir_used = True
                    break

            # This test FAILS until implementation is fixed
            assert shadow_dir_used, \
                f"DAG executor should use shadow_dir ({shadow_dir}) when shadow_mode=True"


# Track test failures for exit code
fail_count = 0


def pytest_configure(config):
    """Configure pytest to track failures."""
    global fail_count


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Called at end of test session to determine exit code."""
    global fail_count
    fail_count = 1 if exitstatus != 0 else 0


if __name__ == "__main__":
    # Run pytest programmatically and exit with appropriate code
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)
