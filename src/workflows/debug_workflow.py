"""
Debug Workflow — For bug investigation and fixing.

DIAGNOSE → REPRODUCE → FIX → VERIFY → LEARN

From the plan: REPRODUCE → DIAGNOSE → ROUTING → [Dev|Config|Maint|Report]
Simplified here to the core debug loop. Routing to other workflows
is handled at the story executor level.

Loopback: VERIFY fail → FIX
"""

from functools import partial
from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState
from src.workflows.base_workflow import (
    BaseWorkflow,
    phase_node,
    verify_decision,
)


class DebugWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node("diagnose", partial(phase_node, phase_name="DIAGNOSE", agent_name="diagnoser", routing_engine=re))
        builder.add_node("reproduce", partial(phase_node, phase_name="REPRODUCE", agent_name="reproducer", routing_engine=re))
        builder.add_node("fix", partial(phase_node, phase_name="FIX", agent_name="coder", routing_engine=re))
        builder.add_node("verify", partial(phase_node, phase_name="VERIFY", agent_name="validator", routing_engine=re))
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        builder.set_entry_point("diagnose")

        builder.add_edge("diagnose", "reproduce")
        builder.add_edge("reproduce", "fix")
        builder.add_edge("fix", "verify")

        builder.add_conditional_edges("verify", verify_decision, {
            "pass": "learn",
            "fail": "fix",
        })

        builder.add_edge("learn", END)

        return builder
