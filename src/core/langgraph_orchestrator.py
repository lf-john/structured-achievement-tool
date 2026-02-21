"""
LangGraph Orchestrator State Machine

This module defines a LangGraph StateGraph that models the core Development workflow:
DESIGN -> TDD_RED -> CODE -> TDD_GREEN -> VERIFY -> LEARN

The VERIFY node has a conditional edge back to CODE if verification fails,
or to LEARN if verification passes.
"""

from typing import TypedDict, List, Literal, Optional
from langgraph.graph import StateGraph, END


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


def design_node(state: OrchestratorState) -> OrchestratorState:
    """DESIGN phase node.

    Appends a message indicating the DESIGN phase was executed.
    """
    state = state.copy()
    message = f"DESIGN phase completed for story: {state.get('current_story', 'N/A')}"
    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def tdd_red_node(state: OrchestratorState) -> OrchestratorState:
    """TDD_RED phase node.

    Appends a message indicating the TDD_RED phase was executed.
    """
    state = state.copy()
    message = f"TDD_RED phase completed for task: {state.get('task', 'N/A')}"
    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def code_node(state: OrchestratorState) -> OrchestratorState:
    """CODE phase node.

    Appends a message indicating the CODE phase was executed.
    """
    state = state.copy()
    message = f"CODE phase completed for task: {state.get('task', 'N/A')}"
    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def tdd_green_node(state: OrchestratorState) -> OrchestratorState:
    """TDD_GREEN phase node.

    Appends a message indicating the TDD_GREEN phase was executed.
    """
    state = state.copy()
    message = f"TDD_GREEN phase completed - making tests pass"
    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def verify_node(state: OrchestratorState) -> OrchestratorState:
    """VERIFY phase node.

    Appends a message indicating the VERIFY phase was executed.
    The verify_decision function will determine the next node based on verify_passed.
    """
    state = state.copy()
    passed = state.get('verify_passed', True)
    status = "PASSED" if passed else "FAILED"
    message = f"VERIFY phase {status}"
    state['phase_outputs'] = state.get('phase_outputs', []) + [message]
    return state


def learn_node(state: OrchestratorState) -> OrchestratorState:
    """LEARN phase node.

    Appends a message indicating the LEARN phase was executed.
    """
    state = state.copy()
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
    """

    def __init__(self):
        """Initialize the orchestrator and build the state graph."""
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build and configure the StateGraph with nodes and edges.

        Returns:
            Compiled StateGraph ready for execution
        """
        # Create the state graph with our state type
        builder = StateGraph(OrchestratorState)

        # Add all phase nodes
        builder.add_node('design', design_node)
        builder.add_node('tdd_red', tdd_red_node)
        builder.add_node('code', code_node)
        builder.add_node('tdd_green', tdd_green_node)
        builder.add_node('verify', verify_node)
        builder.add_node('learn', learn_node)

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
