"""
Task Verification Workflow — Replaces the simple Review workflow.

GATHER_OUTPUTS → VERIFY_ACS → DECISION → REPORT

This workflow verifies that task outputs meet acceptance criteria using
the AC-based critic pattern (min 5 individual, avg 7.0).

After 2 critic failures, the task FAILS.
"""

import logging
from functools import partial

from langgraph.graph import END, StateGraph

from src.agents.ac_templates import get_default_acs, merge_acs
from src.agents.critic_agent import CriticAgent, validate_ratings
from src.workflows.base_workflow import (
    BaseWorkflow,
    _run_async,
    phase_node,
    write_output_node,
)
from src.workflows.state import PhaseOutput, PhaseStatus, StoryState

logger = logging.getLogger(__name__)

MAX_CRITIC_RETRIES = 2


def gather_outputs_node(state: StoryState) -> StoryState:
    """Gather all phase outputs into a single review document."""
    state = dict(state)
    state["current_phase"] = "GATHER_OUTPUTS"

    outputs = []
    for po in state.get("phase_outputs", []):
        if po.get("status") == "complete" and po.get("output"):
            outputs.append(f"## {po['phase']}\n{po['output'][:3000]}")

    gathered = "\n\n---\n\n".join(outputs) if outputs else "No phase outputs found."

    phase_output = PhaseOutput(
        phase="GATHER_OUTPUTS",
        status=PhaseStatus.COMPLETE,
        output=gathered,
        exit_code=0,
        provider_used="local",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
    state["design_output"] = gathered
    return state


def verify_acs_node(state: StoryState, routing_engine=None) -> StoryState:
    """Verify gathered outputs against acceptance criteria using CriticAgent."""
    state = dict(state)
    state["current_phase"] = "VERIFY_ACS"
    story = state["story"]
    working_dir = state["working_directory"]

    story_acs = story.get("acceptanceCriteria", [])
    default_acs = get_default_acs("review")
    acceptance_criteria = merge_acs(story_acs, default_acs)

    output_content = state.get("design_output", "")
    if not output_content:
        logger.warning("VERIFY_ACS: No gathered outputs, passing through")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": "No content to verify"}
        phase_output = PhaseOutput(
            phase="VERIFY_ACS",
            status=PhaseStatus.SKIPPED,
            output="Skipped — no content.",
            exit_code=0,
            provider_used="none",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    task_description = state.get("task_description", story.get("description", ""))
    critic_retry_count = state.get("critic_retry_count", 0)
    critic = CriticAgent(mode="content_critic", routing_engine=routing_engine, escalation=critic_retry_count * 5)

    try:
        response = _run_async(
            critic.evaluate(
                acceptance_criteria=acceptance_criteria,
                output_content=output_content,
                task_description=task_description,
                working_directory=working_dir,
            ),
            timeout=180,
        )
    except (ValueError, RuntimeError) as e:
        logger.error(f"VERIFY_ACS critic failed: {e}")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": f"Critic error: {e}"}
        phase_output = PhaseOutput(
            phase="VERIFY_ACS",
            status=PhaseStatus.FAILED,
            output=f"Critic error: {e}",
            exit_code=1,
            provider_used="content_critic",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

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

    status = PhaseStatus.COMPLETE if validation.passed else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="VERIFY_ACS",
        status=status,
        output=f"VERIFY_ACS: {'PASSED' if validation.passed else 'FAILED'} avg={validation.average}",
        exit_code=0 if validation.passed else 1,
        provider_used="content_critic",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    if not validation.passed:
        state["critic_retry_count"] = critic_retry_count + 1
        failing_details = [
            f"  - {f['ac_id']} ({f['ac_name']}): {f['rating']}/10 — {f['justification']}"
            for f in validation.failing_acs
        ]
        state["failure_context"] = (
            f"Task verification failed (avg={validation.average}):\n{validation.message}\n" + "\n".join(failing_details)
        )
        logger.info(
            f"VERIFY_ACS FAILED (avg={validation.average}, retry {state['critic_retry_count']}/{MAX_CRITIC_RETRIES})"
        )
    else:
        logger.info(f"VERIFY_ACS PASSED (avg={validation.average})")

    return state


def verification_decision(state: StoryState) -> str:
    """Route after VERIFY_ACS: pass → report, fail → gather (rework), max → fail."""
    if state.get("critic_passed"):
        return "report"
    if state.get("critic_retry_count", 0) >= MAX_CRITIC_RETRIES:
        logger.warning(f"Task verification limit ({MAX_CRITIC_RETRIES}) reached — task FAILS")
        return "fail"
    return "gather"


class TaskVerificationWorkflow(BaseWorkflow):
    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node("gather_outputs", gather_outputs_node)
        builder.add_node("verify_acs", partial(verify_acs_node, routing_engine=re))
        builder.add_node("report", partial(phase_node, phase_name="REPORT", agent_name="reporter", routing_engine=re))
        builder.add_node("write_output", write_output_node)

        builder.set_entry_point("gather_outputs")
        builder.add_edge("gather_outputs", "verify_acs")

        builder.add_conditional_edges(
            "verify_acs",
            verification_decision,
            {
                "report": "report",
                "gather": "gather_outputs",
                "fail": "report",
            },
        )

        builder.add_edge("report", "write_output")
        builder.add_edge("write_output", END)

        return builder
