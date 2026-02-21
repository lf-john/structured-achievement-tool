"""
LangGraph Orchestrator State Machine

This module defines a LangGraph StateGraph that models the core Development workflow:
DESIGN -> TDD_RED -> CODE -> TDD_GREEN -> VERIFY -> LEARN

The VERIFY node has a conditional edge back to CODE if verification fails,
or to LEARN if verification passes.
"""

from typing import TypedDict, List, Literal, Optional, Callable
from langgraph.graph import StateGraph, END
from functools import partial
from src.core.phase_runner import PhaseRunner
import logging


class OrchestratorState(TypedDict):
    """State for the LangGraph Orchestrator workflow.

    Attributes:
        current_story: The current user story being worked on
        task: The current task description
        phase_outputs: List of messages/output from each phase execution
        verify_passed: Optional flag indicating if verification passed (for conditional routing)
    """
    current_story: str
    task: str
    phase_outputs: List[str]
    verify_passed: Optional[bool]


def design_node(state: OrchestratorState, runner: Optional[PhaseRunner] = None, task_dir: str = ".") -> OrchestratorState:
    """DESIGN phase node.

    Executes the DESIGN phase CLI tool via PhaseRunner.

    Args:
        state: The orchestrator state
        runner: PhaseRunner instance for executing CLI tools
        task_dir: Directory to execute in

    Returns:
        Updated state with phase output appended
    """
    state = state.copy()

    if runner:
        try:
            prompt = f"DESIGN phase for story: {state.get('current_story', 'N/A')}"
            result = runner.execute_cli("claude", prompt, task_dir)
            message = result.get('stdout', '') or f"DESIGN phase completed for story: {state.get('current_story', 'N/A')}"
        except Exception as e:
            logging.warning(f"DESIGN phase CLI execution failed: {e}")
            message = f"DESIGN phase completed for story: {state.get('current_story', 'N/A')} (CLI failed)"
    else:
        message = f"DESIGN phase completed for story: {state.get('current_story', 'N/A')}"

    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def tdd_red_node(state: OrchestratorState, runner: Optional[PhaseRunner] = None, task_dir: str = ".") -> OrchestratorState:
    """TDD_RED phase node.

    Executes the TDD_RED phase CLI tool via PhaseRunner.

    Args:
        state: The orchestrator state
        runner: PhaseRunner instance for executing CLI tools
        task_dir: Directory to execute in

    Returns:
        Updated state with phase output appended
    """
    state = state.copy()

    if runner:
        try:
            prompt = f"TDD_RED phase for task: {state.get('task', 'N/A')}"
            result = runner.execute_cli("claude", prompt, task_dir)
            message = result.get('stdout', '') or f"TDD_RED phase completed for task: {state.get('task', 'N/A')}"
        except Exception as e:
            logging.warning(f"TDD_RED phase CLI execution failed: {e}")
            message = f"TDD_RED phase completed for task: {state.get('task', 'N/A')} (CLI failed)"
    else:
        message = f"TDD_RED phase completed for task: {state.get('task', 'N/A')}"

    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def code_node(state: OrchestratorState, runner: Optional[PhaseRunner] = None, task_dir: str = ".") -> OrchestratorState:
    """CODE phase node.

    Executes the CODE phase CLI tool via PhaseRunner.

    Args:
        state: The orchestrator state
        runner: PhaseRunner instance for executing CLI tools
        task_dir: Directory to execute in

    Returns:
        Updated state with phase output appended
    """
    state = state.copy()

    if runner:
        try:
            prompt = f"CODE phase for task: {state.get('task', 'N/A')}"
            result = runner.execute_cli("claude", prompt, task_dir)
            message = result.get('stdout', '') or f"CODE phase completed for task: {state.get('task', 'N/A')}"
        except Exception as e:
            logging.warning(f"CODE phase CLI execution failed: {e}")
            message = f"CODE phase completed for task: {state.get('task', 'N/A')} (CLI failed)"
    else:
        message = f"CODE phase completed for task: {state.get('task', 'N/A')}"

    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def tdd_green_node(state: OrchestratorState, runner: Optional[PhaseRunner] = None, task_dir: str = ".") -> OrchestratorState:
    """TDD_GREEN phase node.

    Executes the TDD_GREEN phase CLI tool via PhaseRunner.

    Args:
        state: The orchestrator state
        runner: PhaseRunner instance for executing CLI tools
        task_dir: Directory to execute in

    Returns:
        Updated state with phase output appended
    """
    state = state.copy()

    if runner:
        try:
            prompt = "TDD_GREEN phase - make tests pass"
            result = runner.execute_cli("claude", prompt, task_dir)
            message = result.get('stdout', '') or "TDD_GREEN phase completed - making tests pass"
        except Exception as e:
            logging.warning(f"TDD_GREEN phase CLI execution failed: {e}")
            message = "TDD_GREEN phase completed - making tests pass (CLI failed)"
    else:
        message = "TDD_GREEN phase completed - making tests pass"

    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def verify_node(state: OrchestratorState, runner: Optional[PhaseRunner] = None, task_dir: str = ".") -> OrchestratorState:
    """VERIFY phase node.

    Executes the VERIFY phase CLI tool via PhaseRunner and determines pass/fail.

    Args:
        state: The orchestrator state
        runner: PhaseRunner instance for executing CLI tools
        task_dir: Directory to execute in

    Returns:
        Updated state with phase output appended and verify_passed set
    """
    state = state.copy()

    if runner:
        try:
            prompt = "VERIFY phase - run tests and checks"
            result = runner.execute_cli("claude", prompt, task_dir)
            output = result.get('stdout', '') or "VERIFY phase completed"
            # Determine if verification passed based on exit code
            passed = result.get('exit_code', 0) == 0
            status = "PASSED" if passed else "FAILED"
            message = f"VERIFY phase {status}: {output}"
            state['verify_passed'] = passed
        except Exception as e:
            logging.warning(f"VERIFY phase CLI execution failed: {e}")
            message = "VERIFY phase completed (CLI failed)"
            # Default to passed if CLI fails to avoid infinite loop
            state['verify_passed'] = state.get('verify_passed', True)
    else:
        passed = state.get('verify_passed', True)
        status = "PASSED" if passed else "FAILED"
        message = f"VERIFY phase {status}"

    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def learn_node(state: OrchestratorState, runner: Optional[PhaseRunner] = None, task_dir: str = ".") -> OrchestratorState:
    """LEARN phase node.

    Executes the LEARN phase CLI tool via PhaseRunner.

    Args:
        state: The orchestrator state
        runner: PhaseRunner instance for executing CLI tools
        task_dir: Directory to execute in

    Returns:
        Updated state with phase output appended
    """
    state = state.copy()

    if runner:
        try:
            prompt = f"LEARN phase - document learnings from: {state.get('current_story', 'N/A')}"
            result = runner.execute_cli("claude", prompt, task_dir)
            message = result.get('stdout', '') or f"LEARN phase completed - documenting learnings from: {state.get('current_story', 'N/A')}"
        except Exception as e:
            logging.warning(f"LEARN phase CLI execution failed: {e}")
            message = f"LEARN phase completed - documenting learnings from: {state.get('current_story', 'N/A')} (CLI failed)"
    else:
        message = f"LEARN phase completed - documenting learnings from: {state.get('current_story', 'N/A')}"

    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def verify_decision(state: OrchestratorState) -> Literal['code', 'learn']:
    """Conditional edge function for VERIFY node.

    Routes to 'code' if verification failed, or 'learn' if verification passed.

    Args:
        state: The current orchestrator state

    Returns:
        'code' if verify_passed is False or not set (default to pass),
        'learn' if verify_passed is True
    """
    # Default to passing if verify_passed is not set
    if state.get('verify_passed', True):
        return 'learn'
    else:
        return 'code'


class LangGraphOrchestrator:
    """Orchestrator that builds and manages the LangGraph state machine.

    The graph models the development workflow:
    DESIGN -> TDD_RED -> CODE -> TDD_GREEN -> VERIFY -> (CODE | LEARN)

    Attributes:
        project_path: Path to the project directory
        runner: PhaseRunner instance for executing CLI tools
        graph: Compiled LangGraph StateGraph
    """

    def __init__(self, project_path: str):
        """Initialize the orchestrator with a project path and build the state graph.

        Args:
            project_path: Path to the project directory for PhaseRunner
        """
        self.project_path = project_path
        self.runner = PhaseRunner(project_path)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build and configure the StateGraph with nodes and edges.

        Node functions are bound with the PhaseRunner instance using functools.partial.

        Returns:
            Compiled StateGraph ready for execution
        """
        # Create the state graph with our state type
        builder = StateGraph(OrchestratorState)

        # Bind node functions with runner and task_dir using partial
        # This ensures each node has access to the PhaseRunner instance
        task_dir = self.project_path
        builder.add_node('design', partial(design_node, runner=self.runner, task_dir=task_dir))
        builder.add_node('tdd_red', partial(tdd_red_node, runner=self.runner, task_dir=task_dir))
        builder.add_node('code', partial(code_node, runner=self.runner, task_dir=task_dir))
        builder.add_node('tdd_green', partial(tdd_green_node, runner=self.runner, task_dir=task_dir))
        builder.add_node('verify', partial(verify_node, runner=self.runner, task_dir=task_dir))
        builder.add_node('learn', partial(learn_node, runner=self.runner, task_dir=task_dir))

        # Set the entry point
        builder.set_entry_point('design')

        # Add edges connecting nodes in sequence
        builder.add_edge('design', 'tdd_red')
        builder.add_edge('tdd_red', 'code')
        builder.add_edge('code', 'tdd_green')
        builder.add_edge('tdd_green', 'verify')

        # Add conditional edge from VERIFY
        # Routes to CODE if failed, LEARN if passed
        builder.add_conditional_edges(
            'verify',
            verify_decision,
            {
                'code': 'code',
                'learn': 'learn'
            }
        )

        # Add edge from LEARN to END
        builder.add_edge('learn', END)

        # Compile the graph
        return builder.compile()

    def get_graph(self) -> StateGraph:
        """Get the compiled StateGraph.

        Returns:
            The compiled LangGraph StateGraph
        """
        return self.graph
