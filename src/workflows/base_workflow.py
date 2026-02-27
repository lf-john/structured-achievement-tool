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
from src.execution.verification_sdk import ConfigValidator, VerifyResult

logger = logging.getLogger(__name__)

# Directory for streaming LLM output to disk (enables partial recovery on timeout)
STREAM_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".memory", "streams")

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
    phase_timeout = get_phase_timeout(phase_name)
    story_id = story.get("id", "unknown")
    stream_file = _stream_file_path(story_id, phase_name)
    start_time = time.monotonic()
    result = None
    output_text = ""
    try:
        result = _run_async(
            cli_invoke(
                provider=provider, prompt=prompt, working_directory=working_dir,
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
            except (ValueError, Exception):
                pass  # Not all phases return JSON

    except (concurrent.futures.TimeoutError, TimeoutError):
        duration = time.monotonic() - start_time
        # Try to recover partial output from stream file
        output_text = ""
        try:
            if os.path.exists(stream_file):
                with open(stream_file, 'r', encoding='utf-8') as f:
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
    if phase_name in ("DESIGN", "ARCHITECT_CODE"):
        state["design_output"] = output_text
    elif phase_name in ("TDD_RED", "TEST_WRITER"):
        state["test_files"] = output_text
    elif phase_name in ("PLAN", "PLAN_CODE"):
        state["plan_output"] = output_text

    # Update verify_passed for VERIFY phases to feed verify_decision
    if phase_name in ("VERIFY", "VERIFY_SCRIPT"):
        state["verify_passed"] = (status == PhaseStatus.COMPLETE)
        logger.info(f"VERIFY phase setting verify_passed={state['verify_passed']} (status={status.value})")
        # Reset check retry counter — each VERIFY→CODE→CHECK cycle gets fresh budget
        state["phase_retry_count"] = 0
        # Track VERIFY→CODE cycle count when VERIFY fails
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
    phase_timeout = get_phase_timeout(phase_name)
    logger.info(f"Test check {phase_name}: running '{test_cmd}' (expect_failure={expect_failure}, timeout={phase_timeout}s)")
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
    mediator_timeout = get_phase_timeout("MEDIATOR")  # defaults to DEFAULT_PHASE_TIMEOUT (600s)
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
            ),
            timeout=mediator_timeout,
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
            logger.error(
                f"WATCHDOG TIMEOUT: Parallel verify check {agent_name} exceeded "
                f"{check_timeout}s — killing"
            )
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

    # Synthesize results
    state["verify_check_results"] = results
    state["verify_passed"] = all_passed

    if not all_passed:
        state["failure_context"] = (
            f"Parallel verification failed. "
            f"{len(failure_reasons)} check(s) failed:\n" +
            "\n".join(failure_reasons)
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
            check_results.append({
                "file": filepath,
                "passed": result.passed,
                "message": result.message,
            })
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
            state["failure_context"] = (
                f"Config validation failed for {len(failed)} file(s): " +
                "; ".join(f"{c['file']}: {c['message']}" for c in failed)
            )

    status = PhaseStatus.COMPLETE if state["verify_passed"] else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="CONFIG_VALIDATE",
        status=status,
        output=f"Validated {len(check_results)} config file(s), all_passed={all_passed}" if check_results else "No config files to validate",
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
        result = _run_async(cli_invoke(provider=provider, prompt=prompt, working_directory=working_dir, stream_output_file=stream_file), timeout=dep_timeout)
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
        output=output_text[:2000] if 'output_text' in dir() else "",
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
            logger.error(
                f"WATCHDOG TIMEOUT: Parallel gather channel {agent_name} exceeded "
                f"{gather_timeout}s — killing"
            )
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

    def compile(self, checkpointer=None):
        """Compile the workflow graph."""
        return self.build_graph().compile(checkpointer=checkpointer)
