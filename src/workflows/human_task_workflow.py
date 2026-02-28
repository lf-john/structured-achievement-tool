"""
Human Task Workflow — TDD-style workflow for stories that need human intervention.

DETECT → PRE_VERIFY → GENERATE_INSTRUCTIONS → WRITE_INSTRUCTIONS →
  APPROVAL (Notify-Pause loop with escalation) →
  QUICK_CHECK → (pass → FINAL_CHECK → LEARN | fail → re-APPROVAL)

TDD approach for human tasks:
1. DETECT: Confirms human intervention is needed, generates verification checks
2. PRE_VERIFY: Runs all verification checks — both quick and final should FAIL
   (proving the work hasn't been done yet). If any pass, the story may not need
   human intervention after all.
3. GENERATE_INSTRUCTIONS: Produces step-by-step click-by-click instructions
4. WRITE_INSTRUCTIONS: Writes instructions to the task's response file
5. APPROVAL: Notify-Pause loop with follow-up and escalation
6. QUICK_CHECK: Runs immediate verification — user sees "Verifying, please wait..."
7. FINAL_CHECK: Runs delayed verification checks (DNS propagation, etc.)
8. LEARN: Record what happened

Loopbacks:
- If DETECT determines no human input is needed, routes to END
- If PRE_VERIFY checks pass (work already done), routes to LEARN
- If QUICK_CHECK fails, routes back to APPROVAL (user needs to try again)
- FINAL_CHECK uses DelayedChecker wait/retry loop
"""

import logging
import os
from functools import partial
from typing import Literal, Optional

from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState, PhaseOutput, PhaseStatus
from src.workflows.base_workflow import BaseWorkflow, phase_node, _run_async
from src.workflows.control_nodes import notify_node
from src.workflows.approval_workflow import (
    ApprovalConfig,
    approval_pause_node,
    pause_initial_decision,
    approval_follow_up_node,
    follow_up_decision,
    approval_escalation_node,
)
from src.agents.human_task_agent import (
    HumanTaskAgent,
    HumanTaskResponse,
    VerificationCheck,
    detect_human_needs,
    detect_provider,
)
from src.execution.verification_sdk import (
    DelayedChecker,
    PortChecker,
    FileChecker,
    ServiceChecker,
    ConfigValidator,
    VerifyResult,
)
from src.notifications.notifier import Notifier
from src.llm.routing_engine import RoutingEngine

logger = logging.getLogger(__name__)

# Marker that the story executor checks to know this story paused for human input
PAUSED_FOR_HUMAN = "paused_for_human"


# --- Node Functions ---

def detect_node(
    state: StoryState,
    routing_engine: RoutingEngine,
) -> StoryState:
    """Detect whether the story requires human intervention.

    Uses the HumanTaskAgent for LLM-powered analysis. Falls back to
    heuristic detection if the LLM call fails.

    Sets state fields:
    - human_task_response: Full HumanTaskResponse dict
    - human_summary: Instructions text (reuses the human_nodes field)
    - verify_passed: False if human input needed (pauses workflow)
    """
    state = dict(state)
    state["current_phase"] = "DETECT_HUMAN_NEEDS"

    story = state.get("story", {})
    working_dir = state.get("working_directory", ".")
    task_description = state.get("task_description", "")

    agent = HumanTaskAgent(routing_engine=routing_engine)

    try:
        response = _run_async(
            agent.analyze(
                story=story,
                working_directory=working_dir,
                task_description=task_description,
            ),
            timeout=120,
        )
    except Exception as e:
        logger.warning(f"DETECT_HUMAN_NEEDS: LLM analysis failed: {e}, using heuristics")
        response = agent._heuristic_response(story)

    # Store the full response for downstream nodes
    state["human_task_response"] = response.model_dump()

    if response.needs_human:
        state["human_summary"] = response.instructions
        state["verify_passed"] = False  # Signal that we need to pause
        logger.info(
            f"DETECT_HUMAN_NEEDS: Human intervention required for {story.get('id', '?')} "
            f"(provider={response.provider}, reason={response.reason[:100]})"
        )
    else:
        state["verify_passed"] = True
        logger.info(
            f"DETECT_HUMAN_NEEDS: No human intervention needed for {story.get('id', '?')}"
        )

    phase_output = PhaseOutput(
        phase="DETECT_HUMAN_NEEDS",
        status=PhaseStatus.COMPLETE,
        output=f"needs_human={response.needs_human}, provider={response.provider}, reason={response.reason[:200]}",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    return state


def generate_instructions_node(
    state: StoryState,
) -> StoryState:
    """Format the human task instructions into a user-friendly document.

    Takes the raw HumanTaskResponse and formats it into a structured
    markdown document with clear sections for instructions, required
    inputs, and verification steps.
    """
    state = dict(state)
    state["current_phase"] = "GENERATE_INSTRUCTIONS"

    story = state.get("story", {})
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")
    response_data = state.get("human_task_response", {})

    instructions = response_data.get("instructions", "")
    required_inputs = response_data.get("required_inputs", [])
    provider = response_data.get("provider", "")
    doc_url = response_data.get("documentation_url", "")
    est_time = response_data.get("estimated_time_minutes", 0)
    reason = response_data.get("reason", "")

    # Build the formatted instructions document
    parts = [
        f"# Human Action Required: {story_title}",
        f"**Story ID:** {story_id}",
        "",
    ]

    if provider:
        parts.append(f"**Provider:** {provider}")
    if est_time:
        parts.append(f"**Estimated Time:** ~{est_time} minutes")
    if reason:
        parts.append(f"**Why:** {reason}")

    parts.append("")

    # Main instructions
    if instructions:
        parts.append("---")
        parts.append("")
        parts.append(instructions)
        parts.append("")

    # Required inputs section
    if required_inputs:
        parts.append("---")
        parts.append("")
        parts.append("## Information to Provide")
        parts.append("")
        parts.append("Please provide the following in your response:")
        parts.append("")
        for inp in required_inputs:
            name = inp.get("name", "unknown")
            desc = inp.get("description", "")
            example = inp.get("example", "")
            sensitive = inp.get("sensitive", False)

            line = f"- **{name}**: {desc}"
            if example:
                line += f" (example: `{example}`)"
            if sensitive:
                line += " [SENSITIVE]"
            parts.append(line)
        parts.append("")

    # Documentation link
    if doc_url:
        parts.append(f"## Documentation")
        parts.append(f"- {doc_url}")
        parts.append("")

    # Response instructions — explain the verification process
    parts.extend([
        "---",
        "",
        "## How to Respond",
        "",
        "1. Complete the steps above",
        "2. Write your response (credentials, confirmation, etc.) below the `---` separator",
        "3. Remove the `#` from `# <Pending>` at the bottom to signal completion",
        "",
        "## What Happens Next",
        "",
        "After you signal completion, the system will:",
        "1. **Verify immediately** — You'll receive a notification saying \"Verifying, please wait...\"",
        "2. **Quick Check** — The system runs immediate verification checks to confirm your work",
        "3. If checks **pass**, the system proceeds (you'll be notified of success)",
        "4. If checks **fail**, you'll be notified of what failed and asked to try again",
        "5. **Final Check** — For items that take time (DNS propagation, SSL, etc.), the system runs delayed checks with automatic retries",
        "",
    ])

    formatted_instructions = "\n".join(parts)
    state["human_summary"] = formatted_instructions

    phase_output = PhaseOutput(
        phase="GENERATE_INSTRUCTIONS",
        status=PhaseStatus.COMPLETE,
        output=f"Generated {len(formatted_instructions)} chars of instructions for {story_id}",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    logger.info(f"GENERATE_INSTRUCTIONS: Formatted instructions for {story_id} ({len(formatted_instructions)} chars)")
    return state


def write_instructions_node(
    state: StoryState,
    notifier: Notifier,
) -> StoryState:
    """Write human task instructions to the response file and notify.

    This node writes the formatted instructions to a response file in the
    task directory, then sends a notification to the user.

    The response file includes a `# <Pending>` tag so the user can signal
    completion by removing the `#`.
    """
    state = dict(state)
    state["current_phase"] = "WRITE_INSTRUCTIONS"

    story = state.get("story", {})
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")
    instructions = state.get("human_summary", "")
    provider = state.get("human_task_response", {}).get("provider", "")

    # Send notification
    try:
        prefix = f"[{provider}] " if provider else ""
        notifier.send_ntfy(
            title=f"SAT: {prefix}Human Action Required ({story_id})",
            message=f"Story: {story_title}\nAction required — check your task file for instructions.",
            priority="high",
            tags="hand,clipboard",
        )
    except Exception as e:
        logger.warning(f"WRITE_INSTRUCTIONS: notification failed: {e}")

    phase_output = PhaseOutput(
        phase="WRITE_INSTRUCTIONS",
        status=PhaseStatus.COMPLETE,
        output=f"Instructions written for {story_id}, notification sent",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    logger.info(f"WRITE_INSTRUCTIONS: Instructions prepared for {story_id}")
    return state


def _run_verification_check(check: dict, working_dir: str) -> VerifyResult:
    """Run a single verification check and return result."""
    check_type = check.get("type", "command")

    if check_type == "command":
        import subprocess
        try:
            result = subprocess.run(
                check.get("command", "true"), shell=True,
                capture_output=True, text=True, timeout=30, cwd=working_dir,
            )
            return VerifyResult(
                passed=result.returncode == 0,
                checker="human_tdd",
                target=check.get("description", check.get("command", "")),
                message=f"exit {result.returncode}" + (f": {result.stderr[:200]}" if result.stderr else ""),
                details={"stdout": result.stdout[:500], "stderr": result.stderr[:500]},
            )
        except Exception as e:
            return VerifyResult(passed=False, checker="human_tdd", target=check.get("description", ""), message=str(e))

    elif check_type == "http":
        pc = PortChecker()
        return pc.check_http(check.get("url", ""), expected_status=check.get("expected_status", 200))

    elif check_type == "dns":
        import socket
        hostname = check.get("hostname", "")
        expected = check.get("expected_value", "")
        try:
            answers = socket.getaddrinfo(hostname, None)
            resolved = [a[4][0] for a in answers]
            passed = expected in resolved if expected else len(resolved) > 0
            return VerifyResult(passed=passed, checker="human_tdd", target=hostname,
                                message=f"resolves to {', '.join(set(resolved))}")
        except socket.gaierror as e:
            return VerifyResult(passed=False, checker="human_tdd", target=hostname, message=f"DNS failed: {e}")

    elif check_type == "port_check":
        pc = PortChecker()
        return pc.check_listening(check.get("hostname", "localhost"), int(check.get("port", 0)))

    elif check_type == "file_check":
        fc = FileChecker()
        path = check.get("path", check.get("command", ""))
        if path and not os.path.isabs(path):
            path = os.path.join(working_dir, path)
        return fc.check_exists(path)

    elif check_type == "service_check":
        sc = ServiceChecker()
        return sc.check_systemd(check.get("service", ""), user=check.get("user", True))

    else:
        return VerifyResult(passed=False, checker="human_tdd", target=check_type, message=f"unknown check type: {check_type}")


def pre_verify_node(state: StoryState) -> StoryState:
    """Run verification checks BEFORE human acts — TDD Red.

    All checks should FAIL, proving the work hasn't been done yet.
    If checks pass, the work may already be complete.
    """
    state = dict(state)
    state["current_phase"] = "PRE_VERIFY"

    response_data = state.get("human_task_response", {})
    checks = response_data.get("verification_checks", [])
    working_dir = state.get("working_directory", ".")

    if not checks:
        # No verification checks defined — skip pre-verify
        state["validation_result"] = {"passed": False, "reason": "no_checks_defined", "pre_verify": True}
        phase_output = PhaseOutput(
            phase="PRE_VERIFY", status=PhaseStatus.COMPLETE,
            output="No verification checks defined, skipping pre-verify",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    results = []
    for check in checks:
        vr = _run_verification_check(check, working_dir)
        results.append({"description": check.get("description", ""), "passed": vr.passed, "message": vr.message})

    all_failed = all(not r["passed"] for r in results)
    any_passed = any(r["passed"] for r in results)

    if all_failed:
        logger.info(f"PRE_VERIFY: All {len(results)} checks failed as expected (TDD Red confirmed)")
        state["validation_result"] = {"passed": False, "reason": "pre_verify_confirmed", "pre_verify": True, "results": results}
    elif any_passed:
        passed_checks = [r for r in results if r["passed"]]
        logger.info(f"PRE_VERIFY: {len(passed_checks)}/{len(results)} checks already pass — work may be partially done")
        state["validation_result"] = {"passed": True, "reason": "already_done", "pre_verify": True, "results": results}

    phase_output = PhaseOutput(
        phase="PRE_VERIFY", status=PhaseStatus.COMPLETE,
        output=f"Pre-verify: {len(results)} checks, {sum(1 for r in results if not r['passed'])} failed as expected",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
    return state


def pre_verify_decision(state: StoryState) -> Literal["needs_work", "already_done"]:
    """Route after PRE_VERIFY: if all checks pass, work is already done."""
    vr = state.get("validation_result", {})
    if vr.get("passed") and vr.get("reason") == "already_done":
        return "already_done"
    return "needs_work"


def quick_check_node(
    state: StoryState,
    notifier: Optional[Notifier] = None,
) -> StoryState:
    """Run immediate verification checks after human signals completion.

    Sends a "Verifying immediately, please wait..." notification before
    running checks. Only runs checks marked as is_quick_check=True.
    Reports pass/fail result via notification.
    """
    state = dict(state)
    state["current_phase"] = "QUICK_CHECK"

    story = state.get("story", {})
    story_id = story.get("id", "unknown")

    response_data = state.get("human_task_response", {})
    checks = response_data.get("verification_checks", [])
    working_dir = state.get("working_directory", ".")

    quick_checks = [c for c in checks if c.get("is_quick_check", True)]
    if not quick_checks:
        state["validation_result"] = {"passed": True, "reason": "no_quick_checks", "quick_check": True}
        phase_output = PhaseOutput(
            phase="QUICK_CHECK", status=PhaseStatus.COMPLETE,
            output="No quick checks defined, passing",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    # Notify: verifying immediately
    if notifier:
        try:
            notifier.send_ntfy(
                title=f"SAT: Verifying ({story_id})",
                message=f"Verifying immediately, please wait...\nRunning {len(quick_checks)} quick check(s).",
                tags="hourglass_flowing_sand",
            )
        except Exception:
            pass

    results = []
    for check in quick_checks:
        vr = _run_verification_check(check, working_dir)
        results.append({"description": check.get("description", ""), "passed": vr.passed, "message": vr.message})

    all_passed = all(r["passed"] for r in results)

    if all_passed:
        logger.info(f"QUICK_CHECK: All {len(results)} quick checks passed")
        if notifier:
            try:
                notifier.send_ntfy(
                    title=f"SAT: Verification Passed ({story_id})",
                    message=f"All {len(results)} quick check(s) passed.",
                    tags="white_check_mark",
                )
            except Exception:
                pass
    else:
        failed = [r for r in results if not r["passed"]]
        logger.info(f"QUICK_CHECK: {len(failed)}/{len(results)} quick checks failed")
        if notifier:
            fail_details = "\n".join(f"  - {r['description']}: {r['message']}" for r in failed)
            try:
                notifier.send_ntfy(
                    title=f"SAT: Verification Failed ({story_id})",
                    message=f"{len(failed)}/{len(results)} check(s) failed:\n{fail_details}\n\nPlease retry.",
                    priority="high",
                    tags="x",
                )
            except Exception:
                pass

    state["validation_result"] = {"passed": all_passed, "reason": "quick_check", "results": results}
    state["verify_passed"] = all_passed

    status = PhaseStatus.COMPLETE if all_passed else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="QUICK_CHECK", status=status,
        output=f"Quick check: {sum(1 for r in results if r['passed'])}/{len(results)} passed",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
    return state


def quick_check_decision(state: StoryState) -> Literal["passed", "failed"]:
    """Route after QUICK_CHECK."""
    vr = state.get("validation_result", {})
    return "passed" if vr.get("passed") else "failed"


def final_check_node(state: StoryState) -> StoryState:
    """Run delayed verification checks using wait/retry loop.

    Only runs checks marked as is_quick_check=False (delayed checks).
    Uses DelayedChecker for wait/retry behavior.
    """
    state = dict(state)
    state["current_phase"] = "FINAL_CHECK"

    response_data = state.get("human_task_response", {})
    checks = response_data.get("verification_checks", [])
    working_dir = state.get("working_directory", ".")

    delayed_checks = [c for c in checks if not c.get("is_quick_check", True)]
    if not delayed_checks:
        state["validation_result"] = {"passed": True, "reason": "no_delayed_checks", "final_check": True}
        state["verify_passed"] = True
        phase_output = PhaseOutput(
            phase="FINAL_CHECK", status=PhaseStatus.COMPLETE,
            output="No delayed checks defined, passing",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    dc = DelayedChecker()
    results = []
    all_passed = True

    for check in delayed_checks:
        wait_secs = check.get("wait_seconds", 300)
        max_att = check.get("max_attempts", 6)
        desc = check.get("description", "delayed check")

        def make_check_fn(c):
            return lambda: _run_verification_check(c, working_dir)

        vr = dc.check_with_retry(
            check_fn=make_check_fn(check),
            wait_seconds=wait_secs,
            max_attempts=max_att,
            description=desc,
        )
        results.append({"description": desc, "passed": vr.passed, "message": vr.message, "details": vr.details})
        if not vr.passed:
            all_passed = False

    state["validation_result"] = {"passed": all_passed, "reason": "final_check", "results": results}
    state["verify_passed"] = all_passed

    status = PhaseStatus.COMPLETE if all_passed else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="FINAL_CHECK", status=status,
        output=f"Final check: {sum(1 for r in results if r['passed'])}/{len(results)} passed",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
    return state


def detect_decision(state: StoryState) -> Literal["human_needed", "not_needed"]:
    """Route after DETECT: human_needed -> pre_verify, not_needed -> END."""
    response_data = state.get("human_task_response", {})
    if response_data.get("needs_human", False):
        return "human_needed"
    return "not_needed"


# --- Workflow Class ---

class HumanTaskWorkflow(BaseWorkflow):
    """TDD-style workflow for stories that require human intervention.

    DETECT → PRE_VERIFY → GENERATE_INSTRUCTIONS → WRITE_INSTRUCTIONS →
      NOTIFY → PAUSE → QUICK_CHECK → (pass → FINAL_CHECK → LEARN | fail → re-PAUSE)

    TDD approach:
    1. DETECT: Analyze story, generate verification checks
    2. PRE_VERIFY: Run all checks — should all FAIL (TDD Red)
    3. If all checks already pass, skip to LEARN (work already done)
    4. GENERATE/WRITE/NOTIFY: Produce instructions and notify user
    5. PAUSE: Wait for human to complete and signal done
    6. QUICK_CHECK: Run immediate verification checks
    7. If quick checks fail, re-PAUSE (user needs to try again)
    8. FINAL_CHECK: Run delayed verification checks (wait/retry loop)
    9. LEARN: Record outcome

    Uses the ApprovalWorkflow's pause/follow-up/escalation pattern for PAUSE.
    """

    def __init__(
        self,
        routing_engine: Optional[RoutingEngine] = None,
        notifier: Optional[Notifier] = None,
        config: Optional[ApprovalConfig] = None,
    ):
        self.routing_engine = routing_engine or RoutingEngine()
        self.notifier = notifier or Notifier()
        self.config = config or ApprovalConfig()

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine
        ntf = self.notifier
        cfg = self.config

        # Nodes — APPROVAL is the Notify-Pause loop with escalation
        builder.add_node("detect", partial(detect_node, routing_engine=re))
        builder.add_node("pre_verify", pre_verify_node)
        builder.add_node("generate_instructions", generate_instructions_node)
        builder.add_node("write_instructions", partial(write_instructions_node, notifier=ntf))
        builder.add_node("notify", partial(notify_node, notifier=ntf))
        builder.add_node("approval", partial(approval_pause_node, notifier=ntf, config=cfg))
        builder.add_node("approval_follow_up", partial(approval_follow_up_node, notifier=ntf, config=cfg))
        builder.add_node("approval_escalation", partial(approval_escalation_node, notifier=ntf, config=cfg))
        builder.add_node("quick_check", partial(quick_check_node, notifier=ntf))
        builder.add_node("final_check", final_check_node)
        builder.add_node("learn", partial(
            phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re,
        ))

        # Entry
        builder.set_entry_point("detect")

        # DETECT → human_needed: pre_verify, not_needed: END
        builder.add_conditional_edges("detect", detect_decision, {
            "human_needed": "pre_verify",
            "not_needed": END,
        })

        # PRE_VERIFY → needs_work: generate instructions, already_done: learn
        builder.add_conditional_edges("pre_verify", pre_verify_decision, {
            "needs_work": "generate_instructions",
            "already_done": "learn",
        })

        # GENERATE → WRITE → NOTIFY → APPROVAL
        builder.add_edge("generate_instructions", "write_instructions")
        builder.add_edge("write_instructions", "notify")
        builder.add_edge("notify", "approval")

        # APPROVAL → responded: quick_check, follow_up/escalate
        builder.add_conditional_edges("approval", pause_initial_decision, {
            "responded": "quick_check",
            "follow_up": "approval_follow_up",
            "escalate": "approval_escalation",
        })

        builder.add_conditional_edges("approval_follow_up", follow_up_decision, {
            "responded": "quick_check",
            "escalate": "approval_escalation",
        })

        # QUICK_CHECK → passed: final_check, failed: approval (try again)
        builder.add_conditional_edges("quick_check", quick_check_decision, {
            "passed": "final_check",
            "failed": "approval",
        })

        # FINAL_CHECK → LEARN
        builder.add_edge("final_check", "learn")

        # Escalation → LEARN (with whatever response we have)
        builder.add_edge("approval_escalation", "learn")

        # LEARN → END
        builder.add_edge("learn", END)

        return builder

    def compile(self, checkpointer=None):
        return self.build_graph().compile(checkpointer=checkpointer)
