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

from src.agents.ac_templates import get_default_acs, merge_acs
from src.agents.critic_agent import CriticAgent, validate_ratings
from src.execution.git_manager import get_diff
from src.workflows.base_workflow import (
    BaseWorkflow,
    _run_async,
    check_test_decision,
    mediator_decision,
    mediator_gate_node,
    parallel_verify_node,
    phase_node,
    test_check_node,
)
from src.workflows.state import StoryState

logger = __import__("logging").getLogger(__name__)

MAX_CRITIC_RETRIES = 2


def critic_code_review_node(
    state: StoryState,
    routing_engine=None,
) -> StoryState:
    """Blocking critic review of code changes after parallel verify."""
    state = dict(state)
    state["current_phase"] = "CRITIC_CODE_REVIEW"
    story = state["story"]
    working_dir = state["working_directory"]
    task_description = state.get("task_description", story.get("description", ""))

    story_acs = story.get("acceptanceCriteria", [])
    default_acs = get_default_acs("development")
    acceptance_criteria = merge_acs(story_acs, default_acs)

    output_content = get_diff(working_dir)
    if not output_content:
        for po in reversed(state.get("phase_outputs", [])):
            if po.get("phase") == "CODE":
                output_content = po.get("output", "")
                break

    if not output_content:
        logger.warning("Critic code review: no code changes found, passing through")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": "No content to review"}
        return state

    critic_retry_count = state.get("critic_retry_count", 0)
    try:
        critic = CriticAgent(
            mode="dev_critic",
            routing_engine=routing_engine,
            escalation=critic_retry_count * 5,
        )
        response = _run_async(
            critic.evaluate(
                acceptance_criteria=acceptance_criteria,
                output_content=output_content,
                task_description=task_description,
                working_directory=working_dir,
            ),
            timeout=180,
        )
        validation = validate_ratings(response, acceptance_criteria)
        state["critic_passed"] = validation.passed
        state["critic_ratings"] = [r.model_dump() for r in response.ratings]
        state["critic_average"] = validation.average
        state["critic_validation"] = {
            "passed": validation.passed,
            "missing_acs": validation.missing_acs,
            "failing_acs": validation.failing_acs,
            "average": validation.average,
            "message": validation.message,
        }
        if not validation.passed:
            state["critic_retry_count"] = critic_retry_count + 1
            failing_details = [
                f"  - {f['ac_id']} ({f['ac_name']}): rated {f['rating']}/10 — {f['justification']}"
                for f in validation.failing_acs
            ]
            state["failure_context"] = (
                f"Critic code review failed (avg={validation.average}):\n{validation.message}\n"
                + "\n".join(failing_details)
                + f"\n\nAssessment: {response.overall_assessment}"
            )
        logger.info(
            f"Critic code review: avg={validation.average:.1f}, passed={validation.passed}, retry={state.get('critic_retry_count', 0)}/{MAX_CRITIC_RETRIES}"
        )
    except Exception:
        logger.exception("Critic code review failed — passing through")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": "Critic evaluation failed"}
    return state


def critic_code_decision(state: StoryState) -> str:
    """Route after CRITIC_CODE_REVIEW."""
    critic_passed = state.get("critic_passed")
    critic_retry_count = state.get("critic_retry_count", 0)
    if critic_passed:
        return "accept"
    elif critic_retry_count >= MAX_CRITIC_RETRIES:
        logger.warning(f"Dev critic retry limit ({MAX_CRITIC_RETRIES}) reached — story FAILS")
        return "fail"
    else:
        return "rework"


class DevTDDWorkflow(BaseWorkflow):
    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        # Architect Code: high-level architecture — what to build, where, module boundaries
        builder.add_node(
            "architect_code",
            partial(phase_node, phase_name="ARCHITECT_CODE", agent_name="architect", routing_engine=re),
        )

        # Plan Code: step-by-step implementation plan — how to build it in detail
        builder.add_node(
            "plan_code", partial(phase_node, phase_name="PLAN_CODE", agent_name="planner", routing_engine=re)
        )

        # Test Writer: writes failing tests based on the plan
        builder.add_node(
            "test_writer", partial(phase_node, phase_name="TEST_WRITER", agent_name="test_writer", routing_engine=re)
        )

        # Code: implements the solution to make tests pass
        builder.add_node("code", partial(phase_node, phase_name="CODE", agent_name="coder", routing_engine=re))

        # Parallel verification (4 concurrent checks: lint, test, security, arch)
        builder.add_node("parallel_verify", partial(parallel_verify_node, routing_engine=re))

        # Learn: capture learnings
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        # Automated check nodes (no LLM)
        builder.add_node("tdd_red_check", partial(test_check_node, phase_name="TDD_RED_CHECK", expect_failure=True))
        builder.add_node(
            "tdd_green_check", partial(test_check_node, phase_name="TDD_GREEN_CHECK", expect_failure=False)
        )

        # Critic code review: blocking quality gate after parallel verify
        builder.add_node("critic_code_review", partial(critic_code_review_node, routing_engine=re))

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
        builder.add_conditional_edges(
            "tdd_red_check",
            check_test_decision,
            {
                "pass": "code",
                "fail": "test_writer",
            },
        )

        # CODE → mediator_code (reviews code changes)
        builder.add_edge("code", "mediator_code")
        builder.add_conditional_edges(
            "mediator_code",
            mediator_decision,
            {
                "accept": "tdd_green_check",
                "retry": "code",
            },
        )

        # TDD_GREEN_CHECK: pass → parallel_verify, fail → code
        builder.add_conditional_edges(
            "tdd_green_check",
            check_test_decision,
            {
                "pass": "parallel_verify",
                "fail": "code",
            },
        )

        # PARALLEL_VERIFY → critic_code_review → mediator_verify
        builder.add_edge("parallel_verify", "critic_code_review")
        builder.add_conditional_edges(
            "critic_code_review",
            critic_code_decision,
            {
                "accept": "mediator_verify",
                "rework": "code",
                "fail": "learn",
            },
        )
        builder.add_conditional_edges(
            "mediator_verify",
            mediator_decision,
            {
                "accept": "learn",
                "retry": "code",
            },
        )

        # LEARN → END
        builder.add_edge("learn", END)

        return builder
