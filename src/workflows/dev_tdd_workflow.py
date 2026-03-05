"""
Development TDD Workflow — The core TDD pipeline with subagent decomposition.

ARCHITECT_CODE → PLAN_CODE → TEST_WRITER → TDD_RED_CHECK → CODE →
  MEDIATOR_CODE → TDD_GREEN_CHECK → PARALLEL_VERIFY → MEDIATOR_VERIFY → LEARN

Subagent roles:
- Architect Code: HIGH-LEVEL decisions — which files to create/modify, module
  boundaries, API contracts, data flow, dependency choices. Answers "what" and "where".
- Plan Code: STEP-BY-STEP implementation plan — ordered tasks, specific functions
  to write, exact test scenarios, edge cases to handle. Answers "how" in detail.

Mediator gates:
- MEDIATOR_CODE (after CODE): Reviews code changes for quality, scope creep,
  test/code file separation violations before running TDD Green Check.
- MEDIATOR_VERIFY (after PARALLEL_VERIFY): Reviews the overall verification
  results and decides if the story is truly complete before LEARN.

Loopbacks:
- TDD_RED_CHECK fail → TEST_WRITER (tests should fail but didn't)
- MEDIATOR_CODE retry → CODE (mediator rejected code changes)
- TDD_GREEN_CHECK fail → CODE (tests should pass but didn't)
- PARALLEL_VERIFY fail → CODE (verification issues)
- MEDIATOR_VERIFY retry → CODE (mediator rejected after verification)
"""

from functools import partial

from langgraph.graph import END, StateGraph

from src.workflows.base_workflow import (
    BaseWorkflow,
    check_test_decision,
    mediator_decision,
    mediator_gate_node,
    parallel_verify_node,
    phase_node,
    test_check_node,
)
from src.workflows.state import StoryState


class DevTDDWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        # Architect Code: high-level architecture — what to build, where, module boundaries
        builder.add_node("architect_code", partial(phase_node, phase_name="ARCHITECT_CODE", agent_name="architect", routing_engine=re))

        # Plan Code: step-by-step implementation plan — how to build it in detail
        builder.add_node("plan_code", partial(phase_node, phase_name="PLAN_CODE", agent_name="planner", routing_engine=re))

        # Test Writer: writes failing tests based on the plan
        builder.add_node("test_writer", partial(phase_node, phase_name="TEST_WRITER", agent_name="test_writer", routing_engine=re))

        # Code: implements the solution to make tests pass
        builder.add_node("code", partial(phase_node, phase_name="CODE", agent_name="coder", routing_engine=re))

        # Parallel verification (4 concurrent checks: lint, test, security, arch)
        builder.add_node("parallel_verify", partial(parallel_verify_node, routing_engine=re))

        # Learn: capture learnings
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        # Automated check nodes (no LLM)
        builder.add_node("tdd_red_check", partial(test_check_node, phase_name="TDD_RED_CHECK", expect_failure=True))
        builder.add_node("tdd_green_check", partial(test_check_node, phase_name="TDD_GREEN_CHECK", expect_failure=False))

        # Two mediator gates: after CODE and after PARALLEL_VERIFY
        builder.add_node("mediator_code", partial(mediator_gate_node, routing_engine=re))
        builder.add_node("mediator_verify", partial(mediator_gate_node, routing_engine=re))

        # Entry point
        builder.set_entry_point("architect_code")

        # Sequential edges: architect_code → plan_code → test_writer
        builder.add_edge("architect_code", "plan_code")
        builder.add_edge("plan_code", "test_writer")
        builder.add_edge("test_writer", "tdd_red_check")

        # TDD_RED_CHECK: pass → code, fail → test_writer
        builder.add_conditional_edges("tdd_red_check", check_test_decision, {
            "pass": "code",
            "fail": "test_writer",
        })

        # CODE → mediator_code (reviews code changes)
        builder.add_edge("code", "mediator_code")
        builder.add_conditional_edges("mediator_code", mediator_decision, {
            "accept": "tdd_green_check",
            "retry": "code",
        })

        # TDD_GREEN_CHECK: pass → parallel_verify, fail → code
        builder.add_conditional_edges("tdd_green_check", check_test_decision, {
            "pass": "parallel_verify",
            "fail": "code",
        })

        # PARALLEL_VERIFY → mediator_verify (reviews verification results)
        builder.add_edge("parallel_verify", "mediator_verify")
        builder.add_conditional_edges("mediator_verify", mediator_decision, {
            "accept": "learn",
            "retry": "code",
        })

        # LEARN → END
        builder.add_edge("learn", END)

        return builder
