"""
Story Agent — Decompose a user request into atomic stories with dependencies.

Complexity: 7 (Decomposer). Produces stories with dependsOn arrays and
per-story complexity ratings for the routing engine.

Replaces the old core/story_agent.py with proper Pydantic validation
and dependency graph output.
"""

import json
import logging
from typing import Type, Optional
from pydantic import BaseModel

from src.agents.base_agent import BaseAgent
from src.llm.response_parser import DecomposeResponse
from src.execution.dag_executor import DAGExecutor, CircularDependencyError

logger = logging.getLogger(__name__)

# Valid story types — canonical lowercase names matching classify.md and WORKFLOW_MAP
STORY_TYPES = {
    "development", "config", "maintenance", "debug", "research", "review",
    "conversation",
    # Human story types (Phase 5 — not yet implemented)
    "assignment", "approval", "qa_feedback", "escalation",
}

# Map common aliases/variants to canonical names
_TYPE_MAP = {t: t for t in STORY_TYPES}
_TYPE_MAP.update({
    "dev": "development",
    "Dev": "development",
    "Development": "development",
    "Config": "config",
    "Maintenance": "maintenance",
    "Debug": "debug",
    "Research": "research",
    "Review": "review",
    "Conversation": "conversation",
    "Assignment": "assignment",
    "Approval": "approval",
    "QA_Feedback": "qa_feedback",
    "qa feedback": "qa_feedback",
    "Escalation": "escalation",
})


class StoryAgent(BaseAgent):

    @property
    def agent_name(self) -> str:
        return "decomposer"

    @property
    def response_model(self) -> Type[BaseModel]:
        return DecomposeResponse

    async def decompose(
        self,
        user_request: str,
        task_type: str,
        working_directory: str,
        existing_prd: Optional[dict] = None,
        existing_progress: Optional[dict] = None,
        rag_context: str = "",
    ) -> DecomposeResponse:
        """Decompose a user request into stories with dependencies.

        Returns DecomposeResponse with validated stories, each having:
        - id, title, description, type, tdd, status
        - dependsOn: list of story IDs this depends on
        - complexity: 1-10 rating for LLM routing
        - acceptanceCriteria: list of verifiable criteria
        """
        # Build context for decomposition
        context = {}

        if existing_prd:
            context["existing_prd"] = json.dumps(existing_prd, indent=2)

        if existing_progress:
            context["existing_progress"] = json.dumps(existing_progress, indent=2)

        if rag_context:
            context["rag_context"] = rag_context

        story = {
            "id": "DECOMPOSE",
            "title": "Task Decomposition",
            "description": f"Request: {user_request}\nType: {task_type}",
        }

        result = await self.execute(
            story=story,
            phase="DECOMPOSE",
            working_directory=working_directory,
            context=context,
        )

        # Normalize story types (case-insensitive matching)
        self._normalize_stories(result)

        # Validate dependency graph (topological sort, cycle detection)
        self._validate_dependencies(result)

        return result

    def _normalize_stories(self, response: DecomposeResponse):
        """Normalize story fields: map type aliases to canonical lowercase names."""
        for story in response.stories:
            # Try exact match first, then case-insensitive
            matched = _TYPE_MAP.get(story.type) or _TYPE_MAP.get(story.type.lower())
            if matched:
                story.type = matched
            else:
                logger.warning(f"Unknown story type '{story.type}' for {story.id}, defaulting to development")
                story.type = "development"

    def _validate_dependencies(self, response: DecomposeResponse):
        """Validate the dependency graph: no cycles, all refs valid."""
        story_ids = {s.id for s in response.stories}

        # Check all dependsOn references exist — fix on the Pydantic models directly
        for story in response.stories:
            invalid = [d for d in story.dependsOn if d not in story_ids]
            if invalid:
                logger.warning(
                    f"Story {story.id} depends on unknown stories {invalid}, removing"
                )
                story.dependsOn = [d for d in story.dependsOn if d in story_ids]

        # Check for circular dependencies
        try:
            stories_dicts = [s.model_dump() for s in response.stories]
            executor = DAGExecutor(stories_dicts)
            executor.topological_sort()
        except CircularDependencyError as e:
            logger.error(f"Circular dependency detected: {e}")
            # Break the cycle by removing all dependencies
            # This is a fallback — the LLM should produce valid graphs
            for story in response.stories:
                story.dependsOn = []
            logger.warning("Cleared all dependencies to break cycle")
