"""
Human Workflow Nodes — Shared nodes for human story types.

Phase 5 items 5.2-5.5. All human story workflows share:
- PREPARE: Build a human-readable summary (TL;DR, Action Required, Context, Deliverables)
- NOTIFY: Send notification (reuses control_nodes.notify_node)
- PAUSE: Wait for human response (reuses approval_workflow nodes)

Each workflow adds type-specific VALIDATE/PARSE/ROUTE logic after PAUSE.
"""

import logging

from src.workflows.state import PhaseOutput, PhaseStatus, StoryState

logger = logging.getLogger(__name__)


def prepare_node(
    state: StoryState,
    story_type: str = "assignment",
) -> StoryState:
    """Build a human-readable summary from story context.

    Creates a structured brief with:
    - TL;DR: One-line summary
    - Action Required: What the human needs to do
    - Context: Collapsed details from prior phases
    - Deliverables: What the human should produce, with verification criteria
    - Deadline: If specified in story

    The summary is stored in state["human_summary"] for use by
    NOTIFY and PAUSE nodes.
    """
    state = dict(state)
    state["current_phase"] = "PREPARE"

    story = state.get("story", {})
    story_id = story.get("id", "unknown")
    story_title = story.get("title", "Untitled")
    description = story.get("description", "")
    criteria = story.get("acceptanceCriteria", [])
    deadline = story.get("deadline", None)
    phase_outputs = state.get("phase_outputs", [])

    # Build TL;DR from title
    tldr = story_title

    # Determine Action Required based on story type
    action_map = {
        "assignment": "Complete the deliverables listed below and mark as done.",
        "approval": "Review the changes and approve or reject.",
        "qa_feedback": "Test the implementation and provide feedback.",
        "escalation": "Review the diagnostic information and provide guidance.",
    }
    action_required = action_map.get(story_type, "Review and respond.")

    # Build context from prior phase outputs (collapsed)
    context_parts = []
    if description:
        context_parts.append(description)

    for output in phase_outputs:
        phase = output.get("phase", "")
        out_text = output.get("output", "")
        if out_text and phase not in ("PREPARE", "NOTIFY", "PAUSE"):
            context_parts.append(f"**{phase}:** {out_text[:300]}")

    # Add failure context if this is an escalation
    failure_ctx = state.get("failure_context", "")
    if failure_ctx and story_type == "escalation":
        context_parts.append(f"**Failure:** {failure_ctx[:500]}")

    context = "\n\n".join(context_parts) if context_parts else "No additional context."

    # Build deliverables with verification
    deliverables = []
    for criterion in criteria:
        deliverables.append(f"- [ ] {criterion}")

    # Assemble human summary
    summary_parts = [
        f"# {story_type.title()}: {story_id}",
        "",
        "## TL;DR",
        f"{tldr}",
        "",
        "## Action Required",
        f"{action_required}",
        "",
    ]

    if deliverables:
        summary_parts.extend([
            "## Deliverables",
            "",
        ] + deliverables + [""])

    if deadline:
        summary_parts.extend([
            "## Deadline",
            f"{deadline}",
            "",
        ])

    summary_parts.extend([
        "<details>",
        "<summary>Context (click to expand)</summary>",
        "",
        context,
        "",
        "</details>",
    ])

    human_summary = "\n".join(summary_parts)
    state["human_summary"] = human_summary

    # Record phase output
    phase_output = PhaseOutput(
        phase="PREPARE",
        status=PhaseStatus.COMPLETE,
        output=f"Prepared {story_type} summary for {story_id} ({len(human_summary)} chars)",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    logger.info(f"PREPARE: Built {story_type} summary for {story_id}")
    return state


def validate_node(
    state: StoryState,
) -> StoryState:
    """Validate that the human's response meets the acceptance criteria.

    For assignment stories: checks if deliverables are marked as done.
    Uses the human's response text from pause_response.
    """
    state = dict(state)
    state["current_phase"] = "VALIDATE"

    story = state.get("story", {})
    criteria = story.get("acceptanceCriteria", [])
    response = state.get("pause_response", "")

    # Check if response indicates completion
    # Look for explicit markers or positive indicators
    response_lower = response.lower()
    completed = any(word in response_lower for word in [
        "done", "complete", "finished", "delivered", "resolved",
        "approved", "confirmed", "verified",
    ])

    if not criteria:
        # No criteria to validate — accept any response
        state["verify_passed"] = True
        state["validation_result"] = {"passed": True, "reason": "No criteria to validate"}
    elif completed:
        state["verify_passed"] = True
        state["validation_result"] = {"passed": True, "reason": "Human confirmed completion"}
    else:
        state["verify_passed"] = False
        state["validation_result"] = {
            "passed": False,
            "reason": f"Response does not indicate completion: {response[:200]}",
        }

    status = PhaseStatus.COMPLETE if state["verify_passed"] else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="VALIDATE",
        status=status,
        output=f"Validation: passed={state['verify_passed']}",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    return state


def parse_feedback_node(
    state: StoryState,
) -> StoryState:
    """Parse structured feedback from a QA tester's response.

    Extracts:
    - Overall verdict (pass/fail/partial)
    - Individual test results
    - Bug reports
    - Suggestions

    Stores in state["qa_feedback_parsed"].
    """
    state = dict(state)
    state["current_phase"] = "PARSE"

    response = state.get("pause_response", "")
    response_lower = response.lower()

    # Determine overall verdict
    if any(word in response_lower for word in ["pass", "approved", "looks good", "lgtm"]):
        verdict = "pass"
    elif any(word in response_lower for word in ["fail", "broken", "rejected", "bug"]):
        verdict = "fail"
    else:
        verdict = "partial"

    # Extract bug reports (lines starting with "bug:" or "issue:" or "- [x]")
    bugs = []
    suggestions = []
    for line in response.split("\n"):
        line_stripped = line.strip().lower()
        if line_stripped.startswith(("bug:", "issue:", "defect:")):
            bugs.append(line.strip())
        elif line_stripped.startswith(("suggest:", "suggestion:", "improvement:", "consider:")):
            suggestions.append(line.strip())

    state["qa_feedback_parsed"] = {
        "verdict": verdict,
        "bugs": bugs,
        "suggestions": suggestions,
        "raw_response": response[:2000],
    }

    state["verify_passed"] = verdict == "pass"

    phase_output = PhaseOutput(
        phase="PARSE",
        status=PhaseStatus.COMPLETE,
        output=f"QA verdict: {verdict}, bugs: {len(bugs)}, suggestions: {len(suggestions)}",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    return state


def integrate_node(
    state: StoryState,
) -> StoryState:
    """Integrate human work into the system.

    For assignment stories: records the human's deliverables and
    marks the story as complete in state.
    """
    state = dict(state)
    state["current_phase"] = "INTEGRATE"

    story = state.get("story", {})
    response = state.get("pause_response", "")

    # Record human's work
    state["human_deliverables"] = response[:5000]

    phase_output = PhaseOutput(
        phase="INTEGRATE",
        status=PhaseStatus.COMPLETE,
        output=f"Integrated human deliverables for {story.get('id', 'unknown')}",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    return state


def package_diagnostics_node(
    state: StoryState,
) -> StoryState:
    """Package diagnostic information for escalation.

    Collects:
    - All phase outputs and failure context
    - Attempted fixes
    - Recommendations
    - System state information

    Stores in state["escalation_package"].
    """
    state = dict(state)
    state["current_phase"] = "PACKAGE_DIAGNOSTICS"

    story = state.get("story", {})
    phase_outputs = state.get("phase_outputs", [])
    failure_context = state.get("failure_context", "")

    # Collect attempted fixes from phase outputs
    attempted_fixes = []
    for output in phase_outputs:
        phase = output.get("phase", "")
        status = output.get("status", "")
        if phase in ("CODE", "FIX", "EXECUTE") and status == "failed":
            attempted_fixes.append({
                "phase": phase,
                "output": output.get("output", "")[:500],
            })

    # Build recommendations based on failure patterns
    recommendations = []
    if "timeout" in failure_context.lower():
        recommendations.append("Consider increasing timeouts or optimizing the operation")
    if "permission" in failure_context.lower():
        recommendations.append("Check file/directory permissions and user privileges")
    if "import" in failure_context.lower() or "module" in failure_context.lower():
        recommendations.append("Verify dependencies are installed and import paths are correct")
    if not recommendations:
        recommendations.append("Manual investigation recommended — automated diagnosis inconclusive")

    state["escalation_package"] = {
        "story_id": story.get("id", "unknown"),
        "story_title": story.get("title", ""),
        "failure_context": failure_context[:2000],
        "attempted_fixes": attempted_fixes,
        "recommendations": recommendations,
        "total_attempts": state.get("story_attempt", 1),
        "phase_history": [
            {"phase": o.get("phase", ""), "status": o.get("status", "")}
            for o in phase_outputs
        ],
    }

    phase_output = PhaseOutput(
        phase="PACKAGE_DIAGNOSTICS",
        status=PhaseStatus.COMPLETE,
        output=f"Packaged diagnostics: {len(attempted_fixes)} fixes attempted, {len(recommendations)} recommendations",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    return state
