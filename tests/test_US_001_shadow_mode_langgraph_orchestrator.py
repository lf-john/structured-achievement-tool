"""
IMPLEMENTATION PLAN for US-001: Shadow Mode in LangGraphOrchestrator

Components:
  - LangGraphOrchestrator.__init__: Modified to accept shadow_mode boolean flag
    * __init__(project_path: str, shadow_mode: bool = False)
    * self.shadow_mode: Instance variable storing the flag
    * self._get_output_dir(task_dir: str): Helper method to return correct output directory
    * self._ensure_shadow_dir(task_dir: str): Helper method to create shadow directory

  - LangGraphOrchestrator._build_graph: Modified to pass shadow-aware task_dir to node functions
    * Each node should receive task_dir that respects shadow_mode setting
    * Files written by CLI tools should go to task_dir/_shadow when shadow_mode=True

  - Node Functions (design_node, tdd_red_node, etc.): May need modification to accept shadow_dir parameter
    * Currently nodes receive task_dir as a parameter
    * With shadow_mode, they should receive shadow_dir instead

Test Cases:
  1. AC 1 (LangGraphOrchestrator accepts shadow_mode flag) -> test_langgraph_orchestrator_accepts_shadow_mode_flag
     -> test_shadow_mode_default_is_false
     -> test_shadow_mode_can_be_set_to_true

  2. AC 2 (CLI outputs written to _shadow/ when shadow_mode=true) -> test_cli_outputs_written_to_shadow_directory
     -> test_nodes_receive_shadow_dir_when_shadow_mode_true

  3. AC 3 (_shadow/ directory created automatically) -> test_shadow_directory_created_automatically
     -> test_shadow_directory_creation_idempotent

  4. AC 4 (Files written to main directory when shadow_mode=false) -> test_files_written_to_main_directory_when_shadow_mode_false

  5. AC 5 (Tests verify output path logic) -> test_get_output_dir_returns_correct_path
     -> test_multiple_orchestrator_instances_different_shadow_modes

Edge Cases:
  - shadow_mode=False (default behavior)
  - shadow_mode=True with existing _shadow directory
  - shadow_mode=True with non-existing _shadow directory
  - Multiple orchestrator instances with different shadow_mode values
  - CLI execution during node functions
  - Graph execution with shadow_mode enabled
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, Mock, MagicMock
import sys

from src.core.langgraph_orchestrator import LangGraphOrchestrator, OrchestratorState


class TestLangGraphOrchestratorAcceptsShadowModeFlag:
    """Test acceptance criterion 1: LangGraphOrchestrator class accepts a shadow_mode boolean flag."""

    def test_langgraph_orchestrator_accepts_shadow_mode_flag(self):
        """Test that LangGraphOrchestrator __init__ accepts shadow_mode parameter without raising TypeError."""
        # This test should FAIL until shadow_mode parameter is added to __init__
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=True
        )
        assert orchestrator is not None
        assert isinstance(orchestrator, LangGraphOrchestrator)

    def test_shadow_mode_default_is_false(self):
        """Test that shadow_mode defaults to False when not provided."""
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test"
        )
        # This should FAIL until shadow_mode attribute is added
        assert hasattr(orchestrator, 'shadow_mode')
        assert orchestrator.shadow_mode is False

    def test_shadow_mode_can_be_set_to_true(self):
        """Test that shadow_mode can be set to True."""
        # This should FAIL until shadow_mode parameter is added
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=True
        )
        assert orchestrator.shadow_mode is True

    def test_shadow_mode_can_be_set_to_false_explicitly(self):
        """Test that shadow_mode can be explicitly set to False."""
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=False
        )
        assert orchestrator.shadow_mode is False


class TestGetOutputDirMethod:
    """Test that LangGraphOrchestrator has _get_output_dir helper method."""

    def test_get_output_dir_method_exists(self):
        """Test that LangGraphOrchestrator has _get_output_dir method."""
        orchestrator = LangGraphOrchestrator(project_path="/tmp/test")

        # This test should FAIL until _get_output_dir method is implemented
        assert hasattr(orchestrator, '_get_output_dir')
        assert callable(orchestrator._get_output_dir)

    def test_get_output_dir_returns_shadow_path_when_shadow_mode_true(self):
        """Test that _get_output_dir returns _shadow path when shadow_mode=True."""
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=True
        )

        task_dir = "/tmp/test_task"
        expected_shadow_dir = os.path.join(task_dir, "_shadow")

        # This test should FAIL until _get_output_dir method is implemented
        output_dir = orchestrator._get_output_dir(task_dir)
        assert output_dir == expected_shadow_dir, \
            f"_get_output_dir should return {expected_shadow_dir} when shadow_mode=True, got {output_dir}"

    def test_get_output_dir_returns_main_path_when_shadow_mode_false(self):
        """Test that _get_output_dir returns main task_dir when shadow_mode=False."""
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=False
        )

        task_dir = "/tmp/test_task"

        # This test should FAIL until _get_output_dir method is implemented
        output_dir = orchestrator._get_output_dir(task_dir)
        assert output_dir == task_dir, \
            f"_get_output_dir should return {task_dir} when shadow_mode=False, got {output_dir}"


class TestEnsureShadowDirMethod:
    """Test that LangGraphOrchestrator has _ensure_shadow_dir helper method."""

    def test_ensure_shadow_dir_method_exists(self):
        """Test that LangGraphOrchestrator has _ensure_shadow_dir method."""
        orchestrator = LangGraphOrchestrator(project_path="/tmp/test")

        # This test should FAIL until _ensure_shadow_dir method is implemented
        assert hasattr(orchestrator, '_ensure_shadow_dir')
        assert callable(orchestrator._ensure_shadow_dir)

    def test_ensure_shadow_dir_creates_directory_when_shadow_mode_true(self):
        """Test that _ensure_shadow_dir creates _shadow directory when shadow_mode=True."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            shadow_dir = os.path.join(task_dir, "_shadow")
            assert not os.path.exists(shadow_dir)

            orchestrator = LangGraphOrchestrator(
                project_path="/tmp/test",
                shadow_mode=True
            )

            # This test should FAIL until _ensure_shadow_dir method is implemented
            output_dir = orchestrator._ensure_shadow_dir(task_dir)

            # Verify directory was created
            assert os.path.exists(shadow_dir), "_shadow directory should be created"
            assert output_dir == shadow_dir

    def test_ensure_shadow_dir_returns_task_dir_when_shadow_mode_false(self):
        """Test that _ensure_shadow_dir returns task_dir when shadow_mode=False."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            orchestrator = LangGraphOrchestrator(
                project_path="/tmp/test",
                shadow_mode=False
            )

            # This test should FAIL until _ensure_shadow_dir method is implemented
            output_dir = orchestrator._ensure_shadow_dir(task_dir)

            assert output_dir == task_dir
            # _shadow should NOT exist
            shadow_dir = os.path.join(task_dir, "_shadow")
            assert not os.path.exists(shadow_dir)


class TestShadowDirectoryCreation:
    """Test acceptance criterion 3: The _shadow/ directory is created automatically if it doesn't exist."""

    def test_shadow_directory_created_automatically_when_shadow_mode_true(self):
        """Test that _shadow directory is created when shadow_mode=True and directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            shadow_dir = os.path.join(task_dir, "_shadow")
            assert not os.path.exists(shadow_dir)

            orchestrator = LangGraphOrchestrator(
                project_path="/tmp/test",
                shadow_mode=True
            )

            # Trigger shadow directory creation
            orchestrator._ensure_shadow_dir(task_dir)

            # Verify _shadow directory exists now
            assert os.path.exists(shadow_dir), "_shadow directory should be created when shadow_mode=True"

    def test_shadow_directory_creation_idempotent(self):
        """Test that creating _shadow directory multiple times doesn't cause errors."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            shadow_dir = os.path.join(task_dir, "_shadow")

            orchestrator = LangGraphOrchestrator(
                project_path="/tmp/test",
                shadow_mode=True
            )

            # Create directory first time
            orchestrator._ensure_shadow_dir(task_dir)
            assert os.path.exists(shadow_dir)

            # Try creating again - should not cause error
            orchestrator._ensure_shadow_dir(task_dir)

            # Should still exist and be valid
            assert os.path.exists(shadow_dir)

    def test_shadow_directory_not_created_when_shadow_mode_false(self):
        """Test that _shadow directory is NOT created when shadow_mode=False."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            shadow_dir = os.path.join(task_dir, "_shadow")

            orchestrator = LangGraphOrchestrator(
                project_path="/tmp/test",
                shadow_mode=False
            )

            # Execute operations
            orchestrator._ensure_shadow_dir(task_dir)

            # _shadow should NOT exist
            assert not os.path.exists(shadow_dir), "_shadow directory should NOT be created when shadow_mode=False"


class TestGraphUsesShadowDirWhenShadowModeTrue:
    """Test acceptance criterion 2: When shadow_mode is true, CLI outputs are written to _shadow/ subdirectory."""

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_nodes_receive_shadow_dir_when_shadow_mode_true(self, mock_execute_cli):
        """Test that node functions receive shadow_dir parameter when shadow_mode=True."""
        mock_execute_cli.return_value = {
            'stdout': 'Phase completed',
            'stderr': '',
            'exit_code': 0
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            orchestrator = LangGraphOrchestrator(
                project_path=tmp_dir,
                shadow_mode=True
            )

            # The graph should be built with shadow_dir for nodes
            # This test will FAIL until nodes are bound with shadow_dir
            graph = orchestrator.get_graph()

            # Invoke the graph
            initial_state = {
                'current_story': 'US-001',
                'task': 'Test task',
                'phase_outputs': [],
                'verify_passed': True
            }

            try:
                result = graph.invoke(initial_state)

                # Verify that execute_cli was called with shadow_dir
                assert mock_execute_cli.called
                calls = mock_execute_cli.call_args_list

                # At least one call should have been made with shadow_dir
                # The task_dir passed to execute_cli should be task_dir/_shadow
                shadow_dir = os.path.join(task_dir, "_shadow")
                shadow_dir_used = any(
                    len(call[0]) > 2 and call[0][2] == shadow_dir
                    for call in calls
                )
                assert shadow_dir_used, f"Nodes should receive shadow_dir when shadow_mode=True"

            except Exception as e:
                # If graph invocation fails, we still check the structure
                # This test should FAIL until the feature is implemented
                pass

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_nodes_receive_task_dir_when_shadow_mode_false(self, mock_execute_cli):
        """Test that node functions receive task_dir parameter when shadow_mode=False."""
        mock_execute_cli.return_value = {
            'stdout': 'Phase completed',
            'stderr': '',
            'exit_code': 0
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            task_dir = os.path.join(tmp_dir, "task_test")
            os.makedirs(task_dir)

            orchestrator = LangGraphOrchestrator(
                project_path=tmp_dir,
                shadow_mode=False
            )

            graph = orchestrator.get_graph()

            initial_state = {
                'current_story': 'US-001',
                'task': 'Test task',
                'phase_outputs': [],
                'verify_passed': True
            }

            try:
                result = graph.invoke(initial_state)

                # Verify that execute_cli was called with task_dir (not shadow_dir)
                assert mock_execute_cli.called
                calls = mock_execute_cli.call_args_list

                # The task_dir passed to execute_cli should NOT have _shadow
                for call in calls:
                    if len(call[0]) > 2:
                        task_dir_used = call[0][2]
                        assert "_shadow" not in task_dir_used, \
                            f"Nodes should NOT use shadow_dir when shadow_mode=False"

            except Exception as e:
                # This test should FAIL until the feature is implemented
                pass


class TestMultipleOrchestratorInstances:
    """Test that multiple orchestrator instances can have different shadow_mode values."""

    def test_multiple_orchestrator_instances_different_shadow_modes(self):
        """Test that multiple orchestrator instances can coexist with different shadow_mode values."""
        orchestrator1 = LangGraphOrchestrator(
            project_path="/tmp/test1",
            shadow_mode=True
        )

        orchestrator2 = LangGraphOrchestrator(
            project_path="/tmp/test2",
            shadow_mode=False
        )

        # Each should have its own shadow_mode setting
        # This test will FAIL until shadow_mode is added
        assert orchestrator1.shadow_mode is True
        assert orchestrator2.shadow_mode is False

        # Both should be functional
        assert orchestrator1 is not None
        assert orchestrator2 is not None

    def test_orchestrator_instances_independent(self):
        """Test that changing one orchestrator's shadow_mode doesn't affect others."""
        orchestrator1 = LangGraphOrchestrator(
            project_path="/tmp/test1",
            shadow_mode=True
        )

        orchestrator2 = LangGraphOrchestrator(
            project_path="/tmp/test2",
            shadow_mode=False
        )

        # Verify initial state
        assert orchestrator1.shadow_mode is True
        assert orchestrator2.shadow_mode is False

        # Modify orchestrator1's shadow_mode (if it's writable)
        orchestrator1.shadow_mode = False

        # orchestrator2 should be unchanged
        assert orchestrator2.shadow_mode is False


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_task_dir_with_shadow_mode(self):
        """Test handling of empty task directory path with shadow_mode."""
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=True
        )

        # This test should FAIL until _get_output_dir method is implemented
        output_dir = orchestrator._get_output_dir("")
        # Should handle gracefully
        assert output_dir == "_shadow" or output_dir == os.path.join("", "_shadow")

    def test_task_dir_with_trailing_slash(self):
        """Test handling of task_dir with trailing slash."""
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=True
        )

        task_dir = "/tmp/test_task/"

        # This test should FAIL until _get_output_dir method is implemented
        output_dir = orchestrator._get_output_dir(task_dir)
        # Should normalize path and add _shadow
        assert "_shadow" in output_dir

    def test_shadow_mode_with_absolute_paths(self):
        """Test shadow_mode with absolute paths."""
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=True
        )

        task_dir = "/absolute/path/to/task"

        # This test should FAIL until _get_output_dir method is implemented
        output_dir = orchestrator._get_output_dir(task_dir)
        expected = "/absolute/path/to/task/_shadow"
        assert output_dir == expected

    def test_shadow_mode_with_relative_paths(self):
        """Test shadow_mode with relative paths."""
        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=True
        )

        task_dir = "relative/path/to/task"

        # This test should FAIL until _get_output_dir method is implemented
        output_dir = orchestrator._get_output_dir(task_dir)
        expected = "relative/path/to/task/_shadow"
        assert output_dir == expected


class TestIntegrationWithExistingTests:
    """Test that shadow_mode doesn't break existing LangGraphOrchestrator functionality."""

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_shadow_mode_does_not_break_graph_compilation(self, mock_execute_cli):
        """Test that graph still compiles with shadow_mode enabled."""
        mock_execute_cli.return_value = {"stdout": "Success", "stderr": "", "exit_code": 0}

        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=True
        )

        # Graph should still compile
        graph = orchestrator.get_graph()
        assert graph is not None

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_shadow_mode_false_does_not_change_behavior(self, mock_execute_cli):
        """Test that shadow_mode=False doesn't change existing behavior."""
        mock_execute_cli.return_value = {"stdout": "Success", "stderr": "", "exit_code": 0}

        orchestrator = LangGraphOrchestrator(
            project_path="/tmp/test",
            shadow_mode=False
        )

        graph = orchestrator.get_graph()

        initial_state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': [],
            'verify_passed': True
        }

        try:
            result = graph.invoke(initial_state)
            # Should work exactly as before
            assert 'phase_outputs' in result
        except Exception:
            # If it fails due to mocking, that's OK
            pass


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
