"""
Config TDD Workflow — For system setup and configuration tasks.

PLAN → EXECUTE → VERIFY_SCRIPT → LEARN

Loopback: VERIFY_SCRIPT fail → EXECUTE
"""

from functools import partial
from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState
from src.workflows.base_workflow import (
    BaseWorkflow,
    phase_node,
    verify_decision,
)


class ConfigTDDWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node("plan", partial(phase_node, phase_name="PLAN", agent_name="planner", routing_engine=re))
        builder.add_node("execute", partial(phase_node, phase_name="EXECUTE", agent_name="executor", routing_engine=re))
        builder.add_node("verify_script", partial(phase_node, phase_name="VERIFY_SCRIPT", agent_name="validator", routing_engine=re))
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        builder.set_entry_point("plan")

        builder.add_edge("plan", "execute")
        builder.add_edge("execute", "verify_script")

        builder.add_conditional_edges("verify_script", verify_decision, {
            "pass": "learn",
            "fail": "execute",
        })

        builder.add_edge("learn", END)

        return builder
