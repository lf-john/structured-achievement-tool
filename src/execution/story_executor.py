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
from src.llm.routing_engine import RoutingEngine
from src.agents.failure_classifier import classify_failure, FailureSeverity
from src.execution.git_manager import get_current_commit, reset_to_commit
from src.notifications.notifier import Notifier
from src.execution.audit_journal import AuditJournal, AuditRecord
from datetime import datetime
import os

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
}


def get_workflow_for_story(story: dict, routing_engine: RoutingEngine):
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

    workflow = workflow_cls(routing_engine=routing_engine)
    return workflow.compile()


def _create_and_log_audit_record(
    audit_journal: AuditJournal,
    story_id: str,
    story_title: str,
    task_id: str,
    story_start_datetime: datetime, # The actual datetime when the story started
    execution_start_monotonic_time: float,

    success: bool,
    final_state: Optional[dict],
    session_id_from_state: str,
    error_summary: Optional[str] = None,
    exit_code: int = 0,
):
    """Helper to create and log an AuditRecord."""
    duration_seconds = (datetime.now() - story_start_datetime).total_seconds()
    phase_outputs = final_state.get("phase_outputs", []) if final_state else []
    llm_provider_per_phase = {
        p.get("phase"): p.get("llm_provider", "unknown")
        for p in phase_outputs
        if p.get("phase")
    }
    phases_completed = [p.get("phase") for p in phase_outputs if p.get("status") == "complete"]
    total_turns = final_state.get("total_turns", 0) if final_state else 0


    record = AuditRecord(
        timestamp=story_start_datetime, # Use the actual story start datetime
        task_file=task_id, # Using task_id for task_file
        story_id=story_id,
        story_title=story_title,
        llm_provider_per_phase=llm_provider_per_phase,
        session_id=session_id_from_state, # Use session_id from state
        total_turns=total_turns,
        exit_code=exit_code,
        duration_seconds=duration_seconds,
        success=success,
        phases_completed=phases_completed,
        error_summary=error_summary,
    )
    audit_journal.append_record(record)


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

    audit_journal_path = os.path.join(working_directory, ".memory", "audit_journal.jsonl")
    audit_journal = AuditJournal(audit_journal_path)
    start_time = time.monotonic()

    # Get compiled workflow
    graph = get_workflow_for_story(story, re)

    # Capture base commit for reset on retry
    base_commit = get_current_commit(working_directory)

    consecutive_env_failures = 0
    last_failure_reason = ""
    state: Optional[StoryState] = None # Initialize state here

    final_success: bool = False
    final_reason: str = ""
    final_exit_code: int = 1
    final_story_state: Optional[dict] = None
    story_completed_successfully_in_loop: bool = False # New flag

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Story {story_id} attempt {attempt}/{max_attempts}")

        # Check for cancellation
        if cancellation_event and cancellation_event.is_set():
            logger.info(f"Story {story_id} cancelled by user.")
            final_success = False
            final_reason = "Cancelled by user"
            final_exit_code = 1
            final_story_state = state if state else {} # Use current state for cancellation, or an empty dict if state is None
            break

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
            final_state = await graph.invoke(state)
            final_story_state = final_state # Update final_story_state here with the result of invoke # ADDED AWAIT HERE

            # Check if workflow completed successfully
            phase_outputs = final_state.get("phase_outputs", [])
            last_phase = phase_outputs[-1] if phase_outputs else {}
            last_status = last_phase.get("status", "failed")

            if last_status == "complete" and final_state.get("verify_passed", True):
                # Success
                if notifier:
                    notifier.notify_story_complete(story_id, story_title)
                final_success = True
                final_reason = "Story completed successfully"
                final_exit_code = 0
                final_story_state = final_state
                story_completed_successfully_in_loop = True # Set the flag here
                break

            # Workflow completed but with failures
            failure_output = final_state.get("failure_context", "")
            classification = classify_failure(
                exit_code=last_phase.get("exit_code", 1),
                output=failure_output,
                phase=last_phase.get("phase", ""),
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
                
                final_success = False
                final_reason = classification.message
                final_exit_code = last_phase.get("exit_code", 1)
                final_story_state = final_state
                break

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
            
            final_story_state = state # Capture state at time of exception
            final_success = False
            final_reason = str(e)
            final_exit_code = 1

            if classification.severity == FailureSeverity.TRANSIENT:
                consecutive_env_failures += 1
            else:
                consecutive_env_failures = 0

            # Circuit breaker
            if consecutive_env_failures >= CIRCUIT_BREAKER_THRESHOLD:
                logger.error(f"Circuit breaker triggered for {story_id} after {consecutive_env_failures} environmental failures")
                
                final_success = False
                final_reason = f"Circuit breaker: {consecutive_env_failures} consecutive environmental failures"
                final_exit_code = 1
                final_story_state = state  # Use current state for circuit breaker
                break # Break out of attempt loop

            last_failure_reason = str(e)
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            await asyncio.sleep(delay)

    # After the loop, determine the final outcome if not already set by a break
    if not story_completed_successfully_in_loop:
        # If we reached here and the story wasn't successfully completed in the loop,
        # it means it either failed fatally, was cancelled, or exhausted attempts.
        # final_success, final_reason, final_exit_code should already be set
        # by the break statements in the failure paths (cancellation, fatal error, circuit breaker).
        # If it just exhausted attempts without a specific fatal or cancellation break,
        # then final_success will be False, and final_reason will be the last_failure_reason.
        if final_reason == "": # This case covers exhaustion without a specific error reason set before
            final_reason = f"Exhausted {max_attempts} attempts. Last failure: {last_failure_reason}"
            final_exit_code = 1
            final_success = False # Ensure it's explicitly False
    else: # Story completed successfully in the loop
        final_success = True
        final_reason = "Story completed successfully"
        final_exit_code = 0

    if final_story_state is None and state is not None:
        final_story_state = state # Fallback to last known state if not set

    # Log audit record once at the end
    _create_and_log_audit_record(
        audit_journal=audit_journal,
        story_id=story_id,
        story_title=story_title,
        task_id=task_id,
        story_start_datetime=final_story_state.get("start_time", datetime.now()) if final_story_state else datetime.now(),
        execution_start_monotonic_time=start_time,
        success=final_success,
        final_state=final_story_state or (state if state is not None else {}), # Ensure a state is always provided
        session_id_from_state=final_story_state.get("session_id", "unknown") if final_story_state else (state.get("session_id", "unknown") if state is not None else "unknown"),
        error_summary=final_reason if not final_success else None,
        exit_code=final_exit_code,
    )

    return StoryResult(
        story_id=story_id,
        success=final_success,
        attempts=attempt,
        reason=final_reason,
        phase_outputs=final_story_state.get("phase_outputs", []) if final_story_state else [],
    )
