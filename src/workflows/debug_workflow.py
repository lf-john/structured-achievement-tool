"""
DebugWorkflow — LangGraph state machine for debugging tasks.

Defines states for REPRODUCE, DIAGNOSE, ROUTING, and outcome branches (Dev, Config, Maint, Report).
"""

from typing import Literal, Optional
from langgraph.graph import StateGraph, END

from src.workflows.base_workflow import BaseWorkflow, phase_node # Assuming phase_node will be used for these states
from src.workflows.state import StoryState
from src.llm.routing_engine import RoutingEngine


# Placeholder node functions for each state
def reproduce(state: StoryState) -> StoryState:
    print("Executing REPRODUCE phase...")
    return state

def diagnose(state: StoryState) -> StoryState:
    print("Executing DIAGNOSE phase...")
    return state

# Routing is a decision point, not a direct execution node, so it needs a decision function
def routing_decision(state: StoryState) -> Literal["dev", "config", "maint", "report"]:
    print("Executing ROUTING decision...")
    # Placeholder for actual routing logic
    # For now, let's just default to 'dev' for testing purposes or based on some state
    # In a real scenario, this would use the routing_engine or other state info.
    return "dev"

def dev_branch(state: StoryState) -> StoryState:
    print("Executing Dev branch...")
    return state

def config_branch(state: StoryState) -> StoryState:
    print("Executing Config branch...")
    return state

def maint_branch(state: StoryState) -> StoryState:
    print("Executing Maint branch...")
    return state

def report_branch(state: StoryState) -> StoryState:
    print("Executing Report branch...")
    return state


class DebugWorkflow(BaseWorkflow):
    """
    Implements the DebugWorkflow state machine with REPRODUCE, DIAGNOSE, and ROUTING stages,
    and outcome branches (Dev, Config, Maint, Report).
    """

    def __init__(self, routing_engine: Optional[RoutingEngine] = None):
        super().__init__(routing_engine)

    def build_graph(self) -> StateGraph[StoryState, str]:
        """
        Build and return the compiled LangGraph StateGraph for the DebugWorkflow.
        """
        workflow = StateGraph(StoryState)

        # Define nodes for the core stages
        workflow.add_node("reproduce", reproduce)
        workflow.add_node("diagnose", diagnose)
        workflow.add_node("ROUTING", routing_decision)

        # Define nodes for the routing outcome branches
        workflow.add_node("dev", dev_branch)
        workflow.add_node("config", config_branch)
        workflow.add_node("maint", maint_branch)
        workflow.add_node("report", report_branch)
        
        # Set entry point
        workflow.set_entry_point("reproduce")

        # Define edges
        workflow.add_edge("reproduce", "diagnose")
        workflow.add_edge("diagnose", "ROUTING")

        # The routing decision is a conditional edge from a node to multiple potential next nodes
        workflow.add_conditional_edges(
            "ROUTING",  # The source node for the conditional transition
            routing_decision,
            {
                "dev": "dev",
                "config": "config",
                "maint": "maint",
                "report": "report",
            },
        )

        # Each outcome branch leads to the END state for this workflow
        workflow.add_edge("dev", END)
        workflow.add_edge("config", END)
        workflow.add_edge("maint", END)
        workflow.add_edge("report", END)

        return workflow
