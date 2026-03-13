"""
Maintenance TDD Workflow — For dependency updates, cleanup, credential rotation.

PLAN → TEST_WRITER → TDD_RED_CHECK → SNAPSHOT → EXECUTE → PROPAGATION_WAIT →
  TDD_GREEN_CHECK → VERIFY → CRITIC_REVIEW → LEARN → WRITE_OUTPUT

TDD pattern applied to maintenance tasks:
- Test Writer writes verification tests before maintenance changes
- TDD Red Check confirms tests fail (changes not yet applied)
- Snapshot captures state before EXECUTE for rollback
- Execute performs the maintenance work
- Propagation Wait allows changes to take effect
- TDD Green Check confirms tests pass (changes applied correctly)
- Verify runs final verification
- Critic Review evaluates against acceptance criteria

Loopbacks:
- TDD_RED_CHECK fail → TEST_WRITER (tests should fail but didn't)
- TDD_GREEN_CHECK fail → ROLLBACK → EXECUTE (tests should pass but didn't)
- VERIFY fail → EXECUTE (verification failed)
- CRITIC_REVIEW fail → EXECUTE (rework up to MAX_CRITIC_RETRIES)
"""

import logging
import time
from functools import partial

from langgraph.graph import END, StateGraph

from src.agents.ac_templates import get_default_acs, merge_acs
from src.agents.critic_agent import CriticAgent, validate_ratings
from src.execution.git_manager import get_diff
from src.execution.snapshot_manager import capture_snapshot, rollback_to_snapshot
from src.workflows.base_workflow import (
    BaseWorkflow,
    _run_async,
    check_test_decision,
    phase_node,
    test_check_node,
    verify_decision,
    write_output_node,
)
from src.workflows.state import PhaseOutput, PhaseStatus, StoryState

logger = logging.getLogger(__name__)

MAX_CRITIC_RETRIES = 2


def maint_critic_node(state: StoryState, routing_engine=None) -> StoryState:
    """Critic review of maintenance changes against acceptance criteria."""
    state = dict(state)
    state["current_phase"] = "CRITIC_REVIEW"
    story = state["story"]
    working_dir = state["working_directory"]

    story_acs = story.get("acceptanceCriteria", [])
    default_acs = get_default_acs("maintenance")
    acceptance_criteria = merge_acs(story_acs, default_acs)

    output_content = get_diff(working_dir)
    if not output_content:
        for po in reversed(state.get("phase_outputs", [])):
            if po.get("phase") == "EXECUTE" and po.get("output"):
                output_content = po["output"]
                break

    if not output_content:
        logger.warning("Maint critic: no changes found, passing through")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": "Skipped — no content"}
        phase_output = PhaseOutput(
            phase="CRITIC_REVIEW",
            status=PhaseStatus.SKIPPED,
            output="Skipped — no content.",
            exit_code=0,
            provider_used="none",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    task_description = state.get("task_description", story.get("description", ""))
    critic_retry_count = state.get("critic_retry_count", 0)
    critic = CriticAgent(mode="dev_critic", routing_engine=routing_engine, escalation=critic_retry_count * 5)

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
        logger.error(f"Maint critic failed: {e}")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": f"Critic error: {e}"}
        phase_output = PhaseOutput(
            phase="CRITIC_REVIEW",
            status=PhaseStatus.FAILED,
            output=f"Critic error: {e}",
            exit_code=1,
            provider_used="dev_critic",
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
        phase="CRITIC_REVIEW",
        status=status,
        output=f"Critic: {'PASSED' if validation.passed else 'FAILED'} avg={validation.average}",
        exit_code=0 if validation.passed else 1,
        provider_used="dev_critic",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    if not validation.passed:
        state["critic_retry_count"] = critic_retry_count + 1
        failing_details = [
            f"  - {f['ac_id']} ({f['ac_name']}): {f['rating']}/10 — {f['justification']}"
            for f in validation.failing_acs
        ]
        state["failure_context"] = (
            f"Critic failed (avg={validation.average}):\n{validation.message}\n"
            + "\n".join(failing_details)
            + f"\n\nAssessment: {response.overall_assessment}"
        )
        logger.info(
            f"Maint critic FAILED (avg={validation.average}, retry {state['critic_retry_count']}/{MAX_CRITIC_RETRIES})"
        )
    else:
        logger.info(f"Maint critic PASSED (avg={validation.average})")

    return state


def maint_critic_decision(state: StoryState) -> str:
    """Route after maint CRITIC: pass → learn, fail → execute, max → fail."""
    if state.get("critic_passed"):
        return "learn"
    if state.get("critic_retry_count", 0) >= MAX_CRITIC_RETRIES:
        logger.warning(f"Maint critic limit ({MAX_CRITIC_RETRIES}) reached — story FAILS")
        return "fail"
    return "execute"


def maint_propagation_wait_node(state: StoryState) -> StoryState:
    """Wait for maintenance changes to propagate before verification."""
    state = dict(state)
    story = state["story"]
    delay = story.get("propagation_wait_seconds", 0)
    if not delay:
        return state

    delay = min(delay, 172800)  # Cap at 48h
    logger.info(f"Maint propagation wait: {delay}s")

    slot_released = False
    if delay > 120:
        try:
            from src.execution.slot_manager import current_slot_id, current_slot_manager

            sm = current_slot_manager.get()
            sid = current_slot_id.get()
            if sm is not None and sid is not None:
                sm.release_slot(sid)
                slot_released = True
                logger.info(f"Released slot {sid} during {delay}s maint propagation wait")
        except Exception:
            pass

    time.sleep(delay)

    if slot_released:
        try:
            from src.execution.slot_manager import (
                current_slot_id,
                current_slot_manager,
                current_task_file,
            )

            sm = current_slot_manager.get()
            tf = current_task_file.get()
            if sm is not None:
                new_sid = sm.get_available_slot()
                if new_sid is not None:
                    sm.assign_task(new_sid, tf or "propagation_wait")
                    current_slot_id.set(new_sid)
        except Exception:
            pass

    phase_output = PhaseOutput(
        phase="PROPAGATION_WAIT",
        status=PhaseStatus.COMPLETE,
        output=f"Waited {delay}s",
        exit_code=0,
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
    return state


def maint_snapshot_node(state: StoryState) -> StoryState:
    """Capture pre-EXECUTE snapshot for rollback on failure."""
    state = dict(state)
    working_dir = state["working_directory"]
    snapshot_hash = capture_snapshot(working_dir)
    if snapshot_hash:
        state["snapshot_hash"] = snapshot_hash
    return state


def maint_rollback_node(state: StoryState) -> StoryState:
    """Rollback to pre-EXECUTE snapshot after GREEN_CHECK failure."""
    state = dict(state)
    snapshot_hash = state.get("snapshot_hash")
    working_dir = state["working_directory"]
    if snapshot_hash:
        success = rollback_to_snapshot(working_dir, snapshot_hash)
        if success:
            logger.info("Maint: Rolled back to pre-execute snapshot")
        else:
            logger.warning("Maint: Rollback failed")
    return state


class MaintenanceWorkflow(BaseWorkflow):
    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node("plan", partial(phase_node, phase_name="PLAN", agent_name="planner", routing_engine=re))
        builder.add_node(
            "test_writer", partial(phase_node, phase_name="TEST_WRITER", agent_name="test_writer", routing_engine=re)
        )
        builder.add_node("tdd_red_check", partial(test_check_node, phase_name="TDD_RED_CHECK", expect_failure=True))
        builder.add_node("snapshot", maint_snapshot_node)
        builder.add_node("execute", partial(phase_node, phase_name="EXECUTE", agent_name="executor", routing_engine=re))
        builder.add_node("propagation_wait", maint_propagation_wait_node)
        builder.add_node(
            "tdd_green_check", partial(test_check_node, phase_name="TDD_GREEN_CHECK", expect_failure=False)
        )
        builder.add_node("rollback", maint_rollback_node)
        builder.add_node("verify", partial(phase_node, phase_name="VERIFY", agent_name="validator", routing_engine=re))
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))
        builder.add_node("write_output", write_output_node)

        builder.set_entry_point("plan")

        builder.add_edge("plan", "test_writer")
        builder.add_edge("test_writer", "tdd_red_check")

        # TDD_RED_CHECK: pass → snapshot → execute, fail → test_writer, fail_final → learn
        builder.add_conditional_edges(
            "tdd_red_check",
            check_test_decision,
            {
                "pass": "snapshot",
                "fail": "test_writer",
                "fail_final": "learn",
            },
        )

        builder.add_edge("snapshot", "execute")
        builder.add_edge("execute", "propagation_wait")
        builder.add_edge("propagation_wait", "tdd_green_check")

        # TDD_GREEN_CHECK: pass → verify, fail → rollback → execute, fail_final → learn
        builder.add_conditional_edges(
            "tdd_green_check",
            check_test_decision,
            {
                "pass": "verify",
                "fail": "rollback",
                "fail_final": "learn",
            },
        )

        builder.add_edge("rollback", "execute")

        builder.add_conditional_edges(
            "verify",
            verify_decision,
            {
                "pass": "critic_review",
                "fail": "execute",
            },
        )

        # Critic review after verify passes
        builder.add_node("critic_review", partial(maint_critic_node, routing_engine=re))
        builder.add_conditional_edges(
            "critic_review",
            maint_critic_decision,
            {
                "learn": "learn",
                "execute": "execute",
                "fail": "learn",  # Still run learn, but story marked as failed
            },
        )

        builder.add_edge("learn", "write_output")
        builder.add_edge("write_output", END)

        return builder
