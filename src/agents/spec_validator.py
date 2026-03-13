"""
Spec Validator — Pre-processing validation of task specs before decomposition.

Runs BEFORE decomposition in the orchestrator pipeline. Validates task specs
for completeness and consistency using pure Python (no LLM needed).

Checks performed:
  a. Output path — does the task have an ## Output section with a file path?
  b. Acceptance criteria — does the task have checkbox items (- [ ])?
  c. Dependencies — are referenced tasks finished in the database?
  d. Output file existence — does the output file already exist (create vs edit)?
  e. Story type — is the specified story type valid?
"""

import logging
import os
import re
from dataclasses import dataclass, field

from src.agents.story_agent import STORY_TYPES

logger = logging.getLogger(__name__)


@dataclass
class SpecValidationResult:
    """Result of spec validation."""

    valid: bool = True  # True if all critical checks pass
    warnings: list[str] = field(default_factory=list)  # Non-blocking issues
    errors: list[str] = field(default_factory=list)  # Blocking issues
    metadata: dict = field(default_factory=dict)  # Extracted info


def validate_spec(
    task_content: str,
    db_manager=None,
) -> SpecValidationResult:
    """Validate a task spec for completeness and consistency.

    Args:
        task_content: Raw markdown content of the task file.
        db_manager: Optional DatabaseManager instance for dependency checks.

    Returns:
        SpecValidationResult with validation outcome and extracted metadata.
    """
    result = SpecValidationResult()
    result.metadata = {
        "output_path": None,
        "dependencies": [],
        "story_type": None,
        "has_existing_output": False,
        "acceptance_criteria_count": 0,
    }

    _check_output_section(task_content, result)
    _check_acceptance_criteria(task_content, result)
    _check_dependencies(task_content, result, db_manager)
    _check_output_file_existence(result)
    _check_story_type(task_content, result)

    # valid is True only if there are no errors
    result.valid = len(result.errors) == 0

    return result


def _check_output_section(task_content: str, result: SpecValidationResult):
    """Check for ## Output section with a file path."""
    # Detect story type early to allow assignment/human_task without ## Output
    type_match = re.search(
        r"^##\s+Story\s+Type\s*:?\s*\n?\s*(.+)",
        task_content,
        re.MULTILINE | re.IGNORECASE,
    )
    story_type = type_match.group(1).strip().lower() if type_match else None
    no_output_required = story_type in ("assignment", "human_task")

    # Match ## Output or ## Output: (case-insensitive)
    output_match = re.search(
        r"^##\s+Output\b[^\n]*\n(.*?)(?=^##\s|\Z)",
        task_content,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not output_match:
        if no_output_required:
            result.warnings.append("Missing '## Output' section (acceptable for assignment/human_task type)")
        else:
            result.errors.append("Missing '## Output' section in task spec")
        return

    output_body = output_match.group(1).strip()
    if not output_body:
        result.errors.append("'## Output' section is empty — no file path specified")
        return

    # Look for a file path: anything that looks like a path with / or extension
    path_match = re.search(
        r"(?:^|\s)(`?)([~/.][\w./_-]+\.\w+)\1",
        output_body,
    )
    if not path_match:
        # Also try lines that contain just a path-like string
        path_match = re.search(
            r"((?:/[\w._-]+)+(?:\.\w+)?)",
            output_body,
        )

    if path_match:
        raw_path = path_match.group(2) if path_match.lastindex and path_match.lastindex >= 2 else path_match.group(1)
        # Expand ~ if present
        output_path = os.path.expanduser(raw_path)
        result.metadata["output_path"] = output_path
    else:
        result.errors.append("'## Output' section does not contain a recognizable file path")


def _check_acceptance_criteria(task_content: str, result: SpecValidationResult):
    """Check for acceptance criteria (checkbox items)."""
    # Match markdown checkboxes: - [ ] or - [x]
    checkboxes = re.findall(r"^[\s]*-\s+\[[ xX]\]", task_content, re.MULTILINE)
    count = len(checkboxes)
    result.metadata["acceptance_criteria_count"] = count
    if count == 0:
        result.warnings.append("No acceptance criteria (checkbox items) found in task spec")


def _check_dependencies(
    task_content: str,
    result: SpecValidationResult,
    db_manager=None,
):
    """Check if declared dependencies are finished."""
    # Match ## Dependencies or ## Dependencies: section
    dep_match = re.search(
        r"^##\s+Dependencies\s*:?\s*\n(.*?)(?=^##\s|\Z)",
        task_content,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not dep_match:
        return  # No dependencies section — that's fine

    dep_body = dep_match.group(1).strip()
    if not dep_body or dep_body.lower() in ("none", "n/a", "-"):
        return

    # Extract task identifiers: T21, T22, or task names like 001_setup
    dep_ids = re.findall(r"[A-Za-z]?\d[\w_.-]*", dep_body)
    if not dep_ids:
        return

    result.metadata["dependencies"] = dep_ids

    if db_manager is None:
        result.warnings.append(f"Dependencies declared ({', '.join(dep_ids)}) but no database available to verify")
        return

    unmet = []
    for dep_id in dep_ids:
        task_state = db_manager.find_task_state_by_name(dep_id)
        if task_state is None:
            unmet.append(f"{dep_id} (not found in database)")
        elif task_state.get("status") != "finished":
            unmet.append(f"{dep_id} (status: {task_state.get('status', 'unknown')})")

    if unmet:
        result.errors.append(f"Unmet dependencies: {', '.join(unmet)}")


def _check_output_file_existence(result: SpecValidationResult):
    """Check if the output file already exists (create vs edit signal)."""
    output_path = result.metadata.get("output_path")
    if not output_path:
        return

    if os.path.exists(output_path):
        result.metadata["has_existing_output"] = True
        logger.info(f"Output file already exists: {output_path} (flagged as potential edit task)")


def _check_story_type(task_content: str, result: SpecValidationResult):
    """Check if Story Type is valid."""
    type_match = re.search(
        r"^##\s+Story\s+Type\s*:?\s*\n?\s*(.+)",
        task_content,
        re.MULTILINE | re.IGNORECASE,
    )
    if not type_match:
        return  # No story type specified — that's fine, classifier will decide

    raw_type = type_match.group(1).strip().lower()
    result.metadata["story_type"] = raw_type

    if raw_type not in STORY_TYPES:
        result.warnings.append(f"Story type '{raw_type}' is not in valid types: {sorted(STORY_TYPES)}")
