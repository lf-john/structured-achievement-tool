"""
DebugWorkflow — LangGraph state machine for debugging tasks.

Defines the core states: REPRODUCE, DIAGNOSE, ROUTING,
and outcome branches: Dev, Config, Maint, Report.
"""

import logging
from typing import Literal, Optional

from langgraph.graph import StateGraph, END

from src.workflows.base_workflow import BaseWorkflow, phase_node # Import phase_node for LLM-driven nodes
from src.workflows.state import StoryState
from src.llm.routing_engine import RoutingEngine

logger = logging.getLogger(__name__)

# Placeholder node functions - these will contain actual logic later
def reproduce(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    logger.info("Entering REPRODUCE state.")
    # Placeholder for actual reproduction logic
    return state

def diagnose(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    logger.info("Entering DIAGNOSE state.")
    # Placeholder for actual diagnosis logic
    return state

def routing(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    logger.info("Entering ROUTING state.")
    # Placeholder for actual routing logic, the decision will be made by routing_decision
    return state

def dev_workflow(state: StoryState) -> StoryState:
    logger.info("Entering DEV_WORKFLOW state.")
    # Placeholder for kicking off a Dev TDD workflow
    return state

def config_workflow(state: StoryState) -> StoryState:
    logger.info("Entering CONFIG_WORKFLOW state.")
    # Placeholder for kicking off a Config TDD workflow
    return state

def maint_workflow(state: StoryState) -> StoryState:
    logger.info("Entering MAINT_WORKFLOW state.")
    # Placeholder for kicking off a Maintenance workflow
    return state

def report_workflow(state: StoryState) -> StoryState:
    logger.info("Entering REPORT_WORKFLOW state.")
    # Placeholder for generating a report
    return state

class DebugWorkflow(BaseWorkflow):
    """
    Implements the Debugging Workflow state machine.
    """
    def __init__(self, routing_engine: Optional[RoutingEngine] = None):
        super().__init__(routing_engine)

    def routing_decision(self, state: StoryState) -> Literal["dev", "config", "maint", "report"]:
        """
        Routes the debugging task to the appropriate specialized workflow
        based on the output of the DIAGNOSE phase.
        """
        # In a real scenario, this would use the routing_engine to decide
        # For now, it's a placeholder. The test implies the routing_engine will be mocked.
        # We need to ensure the routing_engine has a method for this.
        # Let's assume the routing_engine has a method called route_debug_issue that returns the decision.
        # The test will mock this.
        decision = self.routing_engine.route_debug_issue(state)
        logger.info(f"Routing decision: {decision}")
        return decision

    def build_graph(self) -> StateGraph:
        """
        Builds and returns the LangGraph StateGraph for the DebugWorkflow.
        """
        workflow = StateGraph(StoryState)

        # Add nodes for the core stages
        workflow.add_node("reproduce", lambda state: reproduce(state, self.routing_engine))
        workflow.add_node("diagnose", lambda state: diagnose(state, self.routing_engine))
        workflow.add_node("routing", lambda state: routing(state, self.routing_engine))

        # Add nodes for the outcome branches
        workflow.add_node("dev", dev_workflow)
        workflow.add_node("config", config_workflow)
        workflow.add_node("maint", maint_workflow)
        workflow.add_node("report", report_workflow)

        # Define the entry point
        workflow.set_entry_point("reproduce")

        # Define transitions
        workflow.add_edge("reproduce", "diagnose")
        workflow.add_edge("diagnose", "routing")

        # Conditional transitions from ROUTING
        workflow.add_conditional_edges(
            "routing",
            self.routing_decision,
            {
                "dev": "dev",
                "config": "config",
                "maint": "maint",
                "report": "report",
            },
        )

        # End points for the outcome branches (for now)
        workflow.add_edge("dev", END)
        workflow.add_edge("config", END)
        workflow.add_edge("maint", END)
        workflow.add_edge("report", END)

        return workflow
