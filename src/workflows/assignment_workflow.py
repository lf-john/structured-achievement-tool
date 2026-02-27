"""
Assignment Workflow — Human task assignment with validation.

PREPARE → NOTIFY → PAUSE → VALIDATE → INTEGRATE → LEARN

For tasks that require human action (e.g., DNS changes, credential rotation,
manual testing). SAT prepares a clear brief, notifies the human, waits for
completion, validates the result, integrates it, and captures learnings.

Loopbacks:
- VALIDATE fail → PAUSE (ask human to retry/complete remaining items)
"""

from functools import partial
from typing import Literal

from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState
from src.workflows.base_workflow import BaseWorkflow, phase_node, verify_decision
from src.workflows.human_nodes import (
    prepare_node,
    validate_node,
    integrate_node,
)
from src.workflows.control_nodes import notify_node, pause_node, pause_decision
from src.workflows.approval_workflow import (
    ApprovalConfig,
    approval_pause_node,
    pause_initial_decision,
    approval_follow_up_node,
    follow_up_decision,
    approval_escalation_node,
)
from src.notifications.notifier import Notifier


def validate_decision(state: StoryState) -> Literal["pass", "fail"]:
    """Route after VALIDATE: pass → integrate, fail → pause (retry)."""
    if state.get("verify_passed", False):
        return "pass"
    return "fail"


class AssignmentWorkflow:
    """Assignment story workflow with human task delegation.

    PREPARE → NOTIFY → PAUSE → VALIDATE → INTEGRATE → LEARN

    Uses the Approval Workflow's pause/follow-up/escalation pattern
    for the PAUSE phase. Timing is configurable via ApprovalConfig.
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
        builder.add_node("prepare", partial(prepare_node, story_type="assignment"))
        builder.add_node("notify", partial(notify_node, notifier=ntf))
        builder.add_node("pause", partial(approval_pause_node, notifier=ntf, config=cfg))
        builder.add_node("follow_up", partial(approval_follow_up_node, notifier=ntf, config=cfg))
        builder.add_node("escalation", partial(approval_escalation_node, notifier=ntf, config=cfg))
        builder.add_node("validate", validate_node)
        builder.add_node("integrate", integrate_node)
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        # Entry
        builder.set_entry_point("prepare")

        # PREPARE → NOTIFY → PAUSE
        builder.add_edge("prepare", "notify")
        builder.add_edge("notify", "pause")

        # PAUSE → responded/follow_up/escalate
        builder.add_conditional_edges("pause", pause_initial_decision, {
            "responded": "validate",
            "follow_up": "follow_up",
            "escalate": "escalation",
        })

        builder.add_conditional_edges("follow_up", follow_up_decision, {
            "responded": "validate",
            "escalate": "escalation",
        })

        # Escalation → validate (with whatever response we have)
        builder.add_edge("escalation", "validate")

        # VALIDATE → pass: integrate, fail: pause (retry)
        builder.add_conditional_edges("validate", validate_decision, {
            "pass": "integrate",
            "fail": "pause",
        })

        # INTEGRATE → LEARN → END
        builder.add_edge("integrate", "learn")
        builder.add_edge("learn", END)

        return builder

    def compile(self, checkpointer=None):
        return self.build_graph().compile(checkpointer=checkpointer)
