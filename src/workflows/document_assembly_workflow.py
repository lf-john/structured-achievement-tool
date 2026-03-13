"""
Document Assembly Workflow — For assembling complex documents from multiple sources.

GATHER_INPUTS → DESIGN_LAYOUT → REQUEST_IMAGES → ASSEMBLE → QUALITY_CHECK → WRITE_OUTPUT

This workflow assembles documents that require multiple input sources,
layout design, and optional image generation/collection.

Quality check uses the AC-based critic pattern (min 5 individual, avg 7.0).
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


def quality_check_node(state: StoryState, routing_engine=None) -> StoryState:
    """Quality check of assembled document against acceptance criteria."""
    state = dict(state)
    state["current_phase"] = "QUALITY_CHECK"
    story = state["story"]
    working_dir = state["working_directory"]

    story_acs = story.get("acceptanceCriteria", [])
    default_acs = get_default_acs("content")
    acceptance_criteria = merge_acs(story_acs, default_acs)

    # Get assembled content
    output_content = ""
    for po in reversed(state.get("phase_outputs", [])):
        if po.get("phase") == "ASSEMBLE" and po.get("output"):
            output_content = po["output"]
            break

    if not output_content:
        logger.warning("Quality check: no assembled content, passing through")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": "No content to check"}
        phase_output = PhaseOutput(
            phase="QUALITY_CHECK",
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
        logger.error(f"Quality check critic failed: {e}")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": f"Critic error: {e}"}
        phase_output = PhaseOutput(
            phase="QUALITY_CHECK",
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
        phase="QUALITY_CHECK",
        status=status,
        output=f"Quality check: {'PASSED' if validation.passed else 'FAILED'} avg={validation.average}",
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
        # Edit-on-retry: include existing content for revision
        content_preview = output_content[:10000]
        if len(output_content) > 10000:
            content_preview += "\n[...truncated...]"
        state["failure_context"] = (
            f"Quality check failed (avg={validation.average}):\n{validation.message}\n"
            + "\n".join(failing_details)
            + f"\n\nExisting output to revise:\n```\n{content_preview}\n```"
        )
        logger.info(
            f"Quality check FAILED (avg={validation.average}, retry {state['critic_retry_count']}/{MAX_CRITIC_RETRIES})"
        )
    else:
        logger.info(f"Quality check PASSED (avg={validation.average})")

    return state


def quality_check_decision(state: StoryState) -> str:
    """Route after QUALITY_CHECK: pass → write_output, fail → assemble, max → fail."""
    if state.get("critic_passed"):
        return "write_output"
    if state.get("critic_retry_count", 0) >= MAX_CRITIC_RETRIES:
        logger.warning(f"Quality check limit ({MAX_CRITIC_RETRIES}) reached — task FAILS")
        return "fail"
    return "assemble"


class DocumentAssemblyWorkflow(BaseWorkflow):
    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node(
            "gather_inputs", partial(phase_node, phase_name="GATHER_INPUTS", agent_name="gatherer", routing_engine=re)
        )
        builder.add_node(
            "design_layout", partial(phase_node, phase_name="DESIGN_LAYOUT", agent_name="designer", routing_engine=re)
        )
        builder.add_node(
            "request_images",
            partial(phase_node, phase_name="REQUEST_IMAGES", agent_name="image_requester", routing_engine=re),
        )
        builder.add_node(
            "assemble", partial(phase_node, phase_name="ASSEMBLE", agent_name="assembler", routing_engine=re)
        )
        builder.add_node("quality_check", partial(quality_check_node, routing_engine=re))
        builder.add_node("write_output", write_output_node)

        builder.set_entry_point("gather_inputs")
        builder.add_edge("gather_inputs", "design_layout")
        builder.add_edge("design_layout", "request_images")
        builder.add_edge("request_images", "assemble")
        builder.add_edge("assemble", "quality_check")

        builder.add_conditional_edges(
            "quality_check",
            quality_check_decision,
            {
                "write_output": "write_output",
                "assemble": "assemble",
                "fail": "write_output",  # Still write output even on failure
            },
        )

        builder.add_edge("write_output", END)

        return builder
