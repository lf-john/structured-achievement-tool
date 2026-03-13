"""
Classifier Agent — Classify a user request into a workflow type.

Complexity: 3 (Classification task). Routes to local models.

Supports both task-level classification (whole request) and story-level
classification (individual stories after decomposition).

Sub-classification: determines operation_mode ("create" vs "edit") by checking
for edit-indicating keywords in the description AND verifying the target output
file already exists on disk. Both conditions must be true for "edit" mode.
"""

import logging
import os
import re

from pydantic import BaseModel

from src.agents.base_agent import BaseAgent
from src.llm.response_parser import ClassifyResponse

logger = logging.getLogger(__name__)

# Keywords that suggest an edit/modification operation (case-insensitive)
EDIT_KEYWORDS = re.compile(
    r"\b(fix|update|modify|replace|change|edit|rewrite|correct|patch|revise)\b",
    re.IGNORECASE,
)


def detect_operation_mode(description: str, output_path: str | None, working_directory: str) -> str:
    """Determine whether a story is a 'create' or 'edit' operation.

    Both conditions must be true for "edit":
    1. The description contains edit-indicating keywords
    2. The output file already exists on disk

    Args:
        description: Story/task description text.
        output_path: Expected output file path (absolute or relative).
        working_directory: Working directory for resolving relative paths.

    Returns:
        "edit" if both conditions met, otherwise "create".
    """
    # Condition 1: edit keywords present
    if not EDIT_KEYWORDS.search(description):
        return "create"

    # Condition 2: output file exists
    if not output_path:
        return "create"

    resolved = output_path if os.path.isabs(output_path) else os.path.join(working_directory, output_path)
    if os.path.exists(resolved):
        logger.info(f"Operation mode: edit (keyword match + file exists: {resolved})")
        return "edit"

    return "create"


def _extract_output_path(description: str) -> str | None:
    """Try to extract a file path from the description text.

    Looks for common path patterns mentioned in the request.
    """
    # Match absolute paths or relative paths with file extensions
    patterns = [
        r"(?:^|[\s\"'`(])(/[\w./-]+\.\w+)",  # absolute: /some/path/file.ext
        r"(?:^|[\s\"'`(])(\.?\.?/[\w./-]+\.\w+)",  # relative: ./foo.py or ../foo.py
        r"(?:^|[\s\"'`(])((?:src|tests|config|scripts|docs|output|build|templates)/[\w./-]+\.\w+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, description)
        if match:
            return match.group(1)
    return None


class ClassifierAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "classifier"

    @property
    def response_model(self) -> type[BaseModel]:
        return ClassifyResponse

    async def classify(self, user_request: str, working_directory: str) -> ClassifyResponse:
        """Classify a user request into a workflow type.

        Returns ClassifyResponse with task_type, operation_mode, confidence, reasoning.

        After the LLM determines the primary task_type, this method applies
        rule-based post-processing to determine operation_mode:
        - Checks for edit-indicating keywords in the description
        - Checks if the target output file already exists on disk
        - Both must be true for operation_mode="edit"
        """
        story = {
            "id": "CLASSIFY",
            "title": "Task Classification",
            "description": user_request,
        }

        result = await self.execute(
            story=story,
            phase="CLASSIFY",
            working_directory=working_directory,
        )

        # Post-process: determine operation_mode from description + file existence
        output_path = _extract_output_path(user_request)
        operation_mode = detect_operation_mode(user_request, output_path, working_directory)
        result.operation_mode = operation_mode

        return result

    async def classify_story(
        self,
        story_id: str,
        story_title: str,
        story_description: str,
        acceptance_criteria: list[str],
        output_path: str | None,
        suggested_type: str,
        working_directory: str,
    ) -> ClassifyResponse:
        """Classify a single story based on its specific details.

        Builds a rich description from the story's fields so the classifier
        can make an informed per-story decision.  The suggested_type from the
        decomposer is included as a hint but not binding.

        Also determines operation_mode using rule-based detection.

        Args:
            story_id: Story identifier (e.g. "S1").
            story_title: Short story title.
            story_description: Full story description.
            acceptance_criteria: List of acceptance criteria strings.
            output_path: Expected output file path, if any.
            suggested_type: Type suggested by the decomposer (used as hint).
            working_directory: Project working directory.

        Returns:
            ClassifyResponse with task_type, operation_mode, confidence, reasoning.
        """
        # Build a composite description that gives the classifier full context
        parts = [
            f"Story: {story_title}",
            f"Description: {story_description}",
        ]
        if acceptance_criteria:
            parts.append("Acceptance Criteria:")
            for ac in acceptance_criteria:
                parts.append(f"  - {ac}")
        if output_path:
            parts.append(f"Output path: {output_path}")
        parts.append(f"Suggested type (from decomposer, may be overridden): {suggested_type}")

        composite = "\n".join(parts)

        story = {
            "id": f"CLASSIFY_{story_id}",
            "title": f"Story Classification: {story_title}",
            "description": composite,
        }

        result = await self.execute(
            story=story,
            phase="CLASSIFY",
            working_directory=working_directory,
        )

        # Post-process: determine operation_mode
        effective_path = output_path or _extract_output_path(story_description)
        operation_mode = detect_operation_mode(story_description, effective_path, working_directory)
        result.operation_mode = operation_mode

        return result
