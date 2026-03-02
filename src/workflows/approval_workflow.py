"""
Approval Workflow — Standalone workflow for human approval gates.

Two paths:
- Normal: PAUSE → FOLLOW_UP → decision (approved/rejected/escalate)
- Emergency: PAUSE → decision (approved/rejected/timeout → auto-approve)

Key design principle: Timing is NOT baked into this workflow. Timeouts and
intervals are configured externally via ApprovalConfig, allowing the caller
to set appropriate timing per context.

The workflow uses the NOTIFY and PAUSE primitives from control_nodes.py but
orchestrates them into a complete approval lifecycle with follow-up and
escalation as first-class workflow steps.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState, PhaseOutput, PhaseStatus
from src.notifications.notifier import Notifier
from src.core.checkpoint_manager import (
    read_checkpoint, write_checkpoint, STATUS_WAITING_FOR_HUMAN, STATUS_IN_PROGRESS,
)
from src.workflows.control_nodes import (
    _build_signal_content,
    _read_signal_file,
    _extract_human_response,
    _default_write_signal,
)

logger = logging.getLogger(__name__)


@dataclass
class ApprovalConfig:
    """External configuration for approval timing and behavior.

    Timing is NOT baked into the workflow — the caller provides these
    values based on the approval context (normal vs emergency, story
    priority, time of day, etc.).
    """
    poll_interval: int = 30          # How often to check for response (seconds)
    follow_up_after: int = 3600      # When to send follow-up (seconds)
    escalation_after: int = 7200     # When to escalate (seconds)
    auto_timeout: int = 14400        # When to auto-resolve (seconds, 0 = never)
    emergency: bool = False          # Use emergency path
    auto_approve_on_timeout: bool = False  # Emergency: auto-approve on timeout
    signal_dir: str = "~/GoogleDrive/DriveSyncFiles/sat-tasks"
    escalation_contacts: list = field(default_factory=list)  # Additional contacts for escalation


# --- Node Functions ---

def approval_pause_node(
    state: StoryState,
    notifier: Notifier,
    config: ApprovalConfig,
    _sleep_fn=None,
    _write_fn=None,
    _read_fn=None,
) -> StoryState:
    """Initial pause: create signal file and wait for response.

    Waits up to config.follow_up_after before returning with status.
    Does NOT loop indefinitely — returns control to the graph for
    follow-up or escalation decisions.
    """
    state = dict(state)
    sleep_fn = _sleep_fn or time.sleep
    write_fn = _write_fn or _default_write_signal
    read_fn = _read_fn or _read_signal_file

    story = state.get("story", {})
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")

    # Expand signal dir and create signal file
    expanded_dir = os.path.expanduser(config.signal_dir)
    approvals_dir = os.path.join(expanded_dir, "approvals")
    signal_path = os.path.join(approvals_dir, f"{story_id}_approval.md")
    state["approval_signal_path"] = signal_path

    signal_content = _build_signal_content(state)
    write_fn(signal_path, signal_content)
    logger.info(f"APPROVAL_PAUSE: Signal file written to {signal_path}")

    # Mark checkpoint as waiting for human response
    _update_checkpoint_status(state, STATUS_WAITING_FOR_HUMAN)

    # Send initial notification
    priority = "urgent" if config.emergency else "high"
    prefix = "EMERGENCY: " if config.emergency else ""
    try:
        notifier.send_ntfy(
            title=f"SAT: {prefix}Approval Required ({story_id})",
            message=f"Story: {story_title}\nSignal file: {signal_path}",
            priority=priority,
            tags="hand,warning",
        )
    except Exception as e:
        logger.warning(f"APPROVAL_PAUSE: notification failed: {e}")

    # Poll until follow_up_after (normal) or escalation_after (emergency)
    wait_limit = config.escalation_after if config.emergency else config.follow_up_after
    elapsed = 0

    while elapsed < wait_limit:
        sleep_fn(config.poll_interval)
        elapsed += config.poll_interval

        content = read_fn(signal_path)
        if content is not None:
            response = _extract_human_response(content)
            state["pause_response"] = response
            state["approval_status"] = "responded"
            state["approval_elapsed"] = elapsed
            _record_approval_output(state, "APPROVAL_PAUSE", response)
            _update_checkpoint_status(state, STATUS_IN_PROGRESS)
            return state

    # No response within initial wait — still waiting for human
    state["pause_response"] = "no_response"
    state["approval_status"] = "waiting"
    state["approval_elapsed"] = elapsed
    _record_approval_output(state, "APPROVAL_PAUSE", "no_response")
    return state


def approval_follow_up_node(
    state: StoryState,
    notifier: Notifier,
    config: ApprovalConfig,
    _sleep_fn=None,
    _read_fn=None,
) -> StoryState:
    """Send follow-up notification and continue waiting.

    Waits from follow_up_after to escalation_after.
    """
    state = dict(state)
    sleep_fn = _sleep_fn or time.sleep
    read_fn = _read_fn or _read_signal_file

    story = state.get("story", {})
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")
    signal_path = state.get("approval_signal_path", "")

    # Send follow-up
    try:
        notifier.send_ntfy(
            title=f"SAT: Follow-up - Approval Pending ({story_id})",
            message=f"Story: {story_title}\nAwaiting your response.\nSignal file: {signal_path}",
            priority="high",
            tags="bell,warning",
        )
    except Exception as e:
        logger.warning(f"APPROVAL_FOLLOW_UP: notification failed: {e}")

    # Wait from follow_up to escalation
    remaining = config.escalation_after - config.follow_up_after
    elapsed = 0

    while elapsed < remaining:
        sleep_fn(config.poll_interval)
        elapsed += config.poll_interval

        content = read_fn(signal_path)
        if content is not None:
            response = _extract_human_response(content)
            state["pause_response"] = response
            state["approval_status"] = "responded"
            state["approval_elapsed"] = state.get("approval_elapsed", 0) + elapsed
            _record_approval_output(state, "APPROVAL_FOLLOW_UP", response)
            _update_checkpoint_status(state, STATUS_IN_PROGRESS)
            return state

    # Still waiting for human
    state["pause_response"] = "no_response"
    state["approval_status"] = "waiting"
    state["approval_elapsed"] = state.get("approval_elapsed", 0) + elapsed
    _record_approval_output(state, "APPROVAL_FOLLOW_UP", "no_response")
    return state


def approval_escalation_node(
    state: StoryState,
    notifier: Notifier,
    config: ApprovalConfig,
    _sleep_fn=None,
    _read_fn=None,
) -> StoryState:
    """Escalate: send urgent notifications, wait until auto_timeout.

    If auto_timeout is reached and auto_approve_on_timeout is True
    (emergency path), auto-approves. Otherwise returns "timeout".
    """
    state = dict(state)
    sleep_fn = _sleep_fn or time.sleep
    read_fn = _read_fn or _read_signal_file

    story = state.get("story", {})
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")
    signal_path = state.get("approval_signal_path", "")

    # Send escalation notification
    try:
        notifier.send_ntfy(
            title=f"SAT: ESCALATION - Approval Overdue ({story_id})",
            message=(
                f"Story: {story_title}\n"
                f"No response after {state.get('approval_elapsed', 0)}s.\n"
                f"Signal file: {signal_path}"
            ),
            priority="urgent",
            tags="rotating_light,warning",
        )
    except Exception as e:
        logger.warning(f"APPROVAL_ESCALATION: notification failed: {e}")

    # Notify additional escalation contacts if configured
    for contact in config.escalation_contacts:
        try:
            notifier.send_email(
                subject=f"SAT: ESCALATION - Approval Overdue ({story_id})",
                body_text=f"Story {story_id} ({story_title}) requires approval. No response after {state.get('approval_elapsed', 0)}s.",
                body_html=f"<h2>Approval Overdue: {story_id}</h2><p>{story_title}</p>",
                recipient=contact,
            )
        except Exception as e:
            logger.warning(f"APPROVAL_ESCALATION: email to {contact} failed: {e}")

    # Wait until auto_timeout
    remaining = config.auto_timeout - config.escalation_after
    if remaining <= 0:
        remaining = config.escalation_after  # Fallback: wait another escalation period

    elapsed = 0
    while elapsed < remaining:
        sleep_fn(config.poll_interval)
        elapsed += config.poll_interval

        content = read_fn(signal_path)
        if content is not None:
            response = _extract_human_response(content)
            state["pause_response"] = response
            state["approval_status"] = "responded"
            state["pause_escalated"] = True
            state["approval_elapsed"] = state.get("approval_elapsed", 0) + elapsed
            _record_approval_output(state, "APPROVAL_ESCALATION", response)
            _update_checkpoint_status(state, STATUS_IN_PROGRESS)
            return state

    # Timeout reached
    state["pause_escalated"] = True
    state["approval_elapsed"] = state.get("approval_elapsed", 0) + elapsed

    if config.auto_approve_on_timeout:
        state["pause_response"] = "auto_approved"
        state["approval_status"] = "auto_approved"
        logger.warning(f"APPROVAL_ESCALATION: Auto-approved {story_id} after timeout (emergency path)")
    else:
        state["pause_response"] = "no_response"
        state["approval_status"] = "timeout"
        logger.warning(f"APPROVAL_ESCALATION: Timeout for {story_id}, no auto-approve")

    _record_approval_output(state, "APPROVAL_ESCALATION", state["pause_response"])
    return state


# --- Decision Functions ---

def pause_initial_decision(state: StoryState) -> Literal["responded", "follow_up", "escalate"]:
    """Route after initial pause.

    Normal path: no response → follow_up
    Emergency path: no response → escalate (skip follow-up)
    """
    if state.get("approval_status") == "responded":
        return "responded"
    # Emergency path skips follow-up, goes straight to escalation
    if state.get("approval_status") == "waiting":
        return "follow_up"
    return "follow_up"


def follow_up_decision(state: StoryState) -> Literal["responded", "escalate"]:
    """Route after follow-up: responded or escalate."""
    if state.get("approval_status") == "responded":
        return "responded"
    return "escalate"


def response_decision(state: StoryState) -> Literal["approved", "rejected", "timeout"]:
    """Final routing based on human response content."""
    response = state.get("pause_response", "no_response")

    if response in ("no_response", "timeout"):
        return "timeout"

    if response == "auto_approved":
        return "approved"

    if response.upper().startswith("REJECTED:"):
        return "rejected"

    return "approved"


# --- Helper ---

def _update_checkpoint_status(state: dict, status: str) -> None:
    """Update the checkpoint status for the current task.

    Sets the checkpoint to 'waiting_for_human' when entering an approval pause,
    and back to 'in_progress' when a response is received. This lets the monitor
    and hourly cron distinguish "waiting for human" from "stuck".
    """
    try:
        working_dir = state.get("working_directory", "")
        task_id = state.get("task_id", "")
        if not working_dir or not task_id:
            return
        import os
        db_path = os.path.join(working_dir, ".memory", "checkpoints.db")
        if not os.path.exists(db_path):
            return
        cp = read_checkpoint(db_path, task_id)
        if cp:
            cp.status = status
            write_checkpoint(db_path, cp)
            logger.info(f"Checkpoint status updated: {task_id} → {status}")
    except Exception as e:
        logger.debug(f"Could not update checkpoint status: {e}")


def _record_approval_output(state: dict, phase: str, response: str) -> None:
    """Record approval phase output in state."""
    phase_output = PhaseOutput(
        phase=phase,
        status=PhaseStatus.COMPLETE,
        output=f"response={response[:200]}, status={state.get('approval_status', 'unknown')}",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]


# --- Workflow Class ---

class ApprovalWorkflow:
    """Approval workflow with Normal and Emergency paths.

    Normal path:
        PAUSE → (no response) → FOLLOW_UP → (no response) → ESCALATION → decision

    Emergency path:
        PAUSE → (no response) → ESCALATION → decision (auto-approve on timeout)

    In both paths, if the human responds at any stage, the workflow
    routes directly to the response_decision node.
    """

    def __init__(self, notifier: Notifier, config: Optional[ApprovalConfig] = None):
        self.notifier = notifier
        self.config = config or ApprovalConfig()

    def build_graph(self) -> StateGraph:
        from functools import partial

        builder = StateGraph(StoryState)
        cfg = self.config
        ntf = self.notifier

        # Nodes
        builder.add_node("pause", partial(
            approval_pause_node, notifier=ntf, config=cfg,
        ))
        builder.add_node("follow_up", partial(
            approval_follow_up_node, notifier=ntf, config=cfg,
        ))
        builder.add_node("escalation", partial(
            approval_escalation_node, notifier=ntf, config=cfg,
        ))

        # Entry
        builder.set_entry_point("pause")

        if cfg.emergency:
            # Emergency path: PAUSE → responded or escalate (skip follow-up)
            builder.add_conditional_edges("pause", pause_initial_decision, {
                "responded": END,
                "follow_up": "escalation",  # Emergency skips follow-up
                "escalate": "escalation",
            })
        else:
            # Normal path: PAUSE → responded, follow_up, or escalate
            builder.add_conditional_edges("pause", pause_initial_decision, {
                "responded": END,
                "follow_up": "follow_up",
                "escalate": "escalation",
            })

            # Follow-up → responded or escalate
            builder.add_conditional_edges("follow_up", follow_up_decision, {
                "responded": END,
                "escalate": "escalation",
            })

        # Escalation → END (final decision made in escalation_node)
        builder.add_edge("escalation", END)

        return builder

    def compile(self, checkpointer=None):
        """Compile the approval workflow graph."""
        return self.build_graph().compile(checkpointer=checkpointer)
