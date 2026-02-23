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
from typing import Optional, Dict, List, Any
from datetime import datetime

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

def _log_audit_record(
    audit_journal: AuditJournal,
    story_id: str,
    story_title: str,
    task_file: str,
    success: bool,
    attempts: int,
    start_time: float,
    reason: Optional[str] = None,
    final_state: Optional[Dict[str, Any]] = None,
    exit_code: int = 0,
):
    """Helper function to create and log an audit record."""
    end_time = time.time()
    duration = round(end_time - start_time, 2)

    llm_provider_used_per_phase = final_state.get("llm_provider_used_per_phase", {}) if final_state else {}
    phases_completed = [p.get("phase", "") for p in final_state.get("phase_outputs", []) if p.get("phase")] if final_state else []

    record = AuditRecord(
        timestamp=datetime.now().isoformat(),
        task_file=task_file,
        story_id=story_id,
        story_title=story_title,
        llm_provider_used_per_phase=llm_provider_used_per_phase,
        session_id=f"{task_file}-{story_id}",
        total_turns=attempts,
        exit_code=exit_code,
        duration_seconds=duration,
        success=success,
        phases_completed=phases_completed,
        error_summary=reason,
    )
    audit_journal.log_record(record)


def get_workflow_for_story(story: Dict, routing_engine: RoutingEngine):
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


async def execute_story(
    story: Dict,
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
    start_time = time.time()
    audit_journal = AuditJournal()

    re = routing_engine or RoutingEngine()
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")

    # Get compiled workflow
    graph = get_workflow_for_story(story, re)

    # Capture base commit for reset on retry
    base_commit = get_current_commit(working_directory)

    consecutive_env_failures = 0
    last_failure_reason = ""

    final_state_for_audit: Optional[Dict[str, Any]] = None # To capture final state even on early exits

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Story {story_id} attempt {attempt}/{max_attempts}")

        # Check for cancellation
        if cancellation_event and cancellation_event.is_set():
            _log_audit_record(
                audit_journal=audit_journal,
                story_id=story_id,
                story_title=story_title,
                task_file=task_id,
                success=False,
                attempts=attempt,
                start_time=start_time,
                reason="Cancelled by user",
                exit_code=-2, # Custom exit code for cancellation
            )
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
            final_state_for_audit = final_state # Capture for audit logging

            # Check if workflow completed successfully
            phase_outputs = final_state.get("phase_outputs", [])
            last_phase = phase_outputs[-1] if phase_outputs else {}
            last_status = last_phase.get("status", "failed")

            if last_status == "complete" and final_state.get("verify_passed", True):
                # Success
                if notifier:
                    notifier.notify_story_complete(story_id, story_title)

                _log_audit_record(
                    audit_journal=audit_journal,
                    story_id=story_id,
                    story_title=story_title,
                    task_file=task_id,
                    success=True,
                    attempts=attempt,
                    start_time=start_time,
                    final_state=final_state,
                    exit_code=0,
                )
                return StoryResult(
                    story_id=story_id,
                    success=True,
                    attempts=attempt,
                    phase_outputs=phase_outputs,
                )

            # Workflow completed but with failures
            failure_output = final_state.get("failure_context", "")
            last_phase_exit_code = last_phase.get("exit_code", 1)
            classification = classify_failure(
                exit_code=last_phase_exit_code,
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
                
                _log_audit_record(
                    audit_journal=audit_journal,
                    story_id=story_id,
                    story_title=story_title,
                    task_file=task_id,
                    success=False,
                    attempts=attempt,
                    start_time=start_time,
                    reason=classification.message,
                    final_state=final_state,
                    exit_code=last_phase_exit_code,
                )
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

            exception_exit_code = -1 # General exception
            classification = classify_failure(exit_code=exception_exit_code, output=str(e))

            if classification.severity == FailureSeverity.TRANSIENT:
                consecutive_env_failures += 1
            else:
                consecutive_env_failures = 0

            # Circuit breaker
            if consecutive_env_failures >= CIRCUIT_BREAKER_THRESHOLD:
                logger.error(f"Circuit breaker triggered for {story_id} after {consecutive_env_failures} environmental failures")
                _log_audit_record(
                    audit_journal=audit_journal,
                    story_id=story_id,
                    story_title=story_title,
                    task_file=task_id,
                    success=False,
                    attempts=attempt,
                    start_time=start_time,
                    reason=f"Circuit breaker: {consecutive_env_failures} consecutive environmental failures. Last exception: {e}",
                    final_state=final_state_for_audit, # Pass the last known final state
                    exit_code=-3, # Custom exit code for circuit breaker
                )
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

    _log_audit_record(
        audit_journal=audit_journal,
        story_id=story_id,
        story_title=story_title,
        task_file=task_id,
        success=False,
        attempts=max_attempts,
        start_time=start_time,
        reason=f"Exhausted {max_attempts} attempts. Last failure: {last_failure_reason}",
        final_state=final_state_for_audit, # Pass the last known final state if any
        exit_code=-1, # Custom exit code for exhausted attempts
    )
    return StoryResult(
        story_id=story_id,
        success=False,
        attempts=max_attempts,
        reason=f"Exhausted {max_attempts} attempts. Last failure: {last_failure_reason}",
    )
