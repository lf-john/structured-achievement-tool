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
import datetime  # Added for checkpoint metadata timestamp
import json
import logging
import os
from dataclasses import dataclass, field

from src.agents.failure_classifier import FailureSeverity, classify_failure
from src.core.checkpoint_manager import Checkpoint, read_checkpoint, write_checkpoint
from src.core.checkpoint_manager import init_db as init_checkpoint_db
from src.execution.git_manager import (
    _run_git,
    create_story_worktree,
    get_current_commit,
    get_worktree_diff,
    merge_story_worktree,
    remove_story_worktree,
    reset_to_commit,
)
from src.llm.routing_engine import RoutingEngine
from src.notifications.notifier import Notifier
from src.workflows.assignment_workflow import AssignmentWorkflow
from src.workflows.config_tdd_workflow import ConfigTDDWorkflow
from src.workflows.content_workflow import ContentWorkflow
from src.workflows.conversation_workflow import ConversationWorkflow
from src.workflows.debug_workflow import DebugWorkflow
from src.workflows.dev_tdd_workflow import DevTDDWorkflow
from src.workflows.document_assembly_workflow import DocumentAssemblyWorkflow
from src.workflows.escalation_workflow import EscalationWorkflow
from src.workflows.maintenance_workflow import MaintenanceWorkflow
from src.workflows.qa_feedback_workflow import QAFeedbackWorkflow
from src.workflows.research_workflow import ResearchWorkflow
from src.workflows.review_workflow import ReviewWorkflow
from src.workflows.state import create_initial_state
from src.workflows.task_verification_workflow import TaskVerificationWorkflow

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
    "conversation": ConversationWorkflow,  # Single execute + optional persist (store flag)
    "content": ContentWorkflow,
    "assignment": AssignmentWorkflow,
    # human_task: lazy-imported in get_workflow_for_story (DelayedChecker dependency)
    "qa_feedback": QAFeedbackWorkflow,
    "escalation": EscalationWorkflow,
    "task_verification": TaskVerificationWorkflow,
    "document_assembly": DocumentAssemblyWorkflow,
}


# Human story types that require a notifier
HUMAN_STORY_TYPES = {"assignment", "human_task", "qa_feedback", "escalation"}


def get_workflow_for_story(
    story: dict,
    routing_engine: RoutingEngine,
    notifier: Notifier | None = None,
    checkpointer=None,
):
    """Select and compile the appropriate workflow for a story type.

    Workflow is determined by story type alone (no tdd field).
    Raises ValueError if the story type has no matching workflow.
    """
    story_type = story.get("type", "development")

    if story_type == "human_task":
        from src.workflows.human_task_workflow import HumanTaskWorkflow

        workflow_cls = HumanTaskWorkflow
    else:
        workflow_cls = WORKFLOW_MAP.get(story_type)
        if workflow_cls is None:
            raise ValueError(f"No workflow for story type '{story_type}'. Valid types: {sorted(WORKFLOW_MAP.keys())}")

    # Human workflows need notifier in addition to routing_engine
    if story_type in HUMAN_STORY_TYPES:
        workflow = workflow_cls(
            routing_engine=routing_engine,
            notifier=notifier or Notifier(),
        )
    else:
        workflow = workflow_cls(routing_engine=routing_engine)

    return workflow.compile(checkpointer=checkpointer)


def _load_execution_config() -> dict:
    """Load execution config from config.json.

    Returns the 'execution' block, or an empty dict if not found.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config.json",
    )
    try:
        with open(config_path) as f:
            return json.load(f).get("execution", {})
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not load config.json: {e}")
        return {}


async def execute_story(
    story: dict,
    task_id: str,
    task_description: str,
    working_directory: str,
    routing_engine: RoutingEngine | None = None,
    notifier: Notifier | None = None,
    max_attempts: int = MAX_ATTEMPTS_PER_STORY,
    mediator_enabled: bool = False,
    cancellation_event: asyncio.Event | None = None,
    audit_journal=None,
    task_file: str | None = None,
) -> StoryResult:
    """Execute a story through its workflow with retry logic.

    If ``use_worktree`` is enabled in config.json the story runs inside an
    isolated git worktree so the main repo is never modified by agentic LLMs.
    On success the worktree branch is merged back; on failure the worktree is
    simply discarded.

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
        audit_journal: Optional audit journal (accepted for API compatibility)
        task_file: Optional path to the originating task file

    Returns:
        StoryResult with success/failure status
    """
    re = routing_engine or RoutingEngine()
    story_id = story.get("id", "unknown")
    story.get("title", "Untitled")

    # Set hierarchical correlation context for this story
    try:
        from src.logging_config import set_story_context

        set_story_context(story_id)
    except Exception:
        pass

    # --- Worktree isolation ---
    # Only development/config/debug story types benefit from worktree isolation.
    # Content/research/review workflows write files to absolute paths specified
    # in the task description, which would miss the worktree and end up in the
    # base repo.  Skip worktree for these types to avoid silent no-op merges.
    WORKTREE_TYPES = {"development", "config", "debug", "maintenance"}
    exec_config = _load_execution_config()
    story_type = story.get("type", "development")
    use_worktree = exec_config.get("use_worktree", False) and story_type in WORKTREE_TYPES
    worktree_path: str | None = None
    effective_working_dir = working_directory

    if use_worktree:
        try:
            worktree_path = create_story_worktree(story_id, working_directory)
            effective_working_dir = worktree_path
            logger.info(f"Story {story_id}: using worktree isolation at {worktree_path}")
        except RuntimeError as e:
            logger.error(f"Story {story_id}: failed to create worktree, falling back to main repo: {e}")
            worktree_path = None
            effective_working_dir = working_directory

    result = None
    merge_failed = False

    try:
        result = await _execute_story_inner(
            story=story,
            task_id=task_id,
            task_description=task_description,
            working_directory=effective_working_dir,
            routing_engine=re,
            notifier=notifier,
            max_attempts=max_attempts,
            mediator_enabled=mediator_enabled,
            cancellation_event=cancellation_event,
        )

        # Merge worktree back on success
        if worktree_path and result.success:
            diff_output = get_worktree_diff(worktree_path)
            if diff_output:
                logger.info(f"Story {story_id}: worktree has uncommitted changes, they will be committed before merge")
            merged = merge_story_worktree(worktree_path, working_directory)
            if merged:
                logger.info(f"Story {story_id}: merged worktree changes into main repo")
            else:
                merge_failed = True
                logger.error(
                    f"Story {story_id}: worktree merge FAILED — changes remain "
                    f"on branch story/{story_id} for manual review"
                )
                result.reason = (f"{result.reason}; worktree merge failed — changes on branch story/{story_id}").strip(
                    "; "
                )

        return result

    except Exception as e:
        # If _execute_story_inner raised, return a failure result
        logger.error(f"Story {story_id}: execution crashed: {e}")
        if result is None:
            result = StoryResult(
                story_id=story_id,
                success=False,
                reason=f"Execution crashed: {e}",
            )
        return result

    finally:
        # Clean up worktree only if merge succeeded or story failed.
        # On merge failure, preserve the branch for manual recovery.
        if worktree_path:
            if merge_failed:
                # Remove the worktree directory but keep the branch
                try:
                    if os.path.isdir(worktree_path):
                        _run_git(["worktree", "remove", worktree_path, "--force"], working_directory)
                    logger.warning(
                        f"Story {story_id}: worktree directory removed but branch "
                        f"story/{story_id} preserved for manual review"
                    )
                except Exception as e:
                    logger.warning(f"Story {story_id}: worktree directory cleanup failed: {e}")
            else:
                try:
                    remove_story_worktree(worktree_path, working_directory)
                    logger.info(f"Story {story_id}: cleaned up worktree at {worktree_path}")
                except Exception as e:
                    logger.warning(f"Story {story_id}: worktree cleanup failed: {e}")


async def _execute_story_inner(
    story: dict,
    task_id: str,
    task_description: str,
    working_directory: str,
    routing_engine: RoutingEngine,
    notifier: Notifier | None = None,
    max_attempts: int = MAX_ATTEMPTS_PER_STORY,
    mediator_enabled: bool = False,
    cancellation_event: asyncio.Event | None = None,
) -> StoryResult:
    """Inner story execution logic (retry loop, workflow invocation).

    Separated from execute_story to keep worktree lifecycle management clean.
    """
    re = routing_engine
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")

    # Unique run ID to prevent LangGraph checkpoint collisions across task files.
    # Without this, different tasks that decompose to the same story ID (e.g. US-001)
    # would resume from a previous run's completed checkpoint instead of starting fresh.
    run_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = os.path.join(working_directory, ".memory", "langgraph_checkpoints.db")
    sat_db_path = os.path.join(working_directory, ".memory", "checkpoints.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    with SqliteSaver.from_conn_string(db_path) as checkpointer:
        # Get compiled workflow
        graph = get_workflow_for_story(story, re, notifier=notifier, checkpointer=checkpointer)

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

            config = {
                "configurable": {
                    "thread_id": f"{task_id}_{story_id}_{run_id}_attempt_{attempt}",
                    "task_id": task_id,
                },
                "metadata": {
                    "task_id": task_id,
                    "timestamp": datetime.datetime.now().isoformat(),
                },
            }

            # Check if we should resume
            state_to_invoke = None
            checkpoint_state = graph.get_state(config)
            if not checkpoint_state.values:
                # Create initial state for fresh run
                state_to_invoke = create_initial_state(
                    story=story,
                    task_id=task_id,
                    task_description=task_description,
                    working_directory=working_directory,
                    max_attempts=max_attempts,
                    mediator_enabled=mediator_enabled,
                )
                state_to_invoke["story_attempt"] = attempt
                # Feed failure context from prior attempt, including any partial output
                if attempt > 1 and last_failure_reason:
                    # If the previous failure was a timeout with partial output,
                    # include it with a caveat about quality
                    if "WATCHDOG" in last_failure_reason and "Partial output recovered" in last_failure_reason:
                        state_to_invoke["failure_context"] = (
                            f"PRIOR ATTEMPT FAILED (timeout). The previous agent was killed "
                            f"because it exceeded the time limit. Partial output was recovered "
                            f"but may be incomplete or low quality — use it as a hint, not as "
                            f"a reliable starting point.\n\n"
                            f"Previous failure details:\n{last_failure_reason}"
                        )
                    else:
                        state_to_invoke["failure_context"] = last_failure_reason
                else:
                    state_to_invoke["failure_context"] = ""

            try:
                final_state = graph.invoke(state_to_invoke, config=config)

                # Check if workflow completed successfully
                phase_outputs = final_state.get("phase_outputs", [])
                last_phase = phase_outputs[-1] if phase_outputs else {}
                last_status = last_phase.get("status", "failed")

                # Verification requirements depend on story type:
                # - dev/config/maintenance: verify_passed MUST be True (verification mandatory)
                # - other types: verify_passed=None is acceptable (no verification needed)
                verify_passed = final_state.get("verify_passed")
                story_type = story.get("type", "development")
                VERIFIED_TYPES = {"development", "config", "maintenance"}
                if story_type in VERIFIED_TYPES:
                    verification_ok = verify_passed is True
                else:
                    # Content/research/conversation workflows manage their own
                    # quality gates via retry limits.  If the workflow reached
                    # LEARN and completed, the story succeeded regardless of
                    # the final verify_passed flag (which stays False when
                    # retry limits are hit and the workflow skips ahead).
                    verification_ok = True
                if last_status == "complete" and verification_ok:
                    # Success
                    if notifier:
                        notifier.notify_story_complete(story_id, story_title)

                    # Update story-level checkpoint
                    try:
                        init_checkpoint_db(sat_db_path)
                        checkpoint = read_checkpoint(sat_db_path, task_id)
                        if checkpoint:
                            if story_id not in checkpoint.completed_stories:
                                checkpoint.completed_stories.append(story_id)
                            if story_id in checkpoint.pending_stories:
                                checkpoint.pending_stories.remove(story_id)
                        else:
                            checkpoint = Checkpoint(
                                task_id=task_id,
                                current_phase="EXECUTION",
                                completed_stories=[story_id],
                                pending_stories=[],
                            )
                        write_checkpoint(sat_db_path, checkpoint)
                        logger.info(f"Updated checkpoint for task {task_id} after story {story_id}")
                    except Exception as cp_err:
                        logger.warning(f"Failed to update story-level checkpoint: {cp_err}")

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

                # Identical-failure detection (Failure State 6 + Enhancement #7):
                # Compute a short signature from phase + first 200 chars of error.
                # If the same signature appears twice, allow ONE more attempt with
                # escalated provider. If it appears three times, stop.
                _sig = f"{last_phase.get('phase', '')}:{failure_output[:200]}"
                _failure_signatures.append(_sig)
                identical_count = sum(1 for s in _failure_signatures if s == _sig)
                if identical_count >= 3:
                    logger.warning(
                        "Identical failure signature detected 3 times for %s — "
                        "story is stuck, skipping remaining retries",
                        story_id,
                    )
                    if notifier:
                        notifier.notify_story_failed(
                            story_id,
                            story_title,
                            f"Stuck: identical failure x3: {classification.message}",
                        )
                    return StoryResult(
                        story_id=story_id,
                        success=False,
                        attempts=attempt,
                        reason=f"Stuck: identical failure x3. Last: {classification.message}",
                        phase_outputs=phase_outputs,
                    )
                elif identical_count == 2:
                    logger.warning(
                        "Identical failure x2 for %s — one more attempt allowed with potential escalation",
                        story_id,
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
                    logger.error(
                        f"Circuit breaker triggered for {story_id} after {consecutive_env_failures} environmental failures"
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

        return StoryResult(
            story_id=story_id,
            success=False,
            attempts=max_attempts,
            reason=f"Exhausted {max_attempts} attempts. Last failure: {last_failure_reason}",
        )
