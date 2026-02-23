"""
Development TDD Workflow — The core TDD pipeline.

DESIGN → TDD_RED → TDD_RED_CHECK → CODE → TDD_GREEN_CHECK → VERIFY → LEARN

Loopbacks:
- TDD_RED_CHECK fail → TDD_RED (tests should fail but didn't)
- TDD_GREEN_CHECK fail → CODE (tests should pass but didn't)
- VERIFY fail → CODE (verification issues)

Optional: Mediator gate after CODE (before TDD_GREEN_CHECK).
"""

from functools import partial
from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState
from src.workflows.base_workflow import (
    BaseWorkflow,
    phase_node,
    test_check_node,
    mediator_gate_node,
    verify_decision,
    check_test_decision,
    mediator_decision,
)


class DevTDDWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        # LLM phase nodes
        builder.add_node("design", partial(phase_node, phase_name="DESIGN", agent_name="design", routing_engine=re))
        builder.add_node("tdd_red", partial(phase_node, phase_name="TDD_RED", agent_name="test_writer", routing_engine=re))
        builder.add_node("code", partial(phase_node, phase_name="CODE", agent_name="coder", routing_engine=re))
        builder.add_node("verify", partial(phase_node, phase_name="VERIFY", agent_name="verifier_arch", routing_engine=re))
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        # Automated check nodes (no LLM)
        builder.add_node("tdd_red_check", partial(test_check_node, phase_name="TDD_RED_CHECK", expect_failure=True))
        builder.add_node("tdd_green_check", partial(test_check_node, phase_name="TDD_GREEN_CHECK", expect_failure=False))

        # Optional mediator gate
        builder.add_node("mediator", partial(mediator_gate_node, routing_engine=re))

        # Entry point
        builder.set_entry_point("design")

        # Sequential edges
        builder.add_edge("design", "tdd_red")
        builder.add_edge("tdd_red", "tdd_red_check")

        # TDD_RED_CHECK: pass → code, fail → tdd_red
        builder.add_conditional_edges("tdd_red_check", check_test_decision, {
            "pass": "code",
            "fail": "tdd_red",
        })

        # CODE → mediator (mediator decides to continue or retry)
        builder.add_edge("code", "mediator")
        builder.add_conditional_edges("mediator", mediator_decision, {
            "accept": "tdd_green_check",
            "retry": "code",
        })

        # TDD_GREEN_CHECK: pass → verify, fail → code
        builder.add_conditional_edges("tdd_green_check", check_test_decision, {
            "pass": "verify",
            "fail": "code",
        })

        # VERIFY: pass → learn, fail → code
        builder.add_conditional_edges("verify", verify_decision, {
            "pass": "learn",
            "fail": "code",
        })

        # LEARN → END
        builder.add_edge("learn", END)

        return builder
