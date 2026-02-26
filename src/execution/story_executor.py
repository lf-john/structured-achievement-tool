"""
Story Executor — Execute a single story through its workflow with retry/resume.

Handles:
- Workflow selection based on story type
- Per-story retry logic (5 attempts, exponential backoff)
- Session resume via LangGraph checkpoints
- Graceful interruption (SIGTERM → save state)
- Circuit breaker (3 consecutive environmental failures → halt)
- Git reset on retry (keep code for verify failures, full reset otherwise)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from src.workflows.state import StoryState, create_initial_state
from src.workflows.dev_tdd_workflow import DevTDDWorkflow
from src.workflows.config_tdd_workflow import ConfigTDDWorkflow
from src.workflows.maintenance_workflow import MaintenanceWorkflow
from src.workflows.debug_workflow import DebugWorkflow
from src.workflows.research_workflow import ResearchWorkflow
from src.workflows.review_workflow import ReviewWorkflow
from src.workflows.assignment_workflow import AssignmentWorkflow
from src.workflows.qa_feedback_workflow import QAFeedbackWorkflow
from src.workflows.escalation_workflow import EscalationWorkflow
from src.llm.routing_engine import RoutingEngine
from src.agents.failure_classifier import classify_failure, FailureSeverity
from src.execution.git_manager import get_current_commit, reset_to_commit
from src.notifications.notifier import Notifier

logger = logging.getLogger(__name__)

# Retry configuration
MAX_ATTEMPTS_PER_STORY = 5
RETRY_BASE_DELAY = 5  # seconds
RETRY_MAX_DELAY = 60  # seconds
CIRCUIT_BREAKER_THRESHOLD = 3


@dataclass
class StoryResult:
    """Result of executing a single story."""
    story_id: str
    success: bool
    attempts: int = 1
    reason: str = ""
    phase_outputs: list = field(default_factory=list)
    commit_hashes: list = field(default_factory=list)


# Story type → workflow class mapping
WORKFLOW_MAP = {
    "development": DevTDDWorkflow,
    "config": ConfigTDDWorkflow,
    "maintenance": MaintenanceWorkflow,
    "debug": DebugWorkflow,
    "research": ResearchWorkflow,
    "review": ReviewWorkflow,
    "assignment": AssignmentWorkflow,
    "qa_feedback": QAFeedbackWorkflow,
    "escalation": EscalationWorkflow,
}


# Human story types that require a notifier
HUMAN_STORY_TYPES = {"assignment", "qa_feedback", "escalation"}


def get_workflow_for_story(
    story: dict,
    routing_engine: RoutingEngine,
    notifier: Optional[Notifier] = None,
):
    """Select and compile the appropriate workflow for a story type."""
    story_type = story.get("type", "development")

    # TDD stories always use TDD workflows
    if story.get("tdd", False) and story_type == "development":
        workflow_cls = DevTDDWorkflow
    elif story.get("tdd", False) and story_type == "config":
        workflow_cls = ConfigTDDWorkflow
    elif story.get("tdd", False) and story_type == "maintenance":
        workflow_cls = MaintenanceWorkflow
    else:
        workflow_cls = WORKFLOW_MAP.get(story_type, DevTDDWorkflow)

    # Human workflows need notifier in addition to routing_engine
    if story_type in HUMAN_STORY_TYPES:
        workflow = workflow_cls(
            routing_engine=routing_engine,
            notifier=notifier or Notifier(),
        )
    else:
        workflow = workflow_cls(routing_engine=routing_engine)

    return workflow.compile()


async def execute_story(
    story: dict,
    task_id: str,
    task_description: str,
    working_directory: str,
    routing_engine: Optional[RoutingEngine] = None,
    notifier: Optional[Notifier] = None,
    max_attempts: int = MAX_ATTEMPTS_PER_STORY,
    mediator_enabled: bool = False,
    cancellation_event: Optional[asyncio.Event] = None,
) -> StoryResult:
    """Execute a story through its workflow with retry logic.

    Args:
        story: Story dict from PRD
        task_id: Parent task ID
        task_description: Original user request
        working_directory: Git working directory
        routing_engine: LLM routing engine
        notifier: Notification service
        max_attempts: Max retries per story
        mediator_enabled: Enable mediator review
        cancellation_event: Set this event to request graceful cancellation

    Returns:
        StoryResult with success/failure status
    """
    re = routing_engine or RoutingEngine()
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")

    # Get compiled workflow
    graph = get_workflow_for_story(story, re, notifier=notifier)

    # Capture base commit for reset on retry
    base_commit = get_current_commit(working_directory)

    consecutive_env_failures = 0
    last_failure_reason = ""
    # Track error signatures to detect identical failures (Failure State 6).
    # If the same signature appears twice in a row, skip remaining retries.
    _failure_signatures: list[str] = []

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Story {story_id} attempt {attempt}/{max_attempts}")

        # Check for cancellation
        if cancellation_event and cancellation_event.is_set():
            return StoryResult(
                story_id=story_id,
                success=False,
                attempts=attempt,
                reason="Cancelled by user",
            )

        # Reset on retry (keep code for verify failures, full reset otherwise)
        if attempt > 1 and base_commit:
            if last_failure_reason == "verify_failure":
                logger.info(f"Keeping code for verify retry (attempt {attempt})")
            else:
                logger.info(f"Resetting to base commit for retry (attempt {attempt})")
                reset_to_commit(working_directory, base_commit)

        # Create initial state
        state = create_initial_state(
            story=story,
            task_id=task_id,
            task_description=task_description,
            working_directory=working_directory,
            max_attempts=max_attempts,
            mediator_enabled=mediator_enabled,
        )
        state["story_attempt"] = attempt
        state["failure_context"] = last_failure_reason if attempt > 1 else ""

        # Execute the workflow
        try:
            final_state = graph.invoke(state)

            # Check if workflow completed successfully
            phase_outputs = final_state.get("phase_outputs", [])
            last_phase = phase_outputs[-1] if phase_outputs else {}
            last_status = last_phase.get("status", "failed")

            # verify_passed is None when workflow has no verification phase (e.g., research).
            # Treat None as "no verification needed" (success), only False means failure.
            verify_passed = final_state.get("verify_passed")
            if last_status == "complete" and verify_passed is not False:
                # Success
                if notifier:
                    notifier.notify_story_complete(story_id, story_title)

                return StoryResult(
                    story_id=story_id,
                    success=True,
                    attempts=attempt,
                    phase_outputs=phase_outputs,
                )

            # Workflow completed but with failures
            failure_output = final_state.get("failure_context", "")
            classification = classify_failure(
                exit_code=last_phase.get("exit_code", 1),
                output=failure_output,
                phase=last_phase.get("phase", ""),
            )

            # Identical-failure detection (Failure State 6):
            # Compute a short signature from phase + first 200 chars of error.
            # If the last 2 signatures are identical, stop retrying.
            _sig = f"{last_phase.get('phase', '')}:{failure_output[:200]}"
            _failure_signatures.append(_sig)
            if (
                len(_failure_signatures) >= 2
                and _failure_signatures[-1] == _failure_signatures[-2]
            ):
                logger.warning(
                    "Identical failure signature detected twice for %s — "
                    "skipping remaining retries",
                    story_id,
                )
                if notifier:
                    notifier.notify_story_failed(
                        story_id, story_title,
                        f"Identical failure x2: {classification.message}",
                    )
                return StoryResult(
                    story_id=story_id,
                    success=False,
                    attempts=attempt,
                    reason=f"Identical failure x2. Last: {classification.message}",
                    phase_outputs=phase_outputs,
                )

            if classification.severity == FailureSeverity.TRANSIENT:
                consecutive_env_failures = 0
                last_failure_reason = failure_output
                delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                logger.info(f"Transient failure, retrying in {delay}s: {classification.message}")
                await asyncio.sleep(delay)
                continue

            elif classification.severity == FailureSeverity.FATAL:
                logger.error(f"Fatal failure for {story_id}: {classification.message}")
                if notifier:
                    notifier.notify_story_failed(story_id, story_title, classification.message)
                return StoryResult(
                    story_id=story_id,
                    success=False,
                    attempts=attempt,
                    reason=classification.message,
                    phase_outputs=phase_outputs,
                )

            else:
                # Persistent failure — retry with context
                last_failure_reason = failure_output
                if "verify" in last_phase.get("phase", "").lower():
                    last_failure_reason = "verify_failure"

                delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                logger.info(f"Persistent failure, retrying in {delay}s: {classification.message}")
                await asyncio.sleep(delay)

        except Exception as e:
            logger.error(f"Story {story_id} execution error: {e}")

            classification = classify_failure(exit_code=-1, output=str(e))

            if classification.severity == FailureSeverity.TRANSIENT:
                consecutive_env_failures += 1
            else:
                consecutive_env_failures = 0

            # Circuit breaker
            if consecutive_env_failures >= CIRCUIT_BREAKER_THRESHOLD:
                logger.error(f"Circuit breaker triggered for {story_id} after {consecutive_env_failures} environmental failures")
                return StoryResult(
                    story_id=story_id,
                    success=False,
                    attempts=attempt,
                    reason=f"Circuit breaker: {consecutive_env_failures} consecutive environmental failures",
                )

            last_failure_reason = str(e)
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            await asyncio.sleep(delay)

    # Exhausted all attempts
    if notifier:
        notifier.notify_story_failed(story_id, story_title, f"Failed after {max_attempts} attempts")

    return StoryResult(
        story_id=story_id,
        success=False,
        attempts=max_attempts,
        reason=f"Exhausted {max_attempts} attempts. Last failure: {last_failure_reason}",
    )
