"""
Core Memory Writer — Persist learnings to the 5-level memory hierarchy.

Levels 1-3 are file-based (global, tech_stack, project).
Level 4 (task) is embedded in checkpoint data.
Level 5 (story) is embedded in vector store via RAG.

This module handles Levels 1-3: append new learnings to the appropriate
memory file, and auto-summarize when the file exceeds its token budget.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Token budgets per level (chars ≈ tokens * 3.5)
LEVEL_BUDGETS = {
    "global": 2000,      # tokens
    "tech_stack": 1000,
    "project": 2000,
}

LEVEL_PATHS = {
    "global": os.path.expanduser("~/.config/sat/global.md"),
    # tech_stack and project are relative to working_directory
}


def _get_path(level: str, working_directory: str) -> str:
    """Get the file path for a memory level."""
    if level == "global":
        return LEVEL_PATHS["global"]
    elif level == "tech_stack":
        return os.path.join(working_directory, ".memory", "tech_stack.md")
    elif level == "project":
        return os.path.join(working_directory, ".memory", "project.md")
    raise ValueError(f"Unknown memory level: {level}")


def _estimate_tokens(text: str) -> int:
    """Approximate token count."""
    return int(len(text) / 3.5)


def append_learning(
    level: str,
    content: str,
    working_directory: str,
    tech_stack: Optional[list] = None,
) -> bool:
    """Append a learning to the appropriate memory file.

    Args:
        level: One of "global", "tech_stack", "project"
        content: The learning text to append
        working_directory: Project working directory
        tech_stack: Optional tech stack tags for tech_stack level

    Returns:
        True if successfully written
    """
    if level not in LEVEL_BUDGETS:
        logger.warning(f"Unknown memory level: {level}")
        return False

    path = _get_path(level, working_directory)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        existing = ""
        if os.path.exists(path):
            with open(path, "r") as f:
                existing = f.read()

        # Check for duplicate content (simple substring check)
        if content.strip() in existing:
            logger.debug(f"Duplicate learning skipped for {level}")
            return False

        # Append
        new_content = existing.rstrip() + "\n\n" + content.strip() + "\n" if existing else content.strip() + "\n"

        # Check budget and truncate from the top if over
        budget = LEVEL_BUDGETS[level]
        if _estimate_tokens(new_content) > budget:
            max_chars = int(budget * 3.5)
            # Keep the newest content (from the end)
            new_content = "...\n" + new_content[-max_chars:]
            logger.info(f"Memory {level} exceeded budget, trimmed to {budget} tokens")

        with open(path, "w") as f:
            f.write(new_content)

        logger.info(f"Learning appended to {level} memory: {path}")
        return True

    except Exception as e:
        logger.warning(f"Failed to write {level} memory: {e}")
        return False


def process_learn_output(learn_json: dict, working_directory: str):
    """Process LEARN phase JSON output and route learnings to appropriate memory files.

    Expected format matches the learn.md template output:
    {
        "learnings": [{"level": "project", "title": "...", "description": "...", "techStack": [...]}],
        "recommendedRules": [{"rule": "...", "level": "project", "reason": "...", "techStack": [...]}]
    }
    """
    learnings = learn_json.get("learnings", [])
    rules = learn_json.get("recommendedRules", [])

    for learning in learnings:
        level = learning.get("level", "story")
        if level in ("global", "tech_stack", "project"):
            title = learning.get("title", "")
            desc = learning.get("description", "")
            tech = learning.get("techStack", [])
            tech_str = f" [{', '.join(tech)}]" if tech else ""
            content = f"- **{title}**{tech_str}: {desc}"
            append_learning(level, content, working_directory, tech)

    for rule in rules:
        level = rule.get("level", "project")
        if level in ("global", "tech_stack", "project"):
            rule_text = rule.get("rule", "")
            reason = rule.get("reason", "")
            tech = rule.get("techStack", [])
            tech_str = f" [{', '.join(tech)}]" if tech else ""
            content = f"- **Rule**{tech_str}: {rule_text} — {reason}"
            append_learning(level, content, working_directory, tech)
