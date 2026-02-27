"""
Escalation Workflow — Route unresolvable failures to a human.

PREPARE → PACKAGE_DIAGNOSTICS → NOTIFY → PAUSE → LEARN

For stories that have exhausted automated retries or hit environmental issues.
SAT packages diagnostic information, notifies the human with a structured
escalation report, and waits for guidance.
"""

from functools import partial
from typing import Literal

from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState
from src.workflows.base_workflow import BaseWorkflow, phase_node
from src.workflows.human_nodes import prepare_node, package_diagnostics_node
from src.workflows.control_nodes import notify_node
from src.workflows.approval_workflow import (
    ApprovalConfig,
    approval_pause_node,
    pause_initial_decision,
    approval_follow_up_node,
    follow_up_decision,
    approval_escalation_node,
)
from src.notifications.notifier import Notifier


class EscalationWorkflow:
    """Escalation story workflow for human-assisted troubleshooting.

    PREPARE → PACKAGE_DIAGNOSTICS → NOTIFY → PAUSE → LEARN → END

    Uses the Approval Workflow's pause/follow-up/escalation pattern
    for the PAUSE phase. On response, routes to LEARN to capture
    the human's resolution for future reference.
    """

    def __init__(
        self,
        routing_engine=None,
        notifier: Notifier = None,
        config: ApprovalConfig = None,
    ):
        from src.llm.routing_engine import RoutingEngine
        self.routing_engine = routing_engine or RoutingEngine()
        self.notifier = notifier or Notifier()
        self.config = config or ApprovalConfig()

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine
        ntf = self.notifier
        cfg = self.config

        # Nodes
        builder.add_node("prepare", partial(prepare_node, story_type="escalation"))
        builder.add_node("package_diagnostics", package_diagnostics_node)
        builder.add_node("notify", partial(notify_node, notifier=ntf))
        builder.add_node("pause", partial(approval_pause_node, notifier=ntf, config=cfg))
        builder.add_node("follow_up", partial(approval_follow_up_node, notifier=ntf, config=cfg))
        builder.add_node("escalation", partial(approval_escalation_node, notifier=ntf, config=cfg))
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        # Entry
        builder.set_entry_point("prepare")

        # PREPARE → PACKAGE_DIAGNOSTICS → NOTIFY → PAUSE
        builder.add_edge("prepare", "package_diagnostics")
        builder.add_edge("package_diagnostics", "notify")
        builder.add_edge("notify", "pause")

        # PAUSE → responded/follow_up/escalate
        builder.add_conditional_edges("pause", pause_initial_decision, {
            "responded": "learn",
            "follow_up": "follow_up",
            "escalate": "escalation",
        })

        builder.add_conditional_edges("follow_up", follow_up_decision, {
            "responded": "learn",
            "escalate": "escalation",
        })

        # Escalation → learn (capture whatever guidance we got)
        builder.add_edge("escalation", "learn")

        builder.add_edge("learn", END)

        return builder

    def compile(self, checkpointer=None):
        return self.build_graph().compile(checkpointer=checkpointer)
