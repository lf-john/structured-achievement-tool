"""
IMPLEMENTATION PLAN for US-001: Wire PhaseRunner to Orchestrator Nodes

Components:
  - LangGraphOrchestrator: Modified to accept project_path and initialize PhaseRunner
    * __init__(project_path: str): Initialize with project_path and create PhaseRunner instance
    * self.runner: Instance of PhaseRunner stored on the orchestrator
    * _build_graph(): Pass runner to node functions via functools.partial

  - Node Functions (modified): All node functions must accept and use runner parameter
    * design_node(state, runner): Uses runner.execute_cli() for DESIGN phase
    * tdd_red_node(state, runner): Uses runner.execute_cli() for TDD_RED phase
    * code_node(state, runner): Uses runner.execute_cli() for CODE phase
    * tdd_green_node(state, runner): Uses runner.execute_cli() for TDD_GREEN phase
    * verify_node(state, runner): Uses runner.execute_cli() for VERIFY, sets verify_passed based on exit code
    * learn_node(state, runner): Uses runner.execute_cli() for LEARN phase

Test Cases:
  1. AC 1 (LangGraphOrchestrator accepts project_path and initializes PhaseRunner)
     -> test_orchestrator_accepts_project_path
     -> test_orchestrator_initializes_phase_runner
     -> test_phase_runner_stored_as_instance_variable

  2. AC 2 (Node functions use PhaseRunner to execute CLI tools)
     -> test_design_node_calls_runner_execute_cli
     -> test_tdd_red_node_calls_runner_execute_cli
     -> test_code_node_calls_runner_execute_cli
     -> test_tdd_green_node_calls_runner_execute_cli
     -> test_verify_node_calls_runner_execute_cli
     -> test_learn_node_calls_runner_execute_cli

  3. AC 3 (Phase outputs are captured from actual CLI execution)
     -> test_phase_outputs_contain_cli_stdout
     -> test_phase_outputs_accumulate_from_multiple_nodes

  4. AC 4 (verify_node sets verify_passed based on VERIFY CLI output)
     -> test_verify_node_sets_verify_passed_true_on_success
     -> test_verify_node_sets_verify_passed_false_on_failure

  5. AC 5 (Tests verify runner integration with mocks)
     -> test_runner_integration_with_mocks
     -> test_multiple_orchestrator_instances_have_separate_runners

Edge Cases:
  - Empty project path
  - CLI execution failure (non-zero exit code)
  - CLI execution with empty stdout/stderr
  - Multiple graph instances with different project paths
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import sys
from functools import partial

# Import the classes that need to be modified
from src.core.langgraph_orchestrator import (
    LangGraphOrchestrator,
    OrchestratorState,
    design_node,
    tdd_red_node,
    code_node,
    tdd_green_node,
    verify_node,
    learn_node,
)
from src.core.phase_runner import PhaseRunner


class TestOrchestratorAcceptsProjectPath:
    """Test acceptance criterion 1: LangGraphOrchestrator accepts project_path and initializes PhaseRunner."""

    def test_orchestrator_accepts_project_path(self):
        """Test that LangGraphOrchestrator can be instantiated with a project_path parameter."""
        # This should NOT raise TypeError
        orchestrator = LangGraphOrchestrator(project_path="/tmp/test_project")
        assert orchestrator is not None
        assert isinstance(orchestrator, LangGraphOrchestrator)

    def test_orchestrator_initializes_phase_runner(self):
        """Test that LangGraphOrchestrator initializes a PhaseRunner instance."""
        orchestrator = LangGraphOrchestrator(project_path="/tmp/test_project")

        # Should have a runner attribute that is a PhaseRunner instance
        assert hasattr(orchestrator, 'runner')
        assert orchestrator.runner is not None
        assert isinstance(orchestrator.runner, PhaseRunner)

    def test_phase_runner_stored_as_instance_variable(self):
        """Test that PhaseRunner is stored per-instance, not globally."""
        orchestrator1 = LangGraphOrchestrator(project_path="/tmp/test1")
        orchestrator2 = LangGraphOrchestrator(project_path="/tmp/test2")

        # Each orchestrator should have its own runner instance
        assert orchestrator1.runner is not orchestrator2.runner
        assert orchestrator1.runner.project_path == "/tmp/test1"
        assert orchestrator2.runner.project_path == "/tmp/test2"


class TestNodeFunctionsAcceptRunner:
    """Test that node functions accept a runner parameter."""

    def test_design_node_accepts_runner_parameter(self):
        """Test that design_node accepts a runner parameter."""
        mock_runner = Mock(spec=PhaseRunner)

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        # This should NOT raise TypeError
        result = design_node(state, runner=mock_runner)
        assert result is not None

    def test_tdd_red_node_accepts_runner_parameter(self):
        """Test that tdd_red_node accepts a runner parameter."""
        mock_runner = Mock(spec=PhaseRunner)

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = tdd_red_node(state, runner=mock_runner)
        assert result is not None

    def test_code_node_accepts_runner_parameter(self):
        """Test that code_node accepts a runner parameter."""
        mock_runner = Mock(spec=PhaseRunner)

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = code_node(state, runner=mock_runner)
        assert result is not None

    def test_tdd_green_node_accepts_runner_parameter(self):
        """Test that tdd_green_node accepts a runner parameter."""
        mock_runner = Mock(spec=PhaseRunner)

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = tdd_green_node(state, runner=mock_runner)
        assert result is not None

    def test_verify_node_accepts_runner_parameter(self):
        """Test that verify_node accepts a runner parameter."""
        mock_runner = Mock(spec=PhaseRunner)

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = verify_node(state, runner=mock_runner)
        assert result is not None

    def test_learn_node_accepts_runner_parameter(self):
        """Test that learn_node accepts a runner parameter."""
        mock_runner = Mock(spec=PhaseRunner)

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = learn_node(state, runner=mock_runner)
        assert result is not None


class TestRunnerIntegrationWithMocks:
    """Test acceptance criterion 2 & 5: Node functions use PhaseRunner.execute_cli() (verified with mocks)."""

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_design_node_calls_runner_execute_cli(self, mock_execute_cli):
        """Test that design_node calls runner.execute_cli()."""
        mock_execute_cli.return_value = {
            'stdout': 'Design completed',
            'stderr': '',
            'exit_code': 0
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = design_node(state, runner=mock_runner)

        # Verify execute_cli was called
        assert mock_execute_cli.called, "design_node did not call runner.execute_cli()"

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_tdd_red_node_calls_runner_execute_cli(self, mock_execute_cli):
        """Test that tdd_red_node calls runner.execute_cli()."""
        mock_execute_cli.return_value = {
            'stdout': 'Tests written',
            'stderr': '',
            'exit_code': 0
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = tdd_red_node(state, runner=mock_runner)

        assert mock_execute_cli.called, "tdd_red_node did not call runner.execute_cli()"

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_code_node_calls_runner_execute_cli(self, mock_execute_cli):
        """Test that code_node calls runner.execute_cli()."""
        mock_execute_cli.return_value = {
            'stdout': 'Code implemented',
            'stderr': '',
            'exit_code': 0
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = code_node(state, runner=mock_runner)

        assert mock_execute_cli.called, "code_node did not call runner.execute_cli()"

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_tdd_green_node_calls_runner_execute_cli(self, mock_execute_cli):
        """Test that tdd_green_node calls runner.execute_cli()."""
        mock_execute_cli.return_value = {
            'stdout': 'Tests passing',
            'stderr': '',
            'exit_code': 0
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = tdd_green_node(state, runner=mock_runner)

        assert mock_execute_cli.called, "tdd_green_node did not call runner.execute_cli()"

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_verify_node_calls_runner_execute_cli(self, mock_execute_cli):
        """Test that verify_node calls runner.execute_cli()."""
        mock_execute_cli.return_value = {
            'stdout': 'Verification passed',
            'stderr': '',
            'exit_code': 0
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = verify_node(state, runner=mock_runner)

        assert mock_execute_cli.called, "verify_node did not call runner.execute_cli()"

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_learn_node_calls_runner_execute_cli(self, mock_execute_cli):
        """Test that learn_node calls runner.execute_cli()."""
        mock_execute_cli.return_value = {
            'stdout': 'Learnings documented',
            'stderr': '',
            'exit_code': 0
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = learn_node(state, runner=mock_runner)

        assert mock_execute_cli.called, "learn_node did not call runner.execute_cli()"


class TestPhaseOutputsCapture:
    """Test acceptance criterion 3: Phase outputs are captured from actual CLI execution."""

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_phase_outputs_contain_cli_stdout(self, mock_execute_cli):
        """Test that phase_outputs contain the stdout from CLI execution."""
        expected_output = "DESIGN phase completed successfully"

        mock_execute_cli.return_value = {
            'stdout': expected_output,
            'stderr': '',
            'exit_code': 0
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = design_node(state, runner=mock_runner)

        assert 'phase_outputs' in result
        assert len(result['phase_outputs']) > 0
        # The output should contain the CLI stdout
        assert any(expected_output in output for output in result['phase_outputs'])

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_phase_outputs_accumulate_from_multiple_nodes(self, mock_execute_cli):
        """Test that phase_outputs accumulate when multiple nodes execute."""
        mock_execute_cli.return_value = {
            'stdout': 'Phase output',
            'stderr': '',
            'exit_code': 0
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': ['Previous output']
        }

        # Execute multiple nodes
        state = design_node(state, runner=mock_runner)
        state = tdd_red_node(state, runner=mock_runner)
        state = code_node(state, runner=mock_runner)

        # Should have accumulated outputs
        assert len(state['phase_outputs']) >= 3


class TestVerifyNodeSetsVerifyPassed:
    """Test acceptance criterion 4: verify_node sets verify_passed based on VERIFY CLI output."""

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_verify_node_sets_verify_passed_true_on_success(self, mock_execute_cli):
        """Test that verify_node sets verify_passed=True when CLI succeeds (exit_code 0)."""
        mock_execute_cli.return_value = {
            'stdout': 'All tests passed',
            'stderr': '',
            'exit_code': 0  # Success
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = verify_node(state, runner=mock_runner)

        # verify_passed should be True when exit_code is 0
        assert 'verify_passed' in result or 'verify_passed' in state
        verify_value = result.get('verify_passed', state.get('verify_passed'))
        assert verify_value is True, "verify_passed should be True when CLI exit_code is 0"

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_verify_node_sets_verify_passed_false_on_failure(self, mock_execute_cli):
        """Test that verify_node sets verify_passed=False when CLI fails (non-zero exit_code)."""
        mock_execute_cli.return_value = {
            'stdout': 'Tests failed',
            'stderr': 'AssertionError',
            'exit_code': 1  # Failure
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = verify_node(state, runner=mock_runner)

        # verify_passed should be False when exit_code is non-zero
        assert 'verify_passed' in result or 'verify_passed' in state
        verify_value = result.get('verify_passed', state.get('verify_passed'))
        assert verify_value is False, "verify_passed should be False when CLI exit_code is non-zero"


class TestMultipleOrchestratorInstances:
    """Test that multiple orchestrator instances work correctly with separate runners."""

    def test_multiple_orchestrator_instances_have_separate_runners(self):
        """Test that multiple orchestrator instances can coexist with separate PhaseRunners."""
        orchestrator1 = LangGraphOrchestrator(project_path="/tmp/test1")
        orchestrator2 = LangGraphOrchestrator(project_path="/tmp/test2")

        # Each should have its own runner
        assert orchestrator1.runner is not orchestrator2.runner
        assert orchestrator1.runner.project_path == "/tmp/test1"
        assert orchestrator2.runner.project_path == "/tmp/test2"

        # Both should be functional
        assert hasattr(orchestrator1, 'graph')
        assert hasattr(orchestrator2, 'graph')


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_cli_execution_failure_handling(self, mock_execute_cli):
        """Test that node functions handle CLI execution failures gracefully."""
        mock_execute_cli.return_value = {
            'stdout': '',
            'stderr': 'Command failed',
            'exit_code': 127  # Command not found
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        # Should not raise exception, should handle gracefully
        result = design_node(state, runner=mock_runner)
        assert result is not None

    @patch('src.core.phase_runner.PhaseRunner.execute_cli')
    def test_cli_execution_with_empty_output(self, mock_execute_cli):
        """Test handling of CLI execution with empty stdout/stderr."""
        mock_execute_cli.return_value = {
            'stdout': '',
            'stderr': '',
            'exit_code': 0
        }

        mock_runner = Mock(spec=PhaseRunner)
        mock_runner.execute_cli = mock_execute_cli

        state = {
            'current_story': 'US-001',
            'task': 'Test task',
            'phase_outputs': []
        }

        result = design_node(state, runner=mock_runner)
        assert result is not None


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
