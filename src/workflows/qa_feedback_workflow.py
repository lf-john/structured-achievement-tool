"""
QA Feedback Workflow — Collect and process QA tester feedback.

PREPARE → NOTIFY → PAUSE → PARSE → ROUTE

Routes based on parsed feedback:
- pass → LEARN (QA approved)
- fail → END with feedback (creates follow-up debug stories)
- partial → END with feedback (creates follow-up stories for remaining items)
"""

from functools import partial
from typing import Literal

from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState
from src.workflows.base_workflow import BaseWorkflow, phase_node
from src.workflows.human_nodes import prepare_node, parse_feedback_node
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


def qa_route_decision(state: StoryState) -> Literal["pass", "fail"]:
    """Route based on QA feedback verdict."""
    parsed = state.get("qa_feedback_parsed", {})
    verdict = parsed.get("verdict", "partial")
    if verdict == "pass":
        return "pass"
    return "fail"  # Both "fail" and "partial" need follow-up


class QAFeedbackWorkflow:
    """QA feedback collection workflow.

    PREPARE → NOTIFY → PAUSE → PARSE → ROUTE
    - pass → LEARN → END
    - fail → END (feedback stored for follow-up story creation)
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

        builder.add_node("prepare", partial(prepare_node, story_type="qa_feedback"))
        builder.add_node("notify", partial(notify_node, notifier=ntf))
        builder.add_node("pause", partial(approval_pause_node, notifier=ntf, config=cfg))
        builder.add_node("follow_up", partial(approval_follow_up_node, notifier=ntf, config=cfg))
        builder.add_node("escalation", partial(approval_escalation_node, notifier=ntf, config=cfg))
        builder.add_node("parse", parse_feedback_node)
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        builder.set_entry_point("prepare")

        builder.add_edge("prepare", "notify")
        builder.add_edge("notify", "pause")

        builder.add_conditional_edges("pause", pause_initial_decision, {
            "responded": "parse",
            "follow_up": "follow_up",
            "escalate": "escalation",
        })

        builder.add_conditional_edges("follow_up", follow_up_decision, {
            "responded": "parse",
            "escalate": "escalation",
        })

        builder.add_edge("escalation", "parse")

        # PARSE → ROUTE
        builder.add_conditional_edges("parse", qa_route_decision, {
            "pass": "learn",
            "fail": END,  # Feedback stored; orchestrator creates follow-up stories
        })

        builder.add_edge("learn", END)

        return builder

    def compile(self, checkpointer=None):
        return self.build_graph().compile(checkpointer=checkpointer)
