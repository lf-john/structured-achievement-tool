"""
Prompt Builder — Template loading, placeholder substitution, context injection.

Ported from Ralph Pro buildStoryPrompt (lines 605-754).
Implements progressive disclosure: each phase gets only relevant context.
"""

import logging
import os
import re

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
    "GATHER_WEB": "gather.md",
    "GATHER_CODE": "gather.md",
    "GATHER_DOCS": "gather.md",
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
    "CONTENT_PLAN": "content_plan.md",
    "CONTENT_WRITE": "content_write.md",
    "AGENTIC_VERIFY": "agentic_verify.md",
    # Document assembly workflow phases
    "GATHER_INPUTS": "gather.md",
    "DESIGN_LAYOUT": "design.md",
    "REQUEST_IMAGES": "execute.md",
    "ASSEMBLE": "execute.md",
    "QUALITY_CHECK": "verify.md",
    # Task verification workflow phases
    "GATHER_OUTPUTS": "gather.md",
    "VERIFY_ACS": "verify.md",
    # Debug workflow phases
    "VALIDATE_FIX": "verify.md",
    # Config/maintenance workflow phases
    "PROPAGATION_WAIT": "execute.md",
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
    "CONTENT_PLAN": ["task_description", "acceptance_criteria", "rag_context"],
    "CONTENT_WRITE": ["plan_output", "acceptance_criteria", "failure_context"],
    "AGENTIC_VERIFY": ["plan_output", "acceptance_criteria"],
    # Document assembly workflow phases
    "GATHER_INPUTS": ["task_description", "acceptance_criteria"],
    "DESIGN_LAYOUT": ["task_description", "acceptance_criteria", "gather_output"],
    "REQUEST_IMAGES": ["task_description", "design_output"],
    "ASSEMBLE": ["task_description", "design_output", "acceptance_criteria", "failure_context"],
    "QUALITY_CHECK": ["acceptance_criteria", "diff"],
    # Task verification workflow phases
    "GATHER_OUTPUTS": ["task_description", "phase_summary"],
    "VERIFY_ACS": ["task_description", "acceptance_criteria"],
    # Debug workflow phases
    "VALIDATE_FIX": ["failure_context", "diff", "test_results"],
    # Config/maintenance workflow phases
    "PROPAGATION_WAIT": [],
}


# TACHES-adapted deviation rules (Enhancement #6)
# Non-debug workflows: auto-fix (rules 1-3), log enhancements (rule 5), never stop.
# Debug workflow: includes rule 4 (ask before architectural changes).
DEVIATION_RULES = """## Scope & Deviation Rules
You MUST follow these deviation rules exactly:

1. **Auto-fix bugs** — If code doesn't work as intended, fix it immediately. Run tests after. Track what you changed.
2. **Auto-add critical** — If something essential for correctness or security is missing, add it immediately. Run tests after. Track what you added.
3. **Auto-fix blockers** — If something prevents completing the current task, fix it immediately. Track what you changed.
4. **Log enhancements** — If you notice a non-critical improvement opportunity, do NOT implement it. Instead, note it in your output under an "enhancements_noted" field and continue with the current task.
5. **Stay in scope** — Do not add features, refactor unrelated code, change file structure, or install packages beyond what the acceptance criteria require. If blocked, report the blocker.
"""

DEVIATION_RULES_DEBUG = """## Scope & Deviation Rules (Debug)
You MUST follow these deviation rules exactly:

1. **Auto-fix bugs** — If code doesn't work as intended, fix it immediately. Run tests after. Track what you changed.
2. **Auto-add critical** — If something essential for correctness or security is missing, add it immediately. Run tests after. Track what you added.
3. **Auto-fix blockers** — If something prevents completing the current task, fix it immediately. Track what you changed.
4. **ASK before architecture changes** — If a fix requires significant structural modification (new files, changed interfaces, moved responsibilities), STOP. Report the proposed change in your output under a "architecture_change_proposed" field with your reasoning. Do NOT implement it without approval.
5. **Log enhancements** — If you notice a non-critical improvement, note it in "enhancements_noted" and continue.
6. **Stay in scope** — Do not add features, refactor unrelated code, change file structure, or install packages beyond what the acceptance criteria require.
"""

# Phases that receive deviation rules (agentic, code-producing)
_AGENTIC_PHASES = {"CODE", "EXECUTE", "FIX", "PLAN", "PLAN_CODE"}
# Debug workflow phases get the debug variant (includes architecture-ask rule)
_DEBUG_PHASES = {"DIAGNOSE", "REPRODUCE", "FIX"}


def _estimate_tokens(text: str) -> int:
    """Approximate token count (chars / 3.5 for English text)."""
    return int(len(text) / 3.5)


# Model-specific context budget ratios based on research:
# - Claude: strong on long context, tolerates higher fill (0.60)
# - Gemini: begins confusing past/current info at ~20% — use conservative budget (0.40)
# - Local/Ollama: 50% is the empirical sweet spot for smaller models
PROVIDER_BUDGET_RATIOS = {
    "claude": 0.60,
    "gemini": 0.40,
    "ollama": 0.50,
}
DEFAULT_BUDGET_RATIO = 0.50


def get_budget_ratio(provider_name: str = "") -> float:
    """Get the context budget ratio for a provider.

    Args:
        provider_name: Provider name from routing engine (e.g., "sonnet", "gemini_flash")
    """
    name_lower = provider_name.lower()
    if any(c in name_lower for c in ("opus", "sonnet", "haiku", "claude")):
        return PROVIDER_BUDGET_RATIOS["claude"]
    elif any(g in name_lower for g in ("gemini", "glm")):
        return PROVIDER_BUDGET_RATIOS["gemini"]
    elif any(o in name_lower for o in ("qwen", "deepseek", "nemotron", "ollama")):
        return PROVIDER_BUDGET_RATIOS["ollama"]
    return DEFAULT_BUDGET_RATIO


def trim_to_budget(
    prompt: str,
    max_tokens: int,
    budget_ratio: float = 0.50,
    provider_name: str = "",
) -> str:
    """Trim prompt to stay within context budget.

    Removes lowest-priority sections first:
    1. RAG context ({{RAG_CONTEXT}} blocks)
    2. Prior phase outputs ({{DESIGN_OUTPUT}}, etc.)
    3. Failure context

    System instructions and task description are never trimmed.

    Args:
        prompt: Full assembled prompt
        max_tokens: Target model's context window in tokens
        budget_ratio: Maximum fraction of context window to use (default 0.50).
                      Overridden by provider_name if provided.
        provider_name: If provided, uses model-specific budget ratio instead.
    """
    if provider_name:
        budget_ratio = get_budget_ratio(provider_name)
    budget = int(max_tokens * budget_ratio)
    current_tokens = _estimate_tokens(prompt)

    if current_tokens <= budget:
        return prompt

    logger.info(
        f"Prompt exceeds context budget: ~{current_tokens} tokens vs {budget} budget "
        f"({max_tokens} window * {budget_ratio}). Trimming."
    )

    # Trim in priority order (lowest priority first)
    # Section markers to look for in the assembled prompt
    trim_sections = [
        ("RAG context", "## Retrieved Context", "---"),
        ("Prior phase output", "## Architecture", "---"),
        ("Prior phase output", "## Previous Output", "---"),
        ("Failure context", "<prior-failure>", "</prior-failure>"),
    ]

    result = prompt
    for label, start_marker, end_marker in trim_sections:
        if _estimate_tokens(result) <= budget:
            break
        start_idx = result.find(start_marker)
        if start_idx == -1:
            continue
        end_idx = result.find(end_marker, start_idx + len(start_marker))
        if end_idx == -1:
            # Remove from marker to end
            result = result[:start_idx] + f"\n[{label} trimmed for context budget]\n"
        else:
            result = (
                result[:start_idx] + f"\n[{label} trimmed for context budget]\n" + result[end_idx + len(end_marker) :]
            )
        logger.info(f"Trimmed {label} from prompt")

    final_tokens = _estimate_tokens(result)
    if final_tokens > budget:
        logger.warning(f"Prompt still exceeds budget after trimming: ~{final_tokens} vs {budget}")

    return result


def _extract_template_version(content: str) -> str:
    """Extract version from template header comment.

    Templates may start with a version comment: <!-- version: 1.0 -->
    Returns the version string or "1.0" if no version comment found.
    """
    match = re.match(r"^\s*<!--\s*version:\s*(\S+)\s*-->", content)
    return match.group(1) if match else "1.0"


# Cache of template versions for event logging
_template_versions: dict[str, str] = {}


def get_template_version(phase: str) -> str:
    """Get the current version of a template for a given phase.

    Used by the event logger to correlate template versions with G-Eval scores.
    """
    return _template_versions.get(phase, "1.0")


def load_template(phase: str, template_dir: str | None = None) -> str | None:
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

    with open(path) as f:
        content = f.read()

    # Extract and cache version
    version = _extract_template_version(content)
    _template_versions[phase] = version

    return content


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
            with open(claude_md) as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to read CLAUDE.md: {e}")
    return ""


# Core Memory token budgets per level
_CORE_MEMORY_LIMITS = {
    "global": 2000,  # ~/.config/sat/global.md
    "tech_stack": 1000,  # {project}/.memory/tech_stack.md
    "project": 2000,  # {project}/.memory/project.md
}


def _load_core_memory(working_directory: str) -> str:
    """Load multi-level core memory (Levels 1-3) for prompt injection.

    Level 1: Global   — ~/.config/sat/global.md (all projects)
    Level 2: Tech Stack — {project}/.memory/tech_stack.md (language/framework)
    Level 3: Project  — {project}/.memory/project.md (architecture, patterns)

    Levels 4-5 (Task, Story) are retrieved via RAG, not injected here.
    Each level is trimmed to its token budget to keep prompts concise.
    """
    parts = []
    memory_files = [
        ("global", os.path.expanduser("~/.config/sat/global.md")),
        ("tech_stack", os.path.join(working_directory, ".memory", "tech_stack.md")),
        ("project", os.path.join(working_directory, ".memory", "project.md")),
    ]

    for level, path in memory_files:
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                content = f.read().strip()
            if not content:
                continue
            # Trim to budget
            budget = _CORE_MEMORY_LIMITS.get(level, 1000)
            max_chars = int(budget * 3.5)  # Inverse of _estimate_tokens
            if len(content) > max_chars:
                content = content[:max_chars] + "\n[...truncated to token budget]"
            parts.append(f"### Core Memory: {level.replace('_', ' ').title()}\n{content}")
        except Exception as e:
            logger.debug(f"Failed to load core memory {level}: {e}")

    if not parts:
        return ""
    return "## Core Memory\n\n" + "\n\n".join(parts)


def _format_acceptance_criteria(criteria: list) -> str:
    """Format acceptance criteria as a numbered list."""
    if not criteria:
        return "No acceptance criteria specified."
    return "\n".join(f"{i + 1}. {c}" for i, c in enumerate(criteria))


def build_prompt(
    story: dict,
    phase: str,
    working_directory: str,
    context: dict = None,
    template_dir: str | None = None,
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
        # Build substitution context — wrap untrusted user content in delimiters
        # to defend against prompt injection from task file content.
        raw_description = story.get("description", "")
        raw_title = story.get("title", "")
        subs = {
            "STORY_ID": story.get("id", ""),
            "STORY_TITLE": raw_title,
            "STORY_DESCRIPTION": f"<user-task>\n{raw_description}\n</user-task>" if raw_description else "",
            "ACCEPTANCE_CRITERIA": _format_acceptance_criteria(story.get("acceptanceCriteria", [])),
            "PHASE_NAME": phase,
            "AGENT_NAME": f"{phase} Agent",
        }

        # Inject project rules for CLASSIFY so it can respect project-level
        # type hints (e.g., "all tasks are content" in a non-code project).
        if phase == "CLASSIFY":
            project_rules = _load_project_rules(working_directory)
            subs["PROJECT_RULES"] = project_rules or "(none)"

        # Add progressive disclosure context
        allowed_context = PHASE_CONTEXT.get(phase, [])
        for key in allowed_context:
            if ctx.get(key):
                subs[key.upper()] = str(ctx[key])

        # Inject doc-type-specific verification criteria for content phases
        if phase in ("AGENTIC_VERIFY", "CONTENT_WRITE"):
            try:
                from src.workflows.content_models import (
                    format_group1_for_prompt,
                    format_group2_for_prompt,
                    get_qualities_for_doc_type,
                    get_rules_for_doc_type,
                )

                # Extract doc_type from plan output or story
                doc_type = story.get("doc_type", "technical")
                plan_output = ctx.get("plan_output", "")
                if plan_output:
                    try:
                        from src.llm.response_parser import extract_json

                        parsed = extract_json(plan_output)
                        if isinstance(parsed, dict) and parsed.get("doc_type"):
                            doc_type = parsed["doc_type"]
                    except Exception:
                        pass
                if phase == "AGENTIC_VERIFY":
                    qualities = get_qualities_for_doc_type(doc_type)
                    subs["GROUP2_QUALITIES"] = format_group2_for_prompt(qualities)
                elif phase == "CONTENT_WRITE":
                    rules = get_rules_for_doc_type(doc_type)
                    subs.setdefault("GROUP1_RULES", format_group1_for_prompt(rules))
                    qualities = get_qualities_for_doc_type(doc_type)
                    subs.setdefault("GROUP2_QUALITIES", format_group2_for_prompt(qualities))
            except Exception as e:
                logger.warning(f"Failed to inject content criteria for {phase}: {e}")

        # Inject tech stack detection for phases that need it
        if phase in ("TDD_RED", "TEST_WRITER", "CODE", "FIX"):
            from src.execution.tech_stack import detect_tech_stack, get_existing_test_files

            stack = detect_tech_stack(working_directory)
            subs.setdefault("LANGUAGE", stack.language)
            subs.setdefault("TEST_FRAMEWORK", stack.test_framework)
            subs.setdefault("TEST_DIRECTORY", stack.test_directory)
            # List existing test files for TDD_RED/TEST_WRITER
            if phase in ("TDD_RED", "TEST_WRITER"):
                existing = get_existing_test_files(working_directory, stack.test_directory)
                if existing:
                    subs["EXISTING_TEST_FILES"] = "\n".join(f"- `{f}`" for f in existing)
                else:
                    subs["EXISTING_TEST_FILES"] = "No existing test files found."

        # Add failure context if retrying — wrap in delimiters since it may
        # contain prior LLM output or error messages from external processes
        if ctx.get("failure_context"):
            subs["FAILED_CONTEXT"] = f"<prior-failure>\n{ctx['failure_context']}\n</prior-failure>"

        # Wrap human response content if present
        if ctx.get("human_response"):
            subs["HUMAN_RESPONSE"] = f"<human-response>\n{ctx['human_response']}\n</human-response>"

        # Substitute placeholders
        prompt = substitute_placeholders(template, subs)
    else:
        # Inline fallback prompt
        prompt = _build_inline_prompt(story, phase, ctx)

    # Inject deviation rules for agentic phases (Enhancement #6, TACHES-adapted)
    if phase in _DEBUG_PHASES:
        prompt = f"{DEVIATION_RULES_DEBUG}\n{prompt}"
    elif phase in _AGENTIC_PHASES:
        prompt = f"{DEVIATION_RULES}\n{prompt}"

    # Inject project rules (CLAUDE.md) — skip for classification/decomposition phases
    # (they operate on task metadata, not project code)
    if phase not in ("CLASSIFY", "DECOMPOSE", "LEARN"):
        project_rules = _load_project_rules(working_directory)
        if project_rules:
            prompt = f"## Project Rules\n\n{project_rules}\n\n---\n\n{prompt}"

    # Inject core memory (Levels 1-3) after project rules, before the main prompt.
    # Skip for CLASSIFY/DECOMPOSE (metadata phases) and LEARN (extracting, not consuming).
    if phase not in ("CLASSIFY", "DECOMPOSE", "LEARN"):
        core_memory = _load_core_memory(working_directory)
        if core_memory:
            prompt = f"{core_memory}\n\n---\n\n{prompt}"

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

    if context.get("failure_context"):
        parts.append(f"\n## Previous Failure\n{context['failure_context']}")

    if context.get("design_output"):
        parts.append(f"\n## Architecture\n{context['design_output']}")

    parts.append(f"\n## Instructions\nExecute the {phase} phase for this story. Output your response as JSON.")

    return "\n".join(parts)
