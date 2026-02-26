"""
DebugWorkflow — LangGraph state machine for debugging tasks.

Defines the core states: REPRODUCE, DIAGNOSE, ROUTING,
and outcome branches: dev, config, maint, report.
"""

import logging
from typing import Literal, Optional

from langgraph.graph import StateGraph, END

from src.workflows.base_workflow import BaseWorkflow, phase_node # Import phase_node for LLM-driven nodes
from src.workflows.state import StoryState
from src.llm.routing_engine import RoutingEngine

logger = logging.getLogger(__name__)

# This function simulates the reproduction of a failure for the DebugWorkflow.
def simulate_reproduction(failure_context: str) -> dict:
    """
    Simulates an attempt to reproduce a failure based on the provided context.
    This is a placeholder for actual reproduction logic.
    """
    if "Error" in failure_context or "Failure" in failure_context or "fault" in failure_context:
        return {"status": "reproduced", "details": f"Simulated reproduction of: {failure_context[:50]}..."}
    elif not failure_context.strip():
        return {"status": "not_applicable", "details": "No failure context provided for reproduction attempt."}
    else:
        return {"status": "not_reproduced", "details": f"Could not reproduce failure with context: {failure_context[:50]}..."}


def categorize_diagnosis(reproduction_details: str) -> dict:
    """
    Categorizes a diagnosed issue into one of four outcomes: development, config, maintenance, or review.

    Returns:
        dict with "category" and "reasoning" keys
    """
    details_lower = reproduction_details.lower()

    # Check for maintenance issues (system resource/infrastructure problems)
    if any(term in details_lower for term in ["disk", "space", "memory", "permissions", "service", "restart"]):
        return {
            "category": "maintenance",
            "reasoning": "System resource or infrastructure issue requiring maintenance"
        }

    # Check for configuration issues
    if any(term in details_lower for term in ["config", "parameter", "port", "invalid"]):
        return {
            "category": "config",
            "reasoning": "Configuration parameter or setting issue"
        }

    # Check for non-reproducible/informational issues
    if "not reproduced" in details_lower or "not_reproduced" in details_lower:
        return {
            "category": "review",
            "reasoning": "Non-reproducible issue - informational only"
        }

    # Default to development (code-level issues)
    return {
        "category": "development",
        "reasoning": "Code-level issue requiring development fix"
    }

# Placeholder node functions - these will contain actual logic later
def reproduce(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    logger.info("Entering REPRODUCE state.")
    failure_context = state.get("failure_context", "")
    reproduction_outcome = simulate_reproduction(failure_context)

    state["reproduction_status"] = reproduction_outcome["status"]
    state["reproduction_details"] = reproduction_outcome["details"]
    logger.info(f"Reproduction attempt status: {reproduction_outcome['status']}")
    logger.info(f"Reproduction attempt details: {reproduction_outcome['details']}")
    return state

def diagnose(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    logger.info("Entering DIAGNOSE state.")

    # Get reproduction details to use for diagnosis
    reproduction_details = state.get("reproduction_details", "")

    # Categorize the diagnosed issue
    diagnosis = categorize_diagnosis(reproduction_details)

    # Update state with diagnosis information
    state["diagnosis_category"] = diagnosis["category"]
    state["diagnosis_reasoning"] = diagnosis["reasoning"]

    logger.info(f"Diagnosis: {diagnosis['category']} - {diagnosis['reasoning']}")

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
        # Compile the workflow graph and store as app
        self.app = self.compile()

    def routing_decision(self, state: StoryState) -> Literal["dev", "config", "maint", "report"]:
        """
        Routes the debugging task to the appropriate specialized workflow
        based on the output of the DIAGNOSE phase.
        """
        # Use the diagnosis category computed by the diagnose node
        category = state.get("diagnosis_category", "development")
        category_map = {
            "development": "dev",
            "config": "config",
            "maintenance": "maint",
            "review": "report",
        }
        decision = category_map.get(category, "dev")
        logger.info(f"Routing decision: {decision} (from diagnosis: {category})")
        return decision

    def run(self, state: StoryState) -> StoryState:
        """
        Run the DebugWorkflow with the given initial state.

        Args:
            state: The initial StoryState

        Returns:
            The final StoryState after the workflow completes
        """
        return self.app.invoke(state)

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
