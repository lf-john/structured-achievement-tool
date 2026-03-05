"""
Control Nodes — Reusable NOTIFY and PAUSE nodes for LangGraph workflows.

Phase 3, items 3.9 (NOTIFY) and 3.10 (PAUSE).

NOTIFY: Side-effect node that sends notifications about workflow progress.
PAUSE: Blocking node that writes a signal file and polls for human response.

These nodes are not LLM calls — they are control-flow primitives that can be
inserted into any story workflow graph.
"""

import logging
import os
import time
from typing import Literal

from src.notifications.notifier import Notifier
from src.workflows.state import PhaseOutput, PhaseStatus, StoryState

logger = logging.getLogger(__name__)

DEFAULT_SIGNAL_DIR = "~/GoogleDrive/DriveSyncFiles/sat-tasks"


# --- NOTIFY Node ---

def notify_node(
    state: StoryState,
    notifier: Notifier,
    channel: str = "all",
) -> StoryState:
    """Send notification about current story progress.

    This is a pure side-effect node — it reads state and sends a notification
    but does not alter state beyond recording its own phase output.

    Args:
        state: Current workflow state.
        notifier: Notifier instance for sending messages.
        channel: "ntfy", "email", or "all".

    Sends notification with:
    - Story ID and title
    - Current phase
    - Status (success/failure based on verify_passed)
    - Brief context from latest phase output
    """
    state = dict(state)  # Copy for mutation

    story = state.get("story", {})
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")
    current_phase = state.get("current_phase", "UNKNOWN")
    verify_passed = state.get("verify_passed")

    # Determine status label
    if verify_passed is True:
        status_label = "SUCCESS"
        priority = "default"
        tags = "white_check_mark"
    elif verify_passed is False:
        status_label = "FAILED"
        priority = "high"
        tags = "x"
    else:
        status_label = "IN PROGRESS"
        priority = "default"
        tags = "hourglass"

    # Extract brief context from the latest phase output
    phase_outputs = state.get("phase_outputs", [])
    latest_context = ""
    if phase_outputs:
        latest = phase_outputs[-1]
        raw_output = latest.get("output", "")
        latest_context = raw_output[:200].strip()
        if len(raw_output) > 200:
            latest_context += "..."

    title = f"SAT: {story_id} [{current_phase}] {status_label}"
    message = f"Story: {story_title}\nPhase: {current_phase}\nStatus: {status_label}"
    if latest_context:
        message += f"\nContext: {latest_context}"

    ntfy_sent = False
    email_sent = False

    if channel in ("ntfy", "all"):
        try:
            ntfy_sent = notifier.send_ntfy(
                title=title,
                message=message,
                priority=priority,
                tags=tags,
            )
        except Exception as e:
            logger.warning(f"NOTIFY node: ntfy send failed: {e}")

    if channel in ("email", "all"):
        try:
            html_body = (
                f"<h2>{title}</h2>"
                f"<p><strong>Story:</strong> {story_title}</p>"
                f"<p><strong>Phase:</strong> {current_phase}</p>"
                f"<p><strong>Status:</strong> {status_label}</p>"
            )
            if latest_context:
                html_body += f"<p><strong>Context:</strong> {latest_context}</p>"

            email_sent = notifier.send_email(
                subject=title,
                body_html=html_body,
                body_text=message,
            )
        except Exception as e:
            logger.warning(f"NOTIFY node: email send failed: {e}")

    # Record phase output (NOTIFY is always "complete" — notification failures
    # are logged but do not block the workflow)
    phase_output = PhaseOutput(
        phase="NOTIFY",
        status=PhaseStatus.COMPLETE,
        output=f"ntfy={ntfy_sent}, email={email_sent}, channel={channel}",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    logger.info(f"NOTIFY node: {title} (ntfy={ntfy_sent}, email={email_sent})")
    return state


# --- PAUSE Node ---

def _build_signal_content(state: StoryState) -> str:
    """Build the markdown content for a PAUSE signal file."""
    story = state.get("story", {})
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")
    current_phase = state.get("current_phase", "UNKNOWN")
    task_id = state.get("task_id", "unknown")

    # Get latest phase context
    phase_outputs = state.get("phase_outputs", [])
    latest_context = ""
    if phase_outputs:
        latest = phase_outputs[-1]
        raw_output = latest.get("output", "")
        latest_context = raw_output[:500].strip()

    verify_passed = state.get("verify_passed")
    status_str = "passed" if verify_passed is True else ("failed" if verify_passed is False else "pending")

    content = (
        f"# Approval Required: {story_id}\n\n"
        f"**Task:** {task_id}\n"
        f"**Story:** {story_title}\n"
        f"**Phase:** {current_phase}\n"
        f"**Verification:** {status_str}\n\n"
        f"## Context\n\n"
        f"{latest_context}\n\n"
        f"## Your Response\n\n"
        f"Write your response below this line, then remove the `#` from `# <Pending>` to signal approval.\n"
        f"Write `REJECTED:` followed by your reason to reject.\n\n"
        f"---\n\n"
        f"# <Pending>\n"
    )
    return content


def _read_signal_file(signal_path: str) -> str | None:
    """Read signal file and return content if human has responded.

    Returns None if the file still contains '# <Pending>' (not yet responded).
    Returns the file content string if '<Pending>' tag has been activated
    (the '#' prefix removed).
    """
    try:
        with open(signal_path) as f:
            content = f.read()
    except (FileNotFoundError, PermissionError) as e:
        logger.warning(f"PAUSE: Cannot read signal file {signal_path}: {e}")
        return None

    # Check if human has responded: the '# <Pending>' should have been
    # changed to '<Pending>' (# removed). We check that '# <Pending>'
    # is NOT present but '<Pending>' IS present, meaning user activated it.
    if "# <Pending>" in content:
        return None  # Still waiting

    if "<Pending>" in content:
        return content  # User removed the '#', signaling response

    # If neither form is present, the user may have removed the tag entirely
    # or replaced it — treat as responded.
    return content


def _extract_human_response(content: str) -> str:
    """Extract the human's response text from the signal file content.

    Looks for text between the '---' separator and the '<Pending>' tag,
    or any text the user added after the separator.
    """
    # Split on the separator
    parts = content.split("---")
    if len(parts) < 2:
        return content.strip()

    response_section = parts[-1].strip()

    # Remove the <Pending> tag if present
    response_section = response_section.replace("<Pending>", "").strip()

    return response_section if response_section else "approved"


def pause_node(
    state: StoryState,
    notifier: Notifier,
    signal_dir: str = DEFAULT_SIGNAL_DIR,
    escalation_timeout: int = 3600,
    poll_interval: int = 30,
    _sleep_fn=None,
    _write_fn=None,
    _read_fn=None,
) -> StoryState:
    """Pause workflow and wait for human signal.

    1. Creates a signal file: {signal_dir}/approvals/{story_id}_approval.md
       with task context and # <Pending> tag.
    2. Sends notification to user via ntfy.
    3. Polls file for human response (user adds response text and removes #
       from # <Pending>).
    4. If escalation_timeout expires without response:
       - Sends escalation notification (high priority).
       - Waits another escalation_timeout.
       - If still no response, auto-continues with "no_response" state.

    Updates state:
    - pause_response: str (human's response text, or "no_response")
    - pause_escalated: bool

    The _sleep_fn, _write_fn, and _read_fn parameters are for testing only.
    """
    state = dict(state)  # Copy for mutation

    sleep_fn = _sleep_fn or time.sleep
    write_fn = _write_fn or _default_write_signal
    read_fn = _read_fn or _read_signal_file

    story = state.get("story", {})
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")

    # Expand ~ in signal_dir
    expanded_dir = os.path.expanduser(signal_dir)
    approvals_dir = os.path.join(expanded_dir, "approvals")
    signal_path = os.path.join(approvals_dir, f"{story_id}_approval.md")

    # 1. Write signal file
    signal_content = _build_signal_content(state)
    write_fn(signal_path, signal_content)
    logger.info(f"PAUSE node: Signal file written to {signal_path}")

    # 2. Send notification
    try:
        notifier.send_ntfy(
            title=f"SAT: Approval Required ({story_id})",
            message=f"Story: {story_title}\nSignal file: {signal_path}",
            priority="high",
            tags="hand,warning",
        )
    except Exception as e:
        logger.warning(f"PAUSE node: Failed to send initial notification: {e}")

    # 3. Poll for response
    elapsed = 0

    while elapsed < escalation_timeout:
        sleep_fn(poll_interval)
        elapsed += poll_interval

        content = read_fn(signal_path)
        if content is not None:
            response = _extract_human_response(content)
            state["pause_response"] = response
            state["pause_escalated"] = False
            _record_pause_output(state, response, escalated=False)
            logger.info(f"PAUSE node: Human responded: {response[:100]}")
            return state

    # 4. Escalation: first timeout expired
    logger.warning(f"PAUSE node: Escalation timeout reached for {story_id}")

    try:
        notifier.send_ntfy(
            title=f"SAT: ESCALATION - Approval Overdue ({story_id})",
            message=f"Story: {story_title}\nNo response after {escalation_timeout}s.\nSignal file: {signal_path}",
            priority="urgent",
            tags="rotating_light,warning",
        )
    except Exception as e:
        logger.warning(f"PAUSE node: Failed to send escalation notification: {e}")

    # Wait another escalation_timeout
    elapsed_2 = 0
    while elapsed_2 < escalation_timeout:
        sleep_fn(poll_interval)
        elapsed_2 += poll_interval

        content = read_fn(signal_path)
        if content is not None:
            response = _extract_human_response(content)
            state["pause_response"] = response
            state["pause_escalated"] = True
            _record_pause_output(state, response, escalated=True)
            logger.info(f"PAUSE node: Human responded after escalation: {response[:100]}")
            return state

    # 5. Double timeout — auto-continue with no_response
    state["pause_response"] = "no_response"
    state["pause_escalated"] = True
    _record_pause_output(state, "no_response", escalated=True)
    logger.warning(f"PAUSE node: Double timeout for {story_id}, auto-continuing")
    return state


def _default_write_signal(signal_path: str, content: str) -> None:
    """Write signal file to disk, creating directories as needed."""
    os.makedirs(os.path.dirname(signal_path), exist_ok=True)
    with open(signal_path, "w") as f:
        f.write(content)
    # fsync for Google Drive FUSE reliability
    try:
        fd = os.open(signal_path, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except OSError:
        pass


def _record_pause_output(state: dict, response: str, escalated: bool) -> None:
    """Record PAUSE phase output in state."""
    status = PhaseStatus.COMPLETE
    output = f"response={response[:200]}, escalated={escalated}"

    phase_output = PhaseOutput(
        phase="PAUSE",
        status=status,
        output=output,
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]


# --- Decision Functions ---

def pause_decision(state: StoryState) -> Literal["approved", "rejected", "timeout"]:
    """Route after PAUSE node based on human response.

    Returns:
        "approved" — human approved or wrote a non-rejection response.
        "rejected" — human response starts with "REJECTED:" prefix.
        "timeout" — no human response (auto-continued after double timeout).
    """
    response = state.get("pause_response", "no_response")

    if response == "no_response":
        return "timeout"

    if response.upper().startswith("REJECTED:"):
        return "rejected"

    return "approved"
