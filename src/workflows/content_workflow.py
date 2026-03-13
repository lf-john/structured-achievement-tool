"""
Content Workflow — For document creation with mechanical + critic verification.

PLAN → WRITE → MECHANICAL_VERIFY → CRITIC_REVIEW → LEARN

PLAN produces:
- Document outline
- Group 1 rules (mechanical, testable)
- Group 2 qualities (agentic, LLM-reviewed)

WRITE produces the document.

MECHANICAL_VERIFY runs automated checks (word count, format, structure).
On failure → loops back to WRITE (up to 3 times).

CRITIC_REVIEW has CriticAgent evaluate against acceptance criteria.
On failure → loops back to WRITE (up to 2 times), then fails.

LEARN extracts learnings for vector memory.
"""

import logging
import os
import re
from functools import partial

from langgraph.graph import END, StateGraph

from src.agents.ac_templates import get_default_acs, merge_acs
from src.agents.critic_agent import CriticAgent, validate_ratings
from src.workflows.base_workflow import (
    BaseWorkflow,
    _run_async,
    phase_node,
)
from src.workflows.state import PhaseOutput, PhaseStatus, StoryState

logger = logging.getLogger(__name__)

# Max retries for WRITE → VERIFY loops
MAX_VERIFY_RETRIES = 3

# After 2 critic→rework loops, story FAILS
MAX_CRITIC_RETRIES = 2


def _extract_plan_data(state: dict) -> dict:
    """Extract structured plan data from CONTENT_PLAN phase output."""
    plan_output = state.get("plan_output", "")
    if not plan_output:
        return {}
    try:
        from src.llm.response_parser import extract_json

        parsed = extract_json(plan_output)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _parse_range(value: str) -> tuple:
    """Parse a range like '500-2000' or '>=3' into (min, max)."""
    if not value:
        return (0, float("inf"))
    value = value.strip()
    if value.startswith(">="):
        return (int(value[2:]), float("inf"))
    if value.startswith("<="):
        return (0, int(value[2:]))
    if "-" in value:
        parts = value.split("-", 1)
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            return (0, float("inf"))
    try:
        n = int(value)
        return (n, n)
    except ValueError:
        return (0, float("inf"))


def mechanical_verify_node(state: StoryState) -> StoryState:
    """Run Group 1 mechanical checks on the written document.

    Extracts doc_type from the CONTENT_PLAN output and applies per-type rules
    via get_rules_for_doc_type(). Falls back to default rules if plan not available.

    Updates verify_passed and failure_context in state.
    """
    from src.workflows.content_models import get_rules_for_doc_type

    state = dict(state)
    state["current_phase"] = "MECHANICAL_VERIFY"
    story = state["story"]
    story_id = story.get("id", "unknown")
    working_dir = state["working_directory"]

    # Extract doc_type from plan output or story
    plan_data = _extract_plan_data(state)
    doc_type = plan_data.get("doc_type") or story.get("doc_type", "technical")

    # Get doc-type-specific rules
    rules = get_rules_for_doc_type(doc_type)
    rules_dict = {r.name: r for r in rules if r.enabled}

    # Also check plan-specified rules (override defaults, but don't tighten word_count)
    plan_rules = plan_data.get("group1_rules", [])
    for pr in plan_rules:
        name = pr.get("name")
        if name and name in rules_dict:
            if pr.get("value"):
                # Don't let the planner reduce the word_count upper bound
                # below the doc-type default — content writers often exceed
                # the planner's estimate.
                if name == "word_count":
                    default_lo, default_hi = _parse_range(rules_dict[name].value)
                    plan_lo, plan_hi = _parse_range(pr["value"])
                    merged_hi = max(default_hi, plan_hi)
                    merged_lo = min(default_lo, plan_lo) if plan_lo else default_lo
                    rules_dict[name].value = f"{merged_lo}-{merged_hi}"
                else:
                    rules_dict[name].value = pr["value"]
            if pr.get("enabled") is False:
                del rules_dict[name]

    # Find the output file
    output_path = plan_data.get("output_path") or story.get("output_path", "")
    if not output_path:
        output_path = _detect_output_path(state, working_dir)

    if output_path and not os.path.isabs(output_path):
        output_path = os.path.join(working_dir, output_path)

    failures = []
    checks_run = []

    # Check: File exists (always required)
    checks_run.append("file_exists")
    if not output_path or not os.path.exists(output_path):
        failures.append(f"Output file not found: {output_path or 'no path specified'}")
    else:
        try:
            with open(output_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            failures.append(f"Cannot read output file: {e}")
            content = ""

        if content:
            word_count = len(content.split())
            headings = re.findall(r"^#{1,2}\s+\S", content, re.MULTILINE)
            sub_headings = re.findall(r"^#{2,3}\s+\S", content, re.MULTILINE)

            # Word count check
            if "word_count" in rules_dict:
                checks_run.append("word_count")
                lo, hi = _parse_range(rules_dict["word_count"].value)
                if word_count < lo:
                    failures.append(f"Word count too low: {word_count} (expected >={lo})")
                elif word_count > hi:
                    failures.append(f"Word count too high: {word_count} (expected <={hi})")

            # Heading count check
            if "heading_count" in rules_dict:
                checks_run.append("heading_count")
                lo, _ = _parse_range(rules_dict["heading_count"].value)
                if len(headings) < lo:
                    failures.append(f"Heading count: {len(headings)} (expected >={lo})")

            # Sub-heading count check
            if "sub_heading_count" in rules_dict:
                checks_run.append("sub_heading_count")
                lo, _ = _parse_range(rules_dict["sub_heading_count"].value)
                if len(sub_headings) < lo:
                    failures.append(f"Sub-heading count: {len(sub_headings)} (expected >={lo})")

            # No unreplaced placeholders (always enforced)
            checks_run.append("no_placeholders")
            placeholders = re.findall(r"\{\{[A-Z_]+\}\}", content)
            if placeholders:
                failures.append(f"Unreplaced placeholders found: {placeholders[:5]}")

            # No merge conflict markers (always enforced)
            checks_run.append("no_merge_tokens")
            merge_markers = re.findall(r"^[<>=]{7}", content, re.MULTILINE)
            if merge_markers:
                failures.append(f"Merge conflict markers found ({len(merge_markers)})")

            # Substantive content check
            checks_run.append("substantive_content")
            lines = [l.strip() for l in content.split("\n") if l.strip()]
            non_heading_lines = [l for l in lines if not l.startswith("#")]
            if len(non_heading_lines) < 5:
                failures.append(f"Content too sparse: only {len(non_heading_lines)} non-heading lines")

            # Emoji check
            if "emojis" in rules_dict and rules_dict["emojis"].value == "none":
                checks_run.append("no_emojis")
                import unicodedata

                emoji_count = sum(1 for c in content if unicodedata.category(c).startswith("So"))
                if emoji_count > 0:
                    failures.append(f"Emojis found ({emoji_count}) but doc type '{doc_type}' requires none")

            # Code blocks check
            if "code_blocks" in rules_dict:
                val = rules_dict["code_blocks"].value
                if val and val != "optional" and val != "none":
                    checks_run.append("code_blocks")
                    code_blocks = re.findall(r"```", content)
                    block_count = len(code_blocks) // 2
                    lo, _ = _parse_range(val)
                    if block_count < lo:
                        failures.append(f"Code blocks: {block_count} (expected >={lo})")
                elif val == "none":
                    checks_run.append("no_code_blocks")
                    code_blocks = re.findall(r"```", content)
                    if code_blocks:
                        failures.append(f"Code blocks found but doc type '{doc_type}' requires none")

            # Links check
            if "links" in rules_dict:
                val = rules_dict["links"].value
                if val and val != "optional" and val != "none":
                    checks_run.append("links")
                    links = re.findall(r"\[.*?\]\(.*?\)", content)
                    lo, _ = _parse_range(val)
                    if len(links) < lo:
                        failures.append(f"Links: {len(links)} (expected >={lo})")

            # File format check
            checks_run.append("file_format")
            expected_format = plan_data.get("output_format") or story.get("output_format", "markdown")
            if expected_format == "markdown" and not output_path.endswith((".md", ".markdown")):
                failures.append(f"Expected markdown file but got: {output_path}")
            elif expected_format == "html" and not output_path.endswith((".html", ".htm")):
                failures.append(f"Expected HTML file but got: {output_path}")

    # Record phase output
    passed = len(failures) == 0
    status = PhaseStatus.COMPLETE if passed else PhaseStatus.FAILED

    result_text = f"Doc type: {doc_type}\nChecks run: {', '.join(checks_run)}\n"
    if failures:
        result_text += f"Failures ({len(failures)}):\n" + "\n".join(f"  - {f}" for f in failures)
    else:
        result_text += "All mechanical checks passed."

    phase_output = PhaseOutput(
        phase="MECHANICAL_VERIFY",
        status=status,
        output=result_text,
        exit_code=0 if passed else 1,
        provider_used="local",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
    state["verify_passed"] = passed

    if not passed:
        state["failure_context"] = f"Mechanical verification failed:\n{result_text}"
        retry_count = state.get("phase_retry_count", 0)
        state["phase_retry_count"] = retry_count + 1

    if failures:
        logger.info(
            f"Story {story_id}: Mechanical verify FAILED "
            f"(doc_type={doc_type}, {len(checks_run)} checks, {len(failures)} failures: "
            f"{'; '.join(failures)})"
        )
    else:
        logger.info(f"Story {story_id}: Mechanical verify PASSED (doc_type={doc_type}, {len(checks_run)} checks)")
    return state


def mechanical_verify_decision(state: StoryState) -> str:
    """Route after MECHANICAL_VERIFY: pass → critic_review, fail → write."""
    verify_passed = state.get("verify_passed")
    retry_count = state.get("phase_retry_count", 0)

    if verify_passed:
        return "critic_review"
    elif retry_count >= MAX_VERIFY_RETRIES:
        logger.warning(f"Mechanical verify retry limit ({MAX_VERIFY_RETRIES}) reached, skipping to critic")
        return "critic_review"
    else:
        return "write"


def content_critic_node(state: StoryState, routing_engine=None) -> StoryState:
    """Critic review of content output against acceptance criteria."""
    state = dict(state)
    state["current_phase"] = "CRITIC_REVIEW"
    story = state["story"]
    story_id = story.get("id", "unknown")
    working_dir = state["working_directory"]

    story_acs = story.get("acceptanceCriteria", [])
    default_acs = get_default_acs("content")
    acceptance_criteria = merge_acs(story_acs, default_acs)

    # Get output content from the last CONTENT_WRITE phase output
    output_content = ""
    for po in reversed(state.get("phase_outputs", [])):
        if po.get("phase") == "CONTENT_WRITE" and po.get("output"):
            output_content = po["output"]
            break

    if not output_content:
        logger.warning(f"Story {story_id}: Content critic skipped — no CONTENT_WRITE output")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": "Skipped — no content"}
        phase_output = PhaseOutput(
            phase="CRITIC_REVIEW",
            status=PhaseStatus.SKIPPED,
            output="Skipped — no CONTENT_WRITE output.",
            exit_code=0,
            provider_used="none",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    task_description = state.get("task_description", story.get("description", ""))
    critic_retry_count = state.get("critic_retry_count", 0)
    critic = CriticAgent(mode="content_critic", routing_engine=routing_engine, escalation=critic_retry_count * 5)

    try:
        response = _run_async(
            critic.evaluate(
                acceptance_criteria=acceptance_criteria,
                output_content=output_content,
                task_description=task_description,
                working_directory=working_dir,
            ),
            timeout=180,
        )
    except (ValueError, RuntimeError) as e:
        logger.error(f"Story {story_id}: Content critic failed: {e}")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": f"Critic error: {e}"}
        phase_output = PhaseOutput(
            phase="CRITIC_REVIEW",
            status=PhaseStatus.FAILED,
            output=f"Critic error: {e}",
            exit_code=1,
            provider_used="content_critic",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    validation = validate_ratings(response, acceptance_criteria)
    state["critic_passed"] = validation.passed
    state["critic_ratings"] = [r.model_dump() for r in response.ratings]
    state["critic_average"] = validation.average
    state["critic_validation"] = {
        "passed": validation.passed,
        "missing_acs": validation.missing_acs,
        "failing_acs": validation.failing_acs,
        "average": validation.average,
        "message": validation.message,
    }

    status = PhaseStatus.COMPLETE if validation.passed else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="CRITIC_REVIEW",
        status=status,
        output=f"Content critic: {'PASSED' if validation.passed else 'FAILED'} avg={validation.average}",
        exit_code=0 if validation.passed else 1,
        provider_used="content_critic",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    if not validation.passed:
        state["critic_retry_count"] = critic_retry_count + 1
        failing_details = [
            f"  - {f['ac_id']} ({f['ac_name']}): {f['rating']}/10 — {f['justification']}"
            for f in validation.failing_acs
        ]
        # Include existing content for revision on retry
        content_preview = output_content[:10000]
        if len(output_content) > 10000:
            content_preview += "\n[...truncated...]"
        state["failure_context"] = (
            f"Critic failed (avg={validation.average}):\n{validation.message}\n"
            + "\n".join(failing_details)
            + f"\n\nExisting output to revise:\n```\n{content_preview}\n```"
        )
        logger.info(
            f"Story {story_id}: Content critic FAILED (avg={validation.average}, "
            f"retry {state['critic_retry_count']}/{MAX_CRITIC_RETRIES})"
        )
    else:
        logger.info(f"Story {story_id}: Content critic PASSED (avg={validation.average})")

    return state


def content_critic_decision(state: StoryState) -> str:
    """Route after content CRITIC_REVIEW: pass → learn, fail → write, max → fail."""
    if state.get("critic_passed"):
        return "learn"
    if state.get("critic_retry_count", 0) >= MAX_CRITIC_RETRIES:
        logger.warning(f"Content critic retry limit ({MAX_CRITIC_RETRIES}) reached — routing to learn")
        return "fail"
    return "write"


def _detect_output_path(state: dict, working_dir: str) -> str:
    """Try to detect the output file path from WRITE phase output."""
    for po in reversed(state.get("phase_outputs", [])):
        if po.get("phase") == "WRITE" and po.get("output"):
            output = po["output"]
            # Look for file paths in output
            try:
                from src.llm.response_parser import extract_json

                parsed = extract_json(output)
                if isinstance(parsed, dict):
                    # Check common keys
                    for key in ("output_path", "file_path", "path", "filesCreated"):
                        val = parsed.get(key)
                        if val:
                            if isinstance(val, list):
                                return val[0] if val else ""
                            return str(val)
            except Exception:
                pass

            # Try to find file paths in raw text
            matches = re.findall(r"[\w/.-]+\.(?:md|html|txt|rst)", output)
            if matches:
                return matches[0]
    return ""


class ContentWorkflow(BaseWorkflow):
    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        # PLAN: produces outline, Group 1 rules, Group 2 qualities
        builder.add_node(
            "plan", partial(phase_node, phase_name="CONTENT_PLAN", agent_name="content_planner", routing_engine=re)
        )

        # WRITE: produces the document
        builder.add_node(
            "write", partial(phase_node, phase_name="CONTENT_WRITE", agent_name="content_writer", routing_engine=re)
        )

        # MECHANICAL_VERIFY: automated checks (no LLM)
        builder.add_node("mechanical_verify", mechanical_verify_node)

        # CRITIC_REVIEW: CriticAgent evaluates against acceptance criteria
        builder.add_node("critic_review", partial(content_critic_node, routing_engine=re))

        # LEARN: extract learnings
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        # Edges
        builder.set_entry_point("plan")
        builder.add_edge("plan", "write")
        builder.add_edge("write", "mechanical_verify")

        # Mechanical verify → critic_review (pass) or write (fail, with retry limit)
        builder.add_conditional_edges(
            "mechanical_verify",
            mechanical_verify_decision,
            {"critic_review": "critic_review", "write": "write"},
        )

        # Critic review → learn (pass) or write (rework) or learn (max retries)
        builder.add_conditional_edges(
            "critic_review",
            content_critic_decision,
            {"learn": "learn", "write": "write", "fail": "learn"},
        )

        builder.add_edge("learn", END)

        return builder
