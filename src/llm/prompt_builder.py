"""
Prompt Builder — Template loading, placeholder substitution, context injection.

Ported from Ralph Pro buildStoryPrompt (lines 605-754).
Implements progressive disclosure: each phase gets only relevant context.
"""

import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

# Phase-to-template mapping
PHASE_TEMPLATES: dict[str, str] = {
    "DESIGN": "design.md",
    "ARCHITECT_CODE": "design.md",
    "PLAN_CODE": "plan.md",
    "TEST_WRITER": "tdd_red.md",
    "TDD_RED": "tdd_red.md",
    "CODE": "code.md",
    "VERIFY": "verify.md",
    "LEARN": "learn.md",
    "PLAN": "plan.md",
    "EXECUTE": "execute.md",
    "VERIFY_SCRIPT": "verify_script.md",
    "MEDIATOR": "mediator.md",
    "CLASSIFY": "classify.md",
    "DECOMPOSE": "decompose.md",
    "DIAGNOSE": "diagnose.md",
    "REPRODUCE": "reproduce.md",
    "FIX": "code.md",  # Same template as CODE
    "GATHER": "gather.md",
    "ANALYZE": "analyze.md",
    "SYNTHESIZE": "synthesize.md",
    "REVIEW": "review.md",
    "REPORT": "report.md",
    "PRD_DISCOVERY": "prd_discovery.md",
    "PRD_SINGLE_PHASE": "prd_single_phase.md",
    "PRD_REQUIREMENTS": "prd_requirements.md",
    "PRD_ARCHITECTURE": "prd_architecture.md",
    "PRD_IMPLEMENTATION": "prd_implementation.md",
    "VERIFY_LINT": "verify.md",
    "VERIFY_TEST": "verify.md",
    "VERIFY_SECURITY": "verify.md",
    "VERIFY_ARCH": "verify.md",
}

# Progressive disclosure: what context each phase receives
# Keys are phase names, values are lists of state fields to include
PHASE_CONTEXT: dict[str, list[str]] = {
    "DESIGN": ["task_description", "acceptance_criteria", "rag_context"],
    "ARCHITECT_CODE": ["task_description", "acceptance_criteria", "rag_context"],
    "PLAN_CODE": ["design_output", "acceptance_criteria"],
    "TEST_WRITER": ["design_output", "acceptance_criteria"],
    "TDD_RED": ["design_output", "acceptance_criteria"],
    "CODE": ["design_output", "test_files", "acceptance_criteria", "failure_context"],
    "VERIFY": ["diff", "test_results", "acceptance_criteria"],
    "LEARN": ["phase_summary"],
    "PLAN": ["task_description", "acceptance_criteria", "rag_context"],
    "EXECUTE": ["plan_output", "acceptance_criteria", "failure_context"],
    "VERIFY_SCRIPT": ["plan_output", "diff", "acceptance_criteria"],
    "DIAGNOSE": ["task_description", "failure_context"],
    "REPRODUCE": ["failure_context", "diagnose_output"],
    "FIX": ["design_output", "test_files", "acceptance_criteria", "failure_context"],
    "GATHER": ["task_description"],
    "ANALYZE": ["gather_output"],
    "SYNTHESIZE": ["analyze_output"],
    "REVIEW": ["task_description"],
    "REPORT": ["review_output"],
    "VERIFY_LINT": ["diff", "test_results", "acceptance_criteria"],
    "VERIFY_TEST": ["diff", "test_results", "acceptance_criteria"],
    "VERIFY_SECURITY": ["diff", "test_results", "acceptance_criteria"],
    "VERIFY_ARCH": ["diff", "test_results", "acceptance_criteria"],
}


def load_template(phase: str, template_dir: Optional[str] = None) -> Optional[str]:
    """Load a prompt template for a phase.

    Args:
        phase: Phase name (e.g., "DESIGN", "CODE")
        template_dir: Override template directory

    Returns:
        Template content as string, or None if not found
    """
    tdir = template_dir or TEMPLATE_DIR
    template_name = PHASE_TEMPLATES.get(phase)

    if not template_name:
        logger.warning(f"No template mapping for phase: {phase}")
        return None

    path = os.path.join(tdir, template_name)
    if not os.path.exists(path):
        logger.warning(f"Template not found: {path}")
        return None

    with open(path, "r") as f:
        return f.read()


def substitute_placeholders(template: str, context: dict) -> str:
    """Replace {{KEY}} placeholders in template with context values.

    Args:
        template: Template string with {{KEY}} placeholders
        context: Dict of key-value pairs for substitution

    Returns:
        Template with placeholders replaced
    """
    result = template
    for key, value in context.items():
        placeholder = "{{" + key.upper() + "}}"
        result = result.replace(placeholder, str(value) if value else "")
    return result


def _load_project_rules(working_directory: str) -> str:
    """Load CLAUDE.md from project root for global rules injection."""
    claude_md = os.path.join(working_directory, "CLAUDE.md")
    if os.path.exists(claude_md):
        try:
            with open(claude_md, "r") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to read CLAUDE.md: {e}")
    return ""


def _format_acceptance_criteria(criteria: list) -> str:
    """Format acceptance criteria as a numbered list."""
    if not criteria:
        return "No acceptance criteria specified."
    return "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))


def build_prompt(
    story: dict,
    phase: str,
    working_directory: str,
    context: dict = None,
    template_dir: Optional[str] = None,
) -> str:
    """Build a complete prompt for a phase execution.

    Applies progressive disclosure: only includes context relevant to the phase.

    Args:
        story: Story dict with id, title, description, acceptanceCriteria, etc.
        phase: Phase name
        working_directory: Project working directory
        context: Additional context dict (phase_outputs, diffs, test results, etc.)
        template_dir: Override template directory

    Returns:
        Complete prompt string ready for LLM invocation
    """
    ctx = context or {}

    # Load template
    template = load_template(phase, template_dir)

    if template:
        # Build substitution context
        subs = {
            "STORY_ID": story.get("id", ""),
            "STORY_TITLE": story.get("title", ""),
            "STORY_DESCRIPTION": story.get("description", ""),
            "ACCEPTANCE_CRITERIA": _format_acceptance_criteria(story.get("acceptanceCriteria", [])),
            "PHASE_NAME": phase,
            "AGENT_NAME": f"{phase} Agent",
        }

        # Add progressive disclosure context
        allowed_context = PHASE_CONTEXT.get(phase, [])
        for key in allowed_context:
            if key in ctx and ctx[key]:
                subs[key.upper()] = str(ctx[key])

        # Add failure context if retrying
        if "failure_context" in ctx and ctx["failure_context"]:
            subs["FAILED_CONTEXT"] = ctx["failure_context"]

        # Substitute placeholders
        prompt = substitute_placeholders(template, subs)
    else:
        # Inline fallback prompt
        prompt = _build_inline_prompt(story, phase, ctx)

    # Inject project rules (CLAUDE.md) — skip for classification/decomposition phases
    # (they operate on task metadata, not project code)
    if phase not in ("CLASSIFY", "DECOMPOSE", "LEARN"):
        project_rules = _load_project_rules(working_directory)
        if project_rules:
            prompt = f"## Project Rules\n\n{project_rules}\n\n---\n\n{prompt}"

    return prompt


def _build_inline_prompt(story: dict, phase: str, context: dict) -> str:
    """Generate a basic prompt when template file is missing."""
    parts = [
        f"# {phase} Phase",
        f"\n## Story: {story.get('title', 'Unknown')}",
        f"\n**ID:** {story.get('id', 'N/A')}",
        f"\n**Description:** {story.get('description', 'No description')}",
        f"\n**Acceptance Criteria:**\n{_format_acceptance_criteria(story.get('acceptanceCriteria', []))}",
    ]

    if "failure_context" in context and context["failure_context"]:
        parts.append(f"\n## Previous Failure\n{context['failure_context']}")

    if "design_output" in context and context["design_output"]:
        parts.append(f"\n## Architecture\n{context['design_output']}")

    parts.append(f"\n## Instructions\nExecute the {phase} phase for this story. Output your response as JSON.")

    return "\n".join(parts)
