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
from typing import Literal

from langgraph.graph import StateGraph

from src.agents.mediator_agent import MediatorAgent, categorize_files, save_intervention, should_trigger
from src.execution.git_manager import auto_commit, get_diff, get_diff_stat, get_modified_files
from src.execution.intent_verifier import IntentVerifier
from src.execution.test_runner import get_test_command, run_tests
from src.execution.verification_sdk import ConfigValidator
from src.llm.cli_runner import invoke as cli_invoke
from src.llm.prompt_builder import build_prompt
from src.llm.response_parser import MediatorResponse, extract_json
from src.llm.routing_engine import RoutingEngine
from src.workflows.state import (
    MediatorVerdict,
    PhaseOutput,
    PhaseStatus,
    StoryState,
    TestResult,
)

logger = logging.getLogger(__name__)

# Enhancement collection file — agents log non-critical improvements here
ENHANCEMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".memory")


def _collect_enhancements(story_id: str, phase: str, enhancements, working_dir: str):
    """Collect enhancements_noted from agent output to .memory/enhancements.jsonl.

    These are non-critical improvement ideas logged by agents following the
    TACHES deviation rules (rule 4/5). Viewable via monitoring tool.
    """
    import json as _json
    from datetime import datetime as _dt

    target = os.path.join(ENHANCEMENTS_DIR, "enhancements.jsonl")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    items = enhancements if isinstance(enhancements, list) else [str(enhancements)]
    try:
        with open(target, "a", encoding="utf-8") as f:
            for item in items:
                entry = {
                    "ts": _dt.now().isoformat(),
                    "story_id": story_id,
                    "phase": phase,
                    "enhancement": str(item)[:500],
                }
                f.write(_json.dumps(entry, separators=(",", ":")) + "\n")
        logger.info(f"Collected {len(items)} enhancement(s) from {phase}/{story_id}")
    except Exception as e:
        logger.debug(f"Failed to collect enhancements: {e}")


# Directory for streaming LLM output to disk (enables partial recovery on timeout)
STREAM_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".memory", "streams"
)

MAX_PHASE_RETRIES = 10
CHECK_RETRY_LIMIT = 3  # Max retries for test check loops before moving on
VERIFY_RETRY_LIMIT = 3  # Max VERIFY→CODE cycles before accepting and moving to LEARN

# Per-phase wall-clock timeouts (seconds).
# These cap the TOTAL time a phase can run, independent of per-API-call timeouts.
# Test/check phases get short timeouts (tests should NOT take 30 minutes).
PHASE_WALL_CLOCK_TIMEOUTS = {
    # Test/check phases — 5 minutes max
    "TDD_RED_CHECK": 300,
    "TDD_GREEN_CHECK": 300,
    "VERIFY": 300,
    "VERIFY_SCRIPT": 300,
    "VERIFY_LINT": 300,
    "VERIFY_TEST": 300,
    "VERIFY_SECURITY": 300,
    "VERIFY_ARCH": 300,
    "PARALLEL_VERIFY": 300,
    "CONFIG_VALIDATE": 300,
    "DEPENDENCY_CHECK": 300,
    # Code-producing phases — 15 minutes max
    "ARCHITECT_CODE": 900,
    "CODE": 900,
    "TEST_WRITER": 900,
    "TDD_RED": 900,
    "FIX": 900,
    "EXECUTE": 900,
    "PLAN_CODE": 900,
    # Content-producing phases — 15 minutes max (long documents)
    "CONTENT_WRITE": 900,
}
# Default for phases not listed above: 10 minutes
DEFAULT_PHASE_TIMEOUT = 600


def get_phase_timeout(phase_name: str) -> int:
    """Return wall-clock timeout in seconds for a given phase."""
    return PHASE_WALL_CLOCK_TIMEOUTS.get(phase_name, DEFAULT_PHASE_TIMEOUT)


# Thread pool for running async code from synchronous LangGraph nodes.
# LangGraph's graph.invoke() is synchronous, but our CLI runner is async.
# We bridge with a dedicated thread that runs its own event loop.
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _run_async(coro, timeout: int = 660):
    """Run an async coroutine from a synchronous context safely.

    Uses a dedicated thread with a fresh event loop to avoid the
    'RuntimeError: This event loop is already running' issue that
    occurs when calling asyncio.get_event_loop().run_until_complete()
    from within an already-running event loop (e.g., story_executor).

    Args:
        coro: The async coroutine to run.
        timeout: Wall-clock timeout in seconds. Defaults to 660 (11 min).
    """

    def _run():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    future = _thread_pool.submit(_run)
    return future.result(timeout=timeout)


def _stream_file_path(story_id: str, phase: str) -> str:
    """Return a stream output file path for incremental LLM output capture.

    Creates the streams directory if it doesn't exist.
    """
    os.makedirs(STREAM_DIR, exist_ok=True)
    # Sanitize story_id for filename safety
    safe_id = str(story_id).replace("/", "_").replace(" ", "_")
    return os.path.join(STREAM_DIR, f"sat-stream-{safe_id}-{phase}.txt")


def _revert_files(working_directory: str, files: list[str]) -> list[str]:
    """Revert specific files using git checkout HEAD -- <file>.

    Returns list of successfully reverted files.
    """
    import subprocess

    reverted = []
    for filepath in files:
        try:
            result = subprocess.run(
                ["git", "checkout", "HEAD", "--", filepath],
                cwd=working_directory,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                reverted.append(filepath)
                logger.info(f"Reverted file: {filepath}")
            else:
                logger.warning(f"Failed to revert {filepath}: {result.stderr}")
        except Exception as e:
            logger.warning(f"Error reverting {filepath}: {e}")
    return reverted


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

    # Set hierarchical correlation context for this phase
    try:
        from src.logging_config import set_phase_context

        set_phase_context(phase_name)
    except Exception:
        pass

    story = state["story"]
    working_dir = state["working_directory"]

    # Build context with progressive disclosure
    context = _build_phase_context(state, phase_name)

    # Route to the right model
    story_complexity = story.get("complexity", 5)
    story_type = story.get("type", "development")
    is_code = phase_name in ("CODE", "FIX", "EXECUTE")
    provider = routing_engine.select(
        agent_name,
        story_complexity=story_complexity,
        is_code_task=is_code,
        story_type=story_type,
    )
    logger.info(f"Phase {phase_name} ({agent_name}) → {provider.name} (story: {story.get('id', '?')})")

    # Build prompt
    prompt = build_prompt(
        story=story,
        phase=phase_name,
        working_directory=working_dir,
        context=context,
    )

    # Invoke LLM via thread-safe async bridge
    phase_timeout = get_phase_timeout(phase_name)
    story_id = story.get("id", "unknown")
    stream_file = _stream_file_path(story_id, phase_name)
    start_time = time.monotonic()
    result = None
    output_text = ""
    try:
        result = _run_async(
            cli_invoke(
                provider=provider,
                prompt=prompt,
                working_directory=working_dir,
                stream_output_file=stream_file,
            ),
            timeout=phase_timeout,
        )
        duration = time.monotonic() - start_time
        output_text = result.stdout

        if result.is_api_error:
            status = PhaseStatus.FAILED
            state["failure_context"] = f"API error: {result.api_error_code}"
            # Mark provider as rate-limited on 429 so routing picks a different one
            if result.api_error_code == 429:
                routing_engine.mark_rate_limited(provider.name)
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

                # Collect enhancements_noted from agent output
                enhancements = parsed.get("enhancements_noted")
                if enhancements:
                    _collect_enhancements(
                        story.get("id", "unknown"),
                        phase_name,
                        enhancements,
                        working_dir,
                    )

                # Collect architecture_change_proposed from debug agents
                arch_change = parsed.get("architecture_change_proposed")
                if arch_change:
                    _collect_enhancements(
                        story.get("id", "unknown"),
                        phase_name,
                        [f"ARCHITECTURE CHANGE PROPOSED: {arch_change}"],
                        working_dir,
                    )

                # Collect agent self-assessment confidence
                confidence = parsed.get("confidence")
                if confidence is not None:
                    state["agent_self_confidence"] = confidence
            except (ValueError, Exception):
                pass  # Not all phases return JSON

    except (concurrent.futures.TimeoutError, TimeoutError):
        duration = time.monotonic() - start_time
        # Try to recover partial output from stream file
        output_text = ""
        try:
            if os.path.exists(stream_file):
                with open(stream_file, encoding="utf-8") as f:
                    output_text = f.read()
                if output_text:
                    logger.info(
                        f"WATCHDOG: Recovered {len(output_text)} chars of partial output "
                        f"from stream file for phase {phase_name}"
                    )
        except Exception:
            pass
        status = PhaseStatus.FAILED
        state["failure_context"] = (
            f"WATCHDOG: Phase {phase_name} killed after {phase_timeout}s wall-clock timeout "
            f"(elapsed {duration:.0f}s). Subprocess hung."
            + (f" Partial output recovered ({len(output_text)} chars)." if output_text else "")
        )
        logger.error(
            f"WATCHDOG TIMEOUT: Phase {phase_name} exceeded {phase_timeout}s wall-clock limit "
            f"(elapsed {duration:.0f}s) — killing subprocess"
        )

    except Exception as e:
        duration = time.monotonic() - start_time
        output_text = ""
        status = PhaseStatus.FAILED
        state["failure_context"] = str(e)
        logger.error(f"Phase {phase_name} failed: {e}")

    # Log structured event for G-Eval scoring (Enhancement #11)
    try:
        from src.llm.prompt_builder import get_template_version
        from src.logging_config import log_event

        log_event(
            "llm_invocation",
            "base_workflow",
            {
                "provider": provider.name,
                "agent_type": agent_name,
                "phase": phase_name,
                "story_id": story.get("id", "unknown"),
                "duration": round(duration, 1),
                "status": status.value,
                "output_preview": output_text[:2000] if output_text else "",
                "template_version": get_template_version(phase_name),
                "agent_confidence": state.get("agent_self_confidence"),
            },
        )
    except Exception:
        pass  # Best-effort

    # Record invocation in performance tracker for historical routing advice
    if hasattr(routing_engine, "_perf_tracker") and routing_engine._perf_tracker:
        try:
            tokens = 0
            if result is not None:
                # Approximate tokens from output length (actual parsing in cli_runner)
                tokens = len(output_text) // 4 if output_text else 0
            quality = state.get("agent_self_confidence")
            routing_engine._perf_tracker.record_invocation(
                provider=provider.name,
                agent=agent_name,
                story_type=story_type,
                success=(status == PhaseStatus.COMPLETE),
                quality_score=quality,
                tokens=tokens,
                duration_seconds=duration,
            )
        except Exception as e:
            logger.debug(f"Performance tracking failed: {e}")

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
    if phase_name in ("DESIGN", "ARCHITECT_CODE", "ANALYZE", "SYNTHESIZE"):
        state["design_output"] = output_text
    elif phase_name in ("TDD_RED", "TEST_WRITER"):
        state["test_files"] = output_text
    elif phase_name in ("PLAN", "PLAN_CODE", "CONTENT_PLAN"):
        state["plan_output"] = output_text

    # Update verify_passed for VERIFY phases to feed verify_decision
    if phase_name in ("VERIFY", "VERIFY_SCRIPT"):
        state["verify_passed"] = status == PhaseStatus.COMPLETE
        logger.info(f"VERIFY phase setting verify_passed={state['verify_passed']} (status={status.value})")
        # Reset check retry counter — each VERIFY→CODE→CHECK cycle gets fresh budget
        state["phase_retry_count"] = 0
        # Track VERIFY→CODE cycle count when VERIFY fails
        if status == PhaseStatus.FAILED:
            state["verify_retry_count"] = state.get("verify_retry_count", 0) + 1

    logger.info(
        f"Phase {phase_name} completed: status={status.value}, duration={duration:.1f}s, provider={provider.name}"
    )

    # Auto-commit after phases that produce files
    if status == PhaseStatus.COMPLETE and phase_name in (
        "TDD_RED",
        "CODE",
        "FIX",
        "VERIFY",
        "EXECUTE",
        "CONTENT_WRITE",
    ):
        commit_hash = auto_commit(working_dir, story.get("id", "unknown"), phase_name)
        if commit_hash:
            logger.debug(f"Auto-committed after {phase_name}: {commit_hash}")

    # Route LEARN phase output to core memory files (Levels 1-3)
    if phase_name == "LEARN" and status == PhaseStatus.COMPLETE and output_text:
        try:
            from src.core.memory_writer import process_learn_output

            parsed_learn = extract_json(output_text)
            if isinstance(parsed_learn, dict):
                process_learn_output(parsed_learn, working_dir)
        except Exception as e:
            logger.debug(f"Could not route LEARN output to core memory: {e}")

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
    phase_timeout = get_phase_timeout(phase_name)
    logger.info(
        f"Test check {phase_name}: running '{test_cmd}' (expect_failure={expect_failure}, timeout={phase_timeout}s)"
    )
    result = run_tests(working_dir, test_cmd, timeout=phase_timeout)
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


def _invoke_mediator_review(
    mediator: MediatorAgent,
    story: dict,
    phase: str,
    working_dir: str,
    test_results: dict | None,
) -> MediatorResponse:
    """Call the Mediator Agent LLM to review changes. Returns MediatorResponse."""
    diff_stat = get_diff_stat(working_dir)
    diff = get_diff(working_dir)
    mediator_timeout = get_phase_timeout("MEDIATOR")
    return _run_async(
        mediator.review(
            story=story,
            phase=phase,
            working_directory=working_dir,
            changes_summary=diff_stat,
            changes_diff=diff,
            test_results_before=None,
            test_results_after=test_results,
        ),
        timeout=mediator_timeout,
    )


def mediator_gate_node(
    state: StoryState,
    routing_engine: RoutingEngine,
) -> StoryState:
    """Optional mediator review after code-producing phases.

    The smart trigger (should_trigger) is a DIFF SCRIPT — pure Python file
    categorization using git diff. It is NOT an LLM call. 90%+ of the time,
    no relevant file changes are detected and the mediator agent is never called.

    Phase-specific behavior when the trigger fires:

    TDD_RED violation (code files modified during test phase):
        Auto-revert the code files. No LLM call needed — this is an obvious
        violation. The mediator agent is never invoked.

    CODE/FIX violation (test files modified during code phase):
        Call the Mediator Agent LLM to review the test file changes and decide
        what to do.

    VERIFY violation (test OR code files modified):
        Categorize files and review each category separately via the Mediator
        Agent. If either category gets a REVERT verdict, those files are reverted.
    """
    state = dict(state)

    if not state.get("mediator_enabled", False):
        state["mediator_verdict"] = MediatorVerdict(decision="ACCEPT", reasoning="Mediator disabled").model_dump()
        return state

    working_dir = state["working_directory"]
    story = state["story"]
    current_phase = state["current_phase"]

    # Smart trigger: pure Python file categorization (no LLM call)
    modified = get_modified_files(working_dir)
    trigger = should_trigger(current_phase, modified)

    if not trigger["should_trigger"]:
        state["mediator_verdict"] = MediatorVerdict(decision="ACCEPT", reasoning=trigger["reason"]).model_dump()
        return state

    task_path = os.path.dirname(working_dir) if working_dir else "."
    story_id = story.get("id", "unknown")
    test_files, code_files = categorize_files(modified)

    # ---------------------------------------------------------------
    # Case 1: TDD_RED — code files modified during test-writing phase
    # Auto-revert. No LLM call needed — this is an obvious violation.
    # ---------------------------------------------------------------
    if current_phase == "TDD_RED":
        reverted = _revert_files(working_dir, code_files)
        reason = f"Auto-reverted code files modified during TDD_RED phase: {reverted}"
        logger.warning(reason)

        state["mediator_verdict"] = MediatorVerdict(
            decision="REVERT",
            reasoning=reason,
        ).model_dump()

        save_intervention(
            task_path=task_path,
            story_id=story_id,
            phase=current_phase,
            violation="code_in_test_phase",
            decision="REVERT",
            files_involved=code_files,
        )
        return state

    # ---------------------------------------------------------------
    # Case 2: CODE/FIX — test files modified during code phase
    # Call Mediator Agent to review the test changes.
    # ---------------------------------------------------------------
    if current_phase in ("CODE", "FIX"):
        mediator = MediatorAgent(routing_engine=routing_engine)
        try:
            result = _invoke_mediator_review(
                mediator,
                story,
                current_phase,
                working_dir,
                state.get("test_results"),
            )

            state["mediator_verdict"] = MediatorVerdict(
                decision=result.decision.value,
                confidence=result.confidence,
                reasoning=result.reasoning,
                retry_guidance=result.retryGuidance,
            ).model_dump()

            # If verdict is REVERT, revert the offending test files
            if result.decision.value == "REVERT":
                reverted = _revert_files(working_dir, test_files)
                logger.info(f"Mediator REVERT: reverted test files {reverted}")

            save_intervention(
                task_path=task_path,
                story_id=story_id,
                phase=current_phase,
                violation="test_in_code_phase",
                decision=result.decision.value,
                files_involved=test_files,
            )

        except Exception as e:
            logger.warning(f"Mediator failed: {e} — auto-accepting")
            state["mediator_verdict"] = MediatorVerdict(decision="ACCEPT", reasoning=f"Error: {e}").model_dump()

        return state

    # ---------------------------------------------------------------
    # Case 3: VERIFY — any files modified. Review each category
    # separately (test files vs code files). If either gets REVERT,
    # revert those specific files.
    # ---------------------------------------------------------------
    if current_phase == "VERIFY":
        mediator = MediatorAgent(routing_engine=routing_engine)
        combined_decision = "ACCEPT"
        combined_reasoning_parts = []
        combined_confidence = 1.0
        combined_retry_guidance = None

        # Review test files if any were modified
        if test_files:
            try:
                result = _invoke_mediator_review(
                    mediator,
                    story,
                    "VERIFY",
                    working_dir,
                    state.get("test_results"),
                )
                combined_reasoning_parts.append(
                    f"Test files ({test_files}): {result.decision.value} — {result.reasoning}"
                )
                combined_confidence = min(combined_confidence, result.confidence or 1.0)

                if result.decision.value == "REVERT":
                    combined_decision = "REVERT"
                    reverted = _revert_files(working_dir, test_files)
                    logger.info(f"Mediator REVERT (VERIFY/tests): reverted {reverted}")
                elif result.decision.value == "RETRY" and combined_decision != "REVERT":
                    combined_decision = "RETRY"
                    combined_retry_guidance = result.retryGuidance

                save_intervention(
                    task_path=task_path,
                    story_id=story_id,
                    phase="VERIFY",
                    violation="verify_test_changes",
                    decision=result.decision.value,
                    files_involved=test_files,
                )
            except Exception as e:
                logger.warning(f"Mediator failed reviewing test files: {e} — auto-accepting test changes")
                combined_reasoning_parts.append(f"Test files: auto-accepted (error: {e})")

        # Review code files if any were modified
        if code_files:
            try:
                result = _invoke_mediator_review(
                    mediator,
                    story,
                    "VERIFY",
                    working_dir,
                    state.get("test_results"),
                )
                combined_reasoning_parts.append(
                    f"Code files ({code_files}): {result.decision.value} — {result.reasoning}"
                )
                combined_confidence = min(combined_confidence, result.confidence or 1.0)

                if result.decision.value == "REVERT":
                    combined_decision = "REVERT"
                    reverted = _revert_files(working_dir, code_files)
                    logger.info(f"Mediator REVERT (VERIFY/code): reverted {reverted}")
                elif result.decision.value == "RETRY" and combined_decision != "REVERT":
                    combined_decision = "RETRY"
                    combined_retry_guidance = result.retryGuidance

                save_intervention(
                    task_path=task_path,
                    story_id=story_id,
                    phase="VERIFY",
                    violation="verify_code_changes",
                    decision=result.decision.value,
                    files_involved=code_files,
                )
            except Exception as e:
                logger.warning(f"Mediator failed reviewing code files: {e} — auto-accepting code changes")
                combined_reasoning_parts.append(f"Code files: auto-accepted (error: {e})")

        state["mediator_verdict"] = MediatorVerdict(
            decision=combined_decision,
            confidence=combined_confidence,
            reasoning="; ".join(combined_reasoning_parts) if combined_reasoning_parts else "No files to review",
            retry_guidance=combined_retry_guidance,
        ).model_dump()

        return state

    # Fallback: unknown phase that somehow triggered — auto-accept
    logger.warning(f"Mediator gate: unexpected phase {current_phase} triggered, auto-accepting")
    state["mediator_verdict"] = MediatorVerdict(
        decision="ACCEPT", reasoning=f"Unexpected phase: {current_phase}"
    ).model_dump()
    return state


# --- Enhanced Node Factories (Phase 3) ---


def parallel_verify_node(
    state: StoryState,
    routing_engine: RoutingEngine,
) -> StoryState:
    """Run 4 verification checks in parallel and merge results.

    Checks: linter, test_runner (automated), security, arch_review.
    Each check is an LLM call with a specialized prompt. Results are
    synthesized into a single verify verdict stored in verify_check_results.
    """
    state = dict(state)
    state["current_phase"] = "PARALLEL_VERIFY"

    story = state["story"]
    working_dir = state["working_directory"]
    story_complexity = story.get("complexity", 5)
    story_id = story.get("id", "unknown")

    check_agents = [
        ("linter", "VERIFY_LINT"),
        ("test_runner", "VERIFY_TEST"),
        ("security_checker", "VERIFY_SECURITY"),
        ("arch_reviewer", "VERIFY_ARCH"),
    ]

    results = {}
    futures = {}

    # Submit all 4 checks in parallel using thread pool
    for agent_name, check_phase in check_agents:
        provider = routing_engine.select(agent_name, story_complexity=story_complexity, is_code_task=False)
        context = _build_phase_context(state, "VERIFY")
        prompt = build_prompt(
            story=story,
            phase=check_phase,
            working_directory=working_dir,
            context=context,
        )
        stream_file = _stream_file_path(story_id, check_phase)

        def _make_check(p, pr, wd, t, sf):
            return _run_async(cli_invoke(provider=p, prompt=pr, working_directory=wd, stream_output_file=sf), timeout=t)

        check_timeout = get_phase_timeout(check_phase)
        future = _thread_pool.submit(_make_check, provider, prompt, working_dir, check_timeout, stream_file)
        futures[agent_name] = (future, provider.name, check_timeout)

    # Collect results — use per-check wall-clock timeout
    all_passed = True
    failure_reasons = []
    for agent_name, (future, provider_name, check_timeout) in futures.items():
        try:
            result = future.result(timeout=check_timeout + 30)
            output_text = result.stdout if result else ""
            check_passed = result.exit_code == 0 if result else False

            # Try to parse structured response
            try:
                parsed = extract_json(output_text)
                if parsed.get("status") == "blocked" or parsed.get("passed") is False:
                    check_passed = False
            except (ValueError, Exception):
                pass

            results[agent_name] = {
                "passed": check_passed,
                "output": output_text[:1000],
                "provider": provider_name,
            }
            if not check_passed:
                all_passed = False
                failure_reasons.append(f"{agent_name}: {output_text[:200]}")

        except (concurrent.futures.TimeoutError, TimeoutError):
            logger.error(f"WATCHDOG TIMEOUT: Parallel verify check {agent_name} exceeded {check_timeout}s — killing")
            future.cancel()
            results[agent_name] = {
                "passed": False,
                "output": f"WATCHDOG: killed after {check_timeout}s timeout",
                "provider": provider_name,
            }
            all_passed = False
            failure_reasons.append(f"{agent_name}: WATCHDOG timeout after {check_timeout}s")

        except Exception as e:
            logger.error(f"Parallel verify check {agent_name} failed: {e}")
            results[agent_name] = {
                "passed": False,
                "output": str(e)[:500],
                "provider": provider_name,
            }
            all_passed = False
            failure_reasons.append(f"{agent_name}: error — {e}")

    # --- Intent verification (pure Python, no LLM) ---
    try:
        intent_verifier = IntentVerifier()
        diff_text = get_diff(working_dir)
        modified = get_modified_files(working_dir)
        ac_list = story.get("acceptanceCriteria", [])
        description = story.get("description", story.get("title", ""))

        intent_result = intent_verifier.verify_intent(
            story_description=description,
            acceptance_criteria=ac_list,
            diff_text=diff_text,
            modified_files=modified,
        )

        results["intent_verifier"] = {
            "passed": intent_result.aligned,
            "output": "; ".join(intent_result.issues) if intent_result.issues else "Intent aligned",
            "provider": "heuristic",
            "confidence": intent_result.confidence,
        }

        if not intent_result.aligned:
            all_passed = False
            failure_reasons.append(f"intent_verifier: {'; '.join(intent_result.issues)}")

        # Log scope warnings (non-blocking)
        if intent_result.scope_warnings:
            logger.warning(f"Intent scope warnings for {story_id}: {intent_result.scope_warnings}")

    except Exception as e:
        logger.warning(f"Intent verification failed (non-fatal): {e}")
        results["intent_verifier"] = {
            "passed": True,
            "output": f"Skipped due to error: {e}",
            "provider": "heuristic",
        }

    # Synthesize results
    state["verify_check_results"] = results
    state["verify_passed"] = all_passed

    if not all_passed:
        state["failure_context"] = (
            f"Parallel verification failed. {len(failure_reasons)} check(s) failed:\n" + "\n".join(failure_reasons)
        )
        # Track verify retry count
        state["verify_retry_count"] = state.get("verify_retry_count", 0) + 1

    status = PhaseStatus.COMPLETE if all_passed else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="PARALLEL_VERIFY",
        status=status,
        output=f"Checks: {len(results)}, Passed: {sum(1 for r in results.values() if r['passed'])}/{len(results)}",
        exit_code=0 if all_passed else 1,
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    # Reset check retry counter for any subsequent loops
    state["phase_retry_count"] = 0

    logger.info(f"Parallel verify: {sum(1 for r in results.values() if r['passed'])}/{len(results)} checks passed")
    return state


def config_validate_node(
    state: StoryState,
) -> StoryState:
    """Validate config file syntax using the VerificationSDK ConfigValidator.

    Runs after EXECUTE in config workflows to catch syntax errors before
    the heavier VERIFY_SCRIPT phase. Checks JSON, YAML, INI, and env files
    found in the working directory's recent changes.
    """
    state = dict(state)
    state["current_phase"] = "CONFIG_VALIDATE"

    working_dir = state["working_directory"]
    validator = ConfigValidator()

    # Detect config files from git changes
    modified = get_modified_files(working_dir)
    config_extensions = {
        ".json": validator.check_json,
        ".yaml": validator.check_yaml,
        ".yml": validator.check_yaml,
        ".ini": validator.check_ini,
        ".env": validator.check_env_file,
        ".conf": validator.check_ini,  # best-effort INI parse
    }

    check_results = []
    all_passed = True
    for filepath in modified:
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        if ext in config_extensions:
            full_path = os.path.join(working_dir, filepath) if not os.path.isabs(filepath) else filepath
            result = config_extensions[ext](full_path)
            check_results.append(
                {
                    "file": filepath,
                    "passed": result.passed,
                    "message": result.message,
                }
            )
            if not result.passed:
                all_passed = False

    # If no config files found, pass through
    if not check_results:
        logger.info("CONFIG_VALIDATE: no config files in changes, skipping")
        state["config_validation_result"] = {"skipped": True, "reason": "no config files modified"}
        state["verify_passed"] = True
    else:
        state["config_validation_result"] = {
            "checks": check_results,
            "all_passed": all_passed,
        }
        state["verify_passed"] = all_passed
        if not all_passed:
            failed = [c for c in check_results if not c["passed"]]
            state["failure_context"] = f"Config validation failed for {len(failed)} file(s): " + "; ".join(
                f"{c['file']}: {c['message']}" for c in failed
            )

    status = PhaseStatus.COMPLETE if state["verify_passed"] else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="CONFIG_VALIDATE",
        status=status,
        output=f"Validated {len(check_results)} config file(s), all_passed={all_passed}"
        if check_results
        else "No config files to validate",
        exit_code=0 if state["verify_passed"] else 1,
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    logger.info(f"CONFIG_VALIDATE: {len(check_results)} files checked, all_passed={all_passed}")
    return state


def dependency_check_node(
    state: StoryState,
    routing_engine: RoutingEngine,
) -> StoryState:
    """Verify that maintenance changes don't break related components.

    After EXECUTE in maintenance workflows, this node asks an LLM to review
    the changes and identify any dependency or compatibility issues.
    """
    state = dict(state)
    state["current_phase"] = "DEPENDENCY_CHECK"

    story = state["story"]
    working_dir = state["working_directory"]
    story_complexity = story.get("complexity", 5)

    # Get diff of what changed
    diff = get_diff(working_dir)
    diff_stat = get_diff_stat(working_dir)

    if not diff.strip():
        logger.info("DEPENDENCY_CHECK: no changes detected, skipping")
        state["dependency_check_result"] = {"skipped": True, "reason": "no changes"}
        state["verify_passed"] = True
        phase_output = PhaseOutput(
            phase="DEPENDENCY_CHECK",
            status=PhaseStatus.COMPLETE,
            output="No changes to check",
            exit_code=0,
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    # Build context with diff info
    context = _build_phase_context(state, "VERIFY")
    context["diff"] = diff
    context["diff_stat"] = diff_stat

    provider = routing_engine.select("dependency_checker", story_complexity=story_complexity, is_code_task=False)

    prompt = build_prompt(
        story=story,
        phase="DEPENDENCY_CHECK",
        working_directory=working_dir,
        context=context,
    )

    story_id = story.get("id", "unknown")
    stream_file = _stream_file_path(story_id, "DEPENDENCY_CHECK")
    dep_timeout = get_phase_timeout("DEPENDENCY_CHECK")
    try:
        result = _run_async(
            cli_invoke(provider=provider, prompt=prompt, working_directory=working_dir, stream_output_file=stream_file),
            timeout=dep_timeout,
        )
        output_text = result.stdout if result else ""
        check_passed = True

        # Try to parse structured response
        try:
            parsed = extract_json(output_text)
            if parsed.get("status") == "blocked" or parsed.get("dependencies_broken"):
                check_passed = False
        except (ValueError, Exception):
            pass

        state["dependency_check_result"] = {
            "passed": check_passed,
            "output": output_text[:2000],
            "provider": provider.name,
        }
        state["verify_passed"] = check_passed

        if not check_passed:
            state["failure_context"] = f"Dependency check failed: {output_text[:500]}"

    except Exception as e:
        logger.error(f"DEPENDENCY_CHECK failed: {e}")
        state["dependency_check_result"] = {"passed": False, "error": str(e)}
        state["verify_passed"] = False
        state["failure_context"] = f"Dependency check error: {e}"
        output_text = str(e)

    status = PhaseStatus.COMPLETE if state.get("verify_passed", False) else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="DEPENDENCY_CHECK",
        status=status,
        output=output_text[:2000] if "output_text" in dir() else "",
        exit_code=0 if state.get("verify_passed", False) else 1,
        provider_used=provider.name,
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    logger.info(f"DEPENDENCY_CHECK: passed={state.get('verify_passed', False)}")
    return state


def parallel_gather_node(
    state: StoryState,
    routing_engine: RoutingEngine,
) -> StoryState:
    """Run 3 parallel gather channels for research workflows.

    Channels:
    - gather_web: web/documentation research
    - gather_code: code analysis
    - gather_docs: documentation review

    Results are merged into gather_results before ANALYZE.
    """
    state = dict(state)
    state["current_phase"] = "PARALLEL_GATHER"

    story = state["story"]
    working_dir = state["working_directory"]
    story_complexity = story.get("complexity", 5)
    story_id = story.get("id", "unknown")

    gather_channels = [
        ("gatherer_web", "GATHER_WEB"),
        ("gatherer_code", "GATHER_CODE"),
        ("gatherer_docs", "GATHER_DOCS"),
    ]

    results = {}
    futures = {}

    for agent_name, gather_phase in gather_channels:
        provider = routing_engine.select(agent_name, story_complexity=story_complexity, is_code_task=False)
        context = _build_phase_context(state, "GATHER")
        prompt = build_prompt(
            story=story,
            phase=gather_phase,
            working_directory=working_dir,
            context=context,
        )
        stream_file = _stream_file_path(story_id, gather_phase)

        gather_timeout = get_phase_timeout(gather_phase)

        def _make_gather(p, pr, wd, t, sf):
            return _run_async(cli_invoke(provider=p, prompt=pr, working_directory=wd, stream_output_file=sf), timeout=t)

        future = _thread_pool.submit(_make_gather, provider, prompt, working_dir, gather_timeout, stream_file)
        futures[agent_name] = (future, provider.name, gather_timeout)

    # Collect results
    all_outputs = []
    for agent_name, (future, provider_name, gather_timeout) in futures.items():
        try:
            result = future.result(timeout=gather_timeout + 30)
            output_text = result.stdout if result else ""
            results[agent_name] = {
                "output": output_text[:3000],
                "provider": provider_name,
                "exit_code": result.exit_code if result else -1,
            }
            all_outputs.append(f"=== {agent_name} ===\n{output_text[:2000]}")
        except (concurrent.futures.TimeoutError, TimeoutError):
            logger.error(f"WATCHDOG TIMEOUT: Parallel gather channel {agent_name} exceeded {gather_timeout}s — killing")
            future.cancel()
            results[agent_name] = {
                "output": f"WATCHDOG: killed after {gather_timeout}s timeout",
                "provider": provider_name,
                "exit_code": -1,
            }
            all_outputs.append(f"=== {agent_name} ===\nWATCHDOG: killed after {gather_timeout}s")
        except Exception as e:
            logger.error(f"Parallel gather channel {agent_name} failed: {e}")
            results[agent_name] = {
                "output": f"Error: {e}",
                "provider": provider_name,
                "exit_code": -1,
            }
            all_outputs.append(f"=== {agent_name} ===\nError: {e}")

    # Merge into state
    state["gather_results"] = results
    # Also put merged output into design_output for downstream consumption
    merged_output = "\n\n".join(all_outputs)
    state["design_output"] = merged_output

    phase_output = PhaseOutput(
        phase="PARALLEL_GATHER",
        status=PhaseStatus.COMPLETE,
        output=f"Gathered from {len(results)} channels",
        exit_code=0,
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    logger.info(f"PARALLEL_GATHER: {len(results)} channels completed")
    return state


def parallel_analyze_node(
    state: StoryState,
    routing_engine: RoutingEngine,
) -> StoryState:
    """Run parallel ANALYZE channels — one per topic extracted from gather output.

    Splits the gathered information into topics, runs concurrent analysis on each,
    then merges all analysis results into design_output for SYNTHESIZE.

    Topic extraction is lightweight (string splitting on gather channel headers).
    Each topic gets its own ANALYZE invocation with a focused subset of the data.
    """
    state = dict(state)
    state["current_phase"] = "PARALLEL_ANALYZE"

    story = state["story"]
    working_dir = state["working_directory"]
    story_complexity = story.get("complexity", 5)
    story_id = story.get("id", "unknown")

    # Get gathered information from prior phase
    gather_output = state.get("design_output", "")
    if not gather_output:
        logger.warning(f"Story {story_id}: No gather output for parallel analyze")
        phase_output = PhaseOutput(
            phase="PARALLEL_ANALYZE",
            status=PhaseStatus.FAILED,
            output="No gather output available",
            exit_code=-1,
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    # Split gather output into topic chunks by channel headers (=== gatherer_xxx ===)
    # or by section headers (# / ## / ### headings)
    topics = _split_into_topics(gather_output)
    if len(topics) <= 1:
        # Not enough to parallelize — fall through to single ANALYZE
        logger.info(f"Story {story_id}: Only {len(topics)} topic(s), using single ANALYZE")
        topics = [("full_analysis", gather_output)]

    logger.info(f"PARALLEL_ANALYZE: Splitting into {len(topics)} topic channels for story {story_id}")

    analyze_timeout = get_phase_timeout("ANALYZE")
    futures = {}

    for topic_name, topic_content in topics:
        provider = routing_engine.select("analyzer", story_complexity=story_complexity, is_code_task=False)

        # Build a focused prompt with just this topic's content
        topic_story = dict(story)
        topic_story["_analyze_topic"] = topic_name

        context = _build_phase_context(state, "ANALYZE")
        # Override design_output with just this topic's content
        context["design_output"] = topic_content

        prompt = build_prompt(
            story=topic_story,
            phase="ANALYZE",
            working_directory=working_dir,
            context=context,
        )
        stream_file = _stream_file_path(story_id, f"ANALYZE_{topic_name}")

        def _make_analyze(p, pr, wd, t, sf):
            return _run_async(cli_invoke(provider=p, prompt=pr, working_directory=wd, stream_output_file=sf), timeout=t)

        future = _thread_pool.submit(_make_analyze, provider, prompt, working_dir, analyze_timeout, stream_file)
        futures[topic_name] = (future, provider.name)

    # Collect results
    all_outputs = []
    for topic_name, (future, provider_name) in futures.items():
        try:
            result = future.result(timeout=analyze_timeout + 30)
            output_text = result.stdout if result else ""
            all_outputs.append(f"=== Analysis: {topic_name} ===\n{output_text}")
            logger.info(
                f"PARALLEL_ANALYZE: Topic '{topic_name}' completed via {provider_name} ({len(output_text)} chars)"
            )
        except (concurrent.futures.TimeoutError, TimeoutError):
            logger.error(f"WATCHDOG TIMEOUT: Analyze topic '{topic_name}' exceeded {analyze_timeout}s")
            future.cancel()
            all_outputs.append(f"=== Analysis: {topic_name} ===\nWATCHDOG: killed after {analyze_timeout}s")
        except Exception as e:
            logger.error(f"PARALLEL_ANALYZE: Topic '{topic_name}' failed: {e}")
            all_outputs.append(f"=== Analysis: {topic_name} ===\nError: {e}")

    # Merge all analysis results into design_output for SYNTHESIZE
    merged_analysis = "\n\n".join(all_outputs)
    state["design_output"] = merged_analysis

    phase_output = PhaseOutput(
        phase="PARALLEL_ANALYZE",
        status=PhaseStatus.COMPLETE,
        output=f"Analyzed {len(topics)} topics in parallel",
        exit_code=0,
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    logger.info(f"PARALLEL_ANALYZE: {len(topics)} topic channels completed")
    return state


def _split_into_topics(gather_output: str) -> list[tuple[str, str]]:
    """Split gathered output into topic chunks for parallel analysis.

    Looks for:
    1. Channel headers: === gatherer_xxx === or === gather_xxx ===
    2. Major section headers: # Heading or ## Heading

    Returns list of (topic_name, content) tuples.
    Each chunk gets at least 200 chars to be worth analyzing separately.
    """
    import re

    # Try splitting by gather channel headers first
    channel_pattern = re.compile(r"^=== (\w+) ===\s*$", re.MULTILINE)
    channel_matches = list(channel_pattern.finditer(gather_output))

    if len(channel_matches) >= 2:
        topics = []
        for i, match in enumerate(channel_matches):
            name = match.group(1)
            start = match.end()
            end = channel_matches[i + 1].start() if i + 1 < len(channel_matches) else len(gather_output)
            content = gather_output[start:end].strip()
            if len(content) >= 200:
                topics.append((name, content))
        if len(topics) >= 2:
            return topics

    # Fall back to major heading splits (# or ##)
    heading_pattern = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)
    heading_matches = list(heading_pattern.finditer(gather_output))

    if len(heading_matches) >= 2:
        topics = []
        for i, match in enumerate(heading_matches):
            name = re.sub(r"[^a-zA-Z0-9_]", "_", match.group(2).strip())[:40]
            start = match.start()
            end = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(gather_output)
            content = gather_output[start:end].strip()
            if len(content) >= 200:
                topics.append((name, content))
        if len(topics) >= 2:
            return topics

    # Not splittable — return as single topic
    return [("full_analysis", gather_output)]


def config_validate_decision(state: StoryState) -> Literal["pass", "fail"]:
    """Route after CONFIG_VALIDATE: pass -> verify_script, fail -> execute."""
    if state.get("verify_passed", True):
        return "pass"
    return "fail"


# --- Decision Functions ---


def verify_decision(state: StoryState) -> Literal["pass", "fail"]:
    """Route after VERIFY: pass → LEARN, fail → CODE."""
    vp = state.get("verify_passed", True)
    vr = state.get("verify_retry_count", 0)
    logger.info(f"verify_decision: verify_passed={vp}, verify_retry_count={vr}")
    if vp:
        return "pass"
    # Limit VERIFY→CODE cycles to avoid infinite loops
    if vr >= VERIFY_RETRY_LIMIT:
        logger.warning(f"VERIFY failed {vr} times, accepting and moving to LEARN")
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

    # For edit operations on content phases, inject existing file content
    if phase_name in ("CONTENT_PLAN", "CONTENT_WRITE") and story.get("operation_mode") == "edit":
        existing_content = _load_existing_file_for_edit(story, state.get("working_directory", "."))
        if existing_content:
            ctx["existing_file_content"] = existing_content

    return ctx


def _load_existing_file_for_edit(story: dict, working_directory: str) -> str:
    """Load existing file content for edit operations.

    Reads the output file specified in the story and returns its content,
    truncated to 15000 chars to avoid overwhelming the LLM context.

    Returns empty string if the file doesn't exist or can't be read.
    """
    output_path = story.get("output_path")
    if not output_path:
        return ""

    resolved = output_path if os.path.isabs(output_path) else os.path.join(working_directory, output_path)

    try:
        with open(resolved, encoding="utf-8") as f:
            content = f.read()
        if len(content) > 15000:
            content = content[:15000] + "\n\n[...truncated at 15000 chars...]"
        logger.info(f"Loaded existing file for edit: {resolved} ({len(content)} chars)")
        return content
    except (FileNotFoundError, OSError) as e:
        logger.debug(f"Could not load existing file for edit: {resolved}: {e}")
        return ""


def write_output_node(state: StoryState) -> StoryState:
    """Terminal node that writes the final output file for the story.

    Extracts the last meaningful phase output and writes it to the
    story's output_path if specified. Used by workflows that produce
    file-based deliverables (task verification, document assembly, etc.).
    """
    state = dict(state)
    story = state["story"]
    output_path = story.get("output_path")

    if not output_path:
        return state

    working_dir = state.get("working_directory", "")
    if output_path and not os.path.isabs(output_path):
        output_path = os.path.join(working_dir, output_path)

    # Find last complete phase output
    final_output = ""
    for po in reversed(state.get("phase_outputs", [])):
        if po.get("status") == "complete" and po.get("output"):
            final_output = po["output"]
            break

    if final_output and output_path:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                f.write(final_output)
            logger.info(f"Write output: {output_path}")
        except Exception as e:
            logger.error(f"Write output failed: {e}")

    return state


# --- Base Workflow Class ---


class BaseWorkflow(ABC):
    """Abstract base for all LangGraph workflows.

    Subclasses declare phases and edges via define_graph().
    The base class handles graph compilation and common patterns.
    """

    def __init__(self, routing_engine: RoutingEngine | None = None):
        self.routing_engine = routing_engine or RoutingEngine()

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """Build and return the compiled LangGraph StateGraph.

        Subclasses implement this to define their specific phase topology.
        Use the factory functions (phase_node, test_check_node, etc.) to create nodes.
        """
        ...

    def compile(self, checkpointer=None):
        """Compile the workflow graph."""
        return self.build_graph().compile(checkpointer=checkpointer)
