"""
Base Workflow — Shared LangGraph workflow builder with node factories.

Provides:
- phase_node_factory: Creates LLM phase nodes (DESIGN, CODE, etc.)
- automated_check_factory: Creates test execution nodes (TDD_RED_CHECK, etc.)
- mediator_gate_factory: Optional mediator review between phases
- Common post-phase hooks: auto-commit, state updates

All workflows subclass BaseWorkflow and declare phases + edges.
"""

import asyncio
import concurrent.futures
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Literal, Optional, Any
from functools import partial

from langgraph.graph import StateGraph, END

from src.workflows.state import (
    StoryState, PhaseOutput, PhaseStatus, TestResult, MediatorVerdict,
)
from src.llm.routing_engine import RoutingEngine
from src.llm.cli_runner import invoke as cli_invoke
from src.llm.prompt_builder import build_prompt
from src.llm.response_parser import extract_json, AgentResponse, MediatorResponse
from src.llm.providers import get_env_for_provider
from src.execution.git_manager import auto_commit, get_diff, get_diff_stat, get_modified_files
from src.execution.test_runner import run_tests, get_test_command, TestResult as TRTestResult
from src.agents.mediator_agent import should_trigger, MediatorAgent, save_intervention

logger = logging.getLogger(__name__)

MAX_PHASE_RETRIES = 10
CHECK_RETRY_LIMIT = 3  # Max retries for test check loops before moving on
VERIFY_RETRY_LIMIT = 3  # Max VERIFY→CODE cycles before accepting and moving to LEARN

# Thread pool for running async code from synchronous LangGraph nodes.
# LangGraph's graph.invoke() is synchronous, but our CLI runner is async.
# We bridge with a dedicated thread that runs its own event loop.
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _run_async(coro):
    """Run an async coroutine from a synchronous context safely.

    Uses a dedicated thread with a fresh event loop to avoid the
    'RuntimeError: This event loop is already running' issue that
    occurs when calling asyncio.get_event_loop().run_until_complete()
    from within an already-running event loop (e.g., story_executor).
    """
    def _run():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    future = _thread_pool.submit(_run)
    return future.result(timeout=660)  # 11 minutes max (10min CLI timeout + buffer)


# --- Node Factories ---

def phase_node(
    state: StoryState,
    phase_name: str,
    agent_name: str,
    routing_engine: RoutingEngine,
) -> StoryState:
    """Generic LLM phase node. Builds prompt, invokes LLM, updates state."""
    state = dict(state)  # Copy for mutation
    state["current_phase"] = phase_name

    story = state["story"]
    working_dir = state["working_directory"]

    # Build context with progressive disclosure
    context = _build_phase_context(state, phase_name)

    # Route to the right model
    story_complexity = story.get("complexity", 5)
    is_code = phase_name in ("CODE", "FIX", "EXECUTE")
    provider = routing_engine.select(agent_name, story_complexity=story_complexity, is_code_task=is_code)
    logger.info(f"Phase {phase_name} ({agent_name}) → {provider.name} (story: {story.get('id', '?')})")

    # Build prompt
    prompt = build_prompt(
        story=story,
        phase=phase_name,
        working_directory=working_dir,
        context=context,
    )

    # Invoke LLM via thread-safe async bridge
    start_time = time.monotonic()
    result = None
    output_text = ""
    try:
        result = _run_async(
            cli_invoke(provider=provider, prompt=prompt, working_directory=working_dir)
        )
        duration = time.monotonic() - start_time
        output_text = result.stdout

        if result.is_api_error:
            status = PhaseStatus.FAILED
            state["failure_context"] = f"API error: {result.api_error_code}"
        elif result.exit_code != 0 and not output_text.strip():
            status = PhaseStatus.FAILED
            state["failure_context"] = f"CLI error: exit_code={result.exit_code}, stderr={result.stderr[:500]}"
        else:
            status = PhaseStatus.COMPLETE

            # Try to parse JSON response for structured output
            try:
                parsed = extract_json(output_text)
                if parsed.get("status") == "blocked":
                    status = PhaseStatus.FAILED
                    state["failure_context"] = parsed.get("output", "Blocked")
            except (ValueError, Exception):
                pass  # Not all phases return JSON

    except Exception as e:
        duration = time.monotonic() - start_time
        output_text = ""
        status = PhaseStatus.FAILED
        state["failure_context"] = str(e)
        logger.error(f"Phase {phase_name} failed: {e}")

    # Record phase output
    exit_code = result.exit_code if result is not None else -1
    phase_output = PhaseOutput(
        phase=phase_name,
        status=status,
        output=output_text,
        exit_code=exit_code,
        provider_used=provider.name,
        duration_seconds=duration,
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    # Update progressive disclosure context
    if phase_name == "DESIGN":
        state["design_output"] = output_text
    elif phase_name == "TDD_RED":
        state["test_files"] = output_text
    elif phase_name == "PLAN":
        state["plan_output"] = output_text

    # Update verify_passed for phases that feed into verify_decision
    if phase_name in ("VERIFY", "VERIFY_SCRIPT") and status == PhaseStatus.FAILED:
        state["verify_passed"] = False

    # Reset check retry counter when VERIFY completes (pass or fail).
    # Each VERIFY→CODE→CHECK cycle should get a fresh retry budget.
    if phase_name in ("VERIFY", "VERIFY_SCRIPT"):
        state["phase_retry_count"] = 0
        # Track VERIFY→CODE cycle count
        if status == PhaseStatus.FAILED:
            state["verify_retry_count"] = state.get("verify_retry_count", 0) + 1

    logger.info(f"Phase {phase_name} completed: status={status.value}, duration={duration:.1f}s, provider={provider.name}")

    # Auto-commit after code-producing phases
    if status == PhaseStatus.COMPLETE and phase_name in ("TDD_RED", "CODE", "FIX", "VERIFY", "EXECUTE"):
        commit_hash = auto_commit(working_dir, story.get("id", "unknown"), phase_name)
        if commit_hash:
            logger.debug(f"Auto-committed after {phase_name}: {commit_hash}")

    return state


def test_check_node(
    state: StoryState,
    phase_name: str,
    expect_failure: bool = False,
) -> StoryState:
    """Automated test execution node (no LLM).

    For TDD_RED_CHECK: expects tests to FAIL (verifying test quality).
    For TDD_GREEN_CHECK: expects tests to PASS (verifying implementation).
    """
    state = dict(state)
    state["current_phase"] = phase_name

    story = state["story"]
    working_dir = state["working_directory"]

    test_cmd = get_test_command(story, working_dir)
    logger.info(f"Test check {phase_name}: running '{test_cmd}' (expect_failure={expect_failure})")
    result = run_tests(working_dir, test_cmd)
    logger.info(f"Test check {phase_name}: passed={result.passed}, total={result.total}, failures={result.failures}")

    test_result = TestResult(
        passed=result.passed,
        total=result.total,
        failures=result.failures,
        output=result.output[:2000],
        exit_code=result.exit_code,
        framework=result.framework,
    )
    state["test_results"] = test_result.model_dump()

    if expect_failure:
        # TDD_RED_CHECK: tests should FAIL
        state["verify_passed"] = not result.passed
        if result.passed:
            state["failure_context"] = (
                "TDD_RED_CHECK: Tests passed but should have failed. "
                "The tests are not testing new behavior. "
                f"Output: {result.output[:500]}"
            )
    else:
        # TDD_GREEN_CHECK: tests should PASS
        state["verify_passed"] = result.passed
        if not result.passed:
            state["failure_context"] = (
                f"TDD_GREEN_CHECK: Tests failed.\n"
                f"Failures: {result.failures}/{result.total}\n"
                f"Output: {result.output[:1000]}"
            )

    status = PhaseStatus.COMPLETE if state["verify_passed"] else PhaseStatus.FAILED

    # Increment retry counter when check fails (used by check_test_decision to break loops)
    if not state["verify_passed"]:
        state["phase_retry_count"] = state.get("phase_retry_count", 0) + 1
        logger.info(f"Test check {phase_name}: retry count now {state['phase_retry_count']}/{CHECK_RETRY_LIMIT}")

    phase_output = PhaseOutput(
        phase=phase_name,
        status=status,
        output=result.output[:2000],
        exit_code=result.exit_code,
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    return state


def mediator_gate_node(
    state: StoryState,
    routing_engine: RoutingEngine,
) -> StoryState:
    """Optional mediator review after code-producing phases."""
    state = dict(state)

    if not state.get("mediator_enabled", False):
        state["mediator_verdict"] = MediatorVerdict(decision="ACCEPT", reasoning="Mediator disabled").model_dump()
        return state

    working_dir = state["working_directory"]
    story = state["story"]
    current_phase = state["current_phase"]

    # Check if mediator should trigger
    modified = get_modified_files(working_dir)
    trigger = should_trigger(current_phase, modified)

    if not trigger["should_trigger"]:
        state["mediator_verdict"] = MediatorVerdict(decision="ACCEPT", reasoning=trigger["reason"]).model_dump()
        return state

    # Get diffs for review
    diff_stat = get_diff_stat(working_dir)
    diff = get_diff(working_dir)

    # Invoke mediator via thread-safe async bridge
    mediator = MediatorAgent(routing_engine=routing_engine)
    try:
        result = _run_async(
            mediator.review(
                story=story,
                phase=current_phase,
                working_directory=working_dir,
                changes_summary=diff_stat,
                changes_diff=diff,
                test_results_before=None,
                test_results_after=state.get("test_results"),
            )
        )

        state["mediator_verdict"] = MediatorVerdict(
            decision=result.decision.value,
            confidence=result.confidence,
            reasoning=result.reasoning,
            retry_guidance=result.retryGuidance,
        ).model_dump()

        # Track intervention
        task_path = os.path.dirname(working_dir) if working_dir else "."
        save_intervention(
            task_path=task_path,
            story_id=story.get("id", "unknown"),
            phase=current_phase,
            violation=trigger.get("violation", "unknown"),
            decision=result.decision.value,
            files_involved=modified,
        )

    except Exception as e:
        logger.warning(f"Mediator failed: {e} — auto-accepting")
        state["mediator_verdict"] = MediatorVerdict(decision="ACCEPT", reasoning=f"Error: {e}").model_dump()

    return state


# --- Decision Functions ---

def verify_decision(state: StoryState) -> Literal["pass", "fail"]:
    """Route after VERIFY: pass → LEARN, fail → CODE."""
    if state.get("verify_passed", True):
        return "pass"
    # Limit VERIFY→CODE cycles to avoid infinite loops
    verify_retries = state.get("verify_retry_count", 0)
    if verify_retries >= VERIFY_RETRY_LIMIT:
        logger.warning(f"VERIFY failed {verify_retries} times, accepting and moving to LEARN")
        return "pass"
    return "fail"


def check_test_decision(state: StoryState) -> Literal["pass", "fail"]:
    """Route after test check nodes."""
    if state.get("verify_passed", True):
        return "pass"
    # Check retry limit (3 retries for checks, not the full MAX_PHASE_RETRIES)
    retry_count = state.get("phase_retry_count", 0)
    if retry_count >= CHECK_RETRY_LIMIT:
        logger.warning(f"Check failed {retry_count} times, moving on")
        return "pass"  # Give up on retrying, continue to next phase
    return "fail"


def mediator_decision(state: StoryState) -> Literal["accept", "retry"]:
    """Route after mediator: accept → continue, retry → loop back."""
    verdict = state.get("mediator_verdict", {})
    decision = verdict.get("decision", "ACCEPT")

    if decision in ("ACCEPT", "PARTIAL"):
        return "accept"
    return "retry"  # REVERT and RETRY both loop back


# --- Context Builder ---

def _build_phase_context(state: StoryState, phase_name: str) -> dict:
    """Build context dict for a phase using progressive disclosure rules."""
    ctx = {}

    story = state.get("story", {})
    ctx["acceptance_criteria"] = story.get("acceptanceCriteria", [])
    ctx["task_description"] = state.get("task_description", "")

    if state.get("design_output"):
        ctx["design_output"] = state["design_output"]

    if state.get("test_files"):
        ctx["test_files"] = state["test_files"]

    if state.get("plan_output"):
        ctx["plan_output"] = state["plan_output"]

    if state.get("failure_context"):
        ctx["failure_context"] = state["failure_context"]

    # Add diff for VERIFY phases
    if phase_name in ("VERIFY", "VERIFY_SCRIPT"):
        working_dir = state.get("working_directory", ".")
        try:
            ctx["diff"] = get_diff(working_dir)
        except Exception:
            ctx["diff"] = ""

        if state.get("test_results"):
            ctx["test_results"] = str(state["test_results"])

    return ctx


# --- Base Workflow Class ---

class BaseWorkflow(ABC):
    """Abstract base for all LangGraph workflows.

    Subclasses declare phases and edges via define_graph().
    The base class handles graph compilation and common patterns.
    """

    def __init__(self, routing_engine: Optional[RoutingEngine] = None):
        self.routing_engine = routing_engine or RoutingEngine()

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """Build and return the compiled LangGraph StateGraph.

        Subclasses implement this to define their specific phase topology.
        Use the factory functions (phase_node, test_check_node, etc.) to create nodes.
        """
        ...

    def compile(self):
        """Compile the workflow graph."""
        return self.build_graph().compile()
