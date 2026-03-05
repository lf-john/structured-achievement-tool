"""
Story Agent — Decompose a user request into atomic stories with dependencies.

Complexity: 7 (Decomposer). Produces stories with dependsOn arrays and
per-story complexity ratings for the routing engine.

Replaces the old core/story_agent.py with proper Pydantic validation
and dependency graph output.
"""

import json
import logging

from pydantic import BaseModel

from src.agents.base_agent import BaseAgent
from src.execution.dag_executor import CircularDependencyError, DAGExecutor
from src.llm.response_parser import DecomposeResponse

logger = logging.getLogger(__name__)

# Valid story types — canonical lowercase names matching classify.md and WORKFLOW_MAP
STORY_TYPES = {
    "development", "config", "maintenance", "debug", "research", "review",
    "conversation", "content",
    # Human story types
    "assignment", "human_task", "approval", "qa_feedback", "escalation",
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
    "Content": "content",
    "document": "content",
    "Document": "content",
    "documentation": "content",
    "writing": "content",
    "template": "content",
    "Assignment": "assignment",
    "human_task": "human_task",
    "Human_Task": "human_task",
    "HumanTask": "human_task",
    "human task": "human_task",
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
    def response_model(self) -> type[BaseModel]:
        return DecomposeResponse

    async def decompose(
        self,
        user_request: str,
        task_type: str,
        working_directory: str,
        existing_prd: dict | None = None,
        existing_progress: dict | None = None,
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
        """Normalize story fields: map type aliases to canonical lowercase names.

        If a story type is unknown, re-classify by finding the closest match
        from valid types and send an ntfy notification so the user can intervene.
        """
        for story in response.stories:
            # Try exact match first, then case-insensitive
            matched = _TYPE_MAP.get(story.type) or _TYPE_MAP.get(story.type.lower())
            if matched:
                story.type = matched
            else:
                original_type = story.type
                # Re-classify: find closest match from valid types based on description
                reclassified = self._reclassify_story_type(story)
                story.type = reclassified
                logger.warning(
                    f"Unknown story type '{original_type}' for {story.id}, "
                    f"re-classified as '{reclassified}'"
                )
                # Notify user via ntfy so they can intervene if needed
                self._notify_reclassification(story, original_type, reclassified)

    def _reclassify_story_type(self, story) -> str:
        """Find the closest valid type for a story based on its description.

        Uses keyword matching against known type descriptions.
        """
        desc = (story.description + " " + story.title).lower()

        # Keyword-based matching ordered by specificity
        type_keywords = {
            "content": ["document", "template", "write", "create file", "guide",
                        "email", "reference", "readme", "markdown", "html template"],
            "research": ["research", "gather", "analyze", "compare", "summarize",
                         "investigate", "survey", "benchmark"],
            "config": ["config", "configure", "setup", "install", "deploy",
                        "docker", "nginx", "systemd", "environment"],
            "maintenance": ["update", "upgrade", "cleanup", "rotate", "migrate",
                            "backup", "archive", "prune"],
            "debug": ["fix", "bug", "error", "broken", "failing", "crash",
                       "debug", "diagnose", "troubleshoot"],
            "review": ["review", "audit", "assess", "evaluate", "inspect"],
            "development": ["implement", "build", "code", "feature", "function",
                            "class", "module", "api", "endpoint"],
        }

        best_type = "development"
        best_score = 0
        for story_type, keywords in type_keywords.items():
            score = sum(1 for kw in keywords if kw in desc)
            if score > best_score:
                best_score = score
                best_type = story_type

        return best_type

    def _notify_reclassification(self, story, original_type: str, new_type: str):
        """Send ntfy notification about a story type reclassification."""
        try:
            import os
            import urllib.error
            import urllib.request

            topic = os.environ.get("NTFY_TOPIC", "johnlane-claude-tasks")
            server = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
            url = f"{server}/{topic}"

            message = (
                f"Story type re-classified\n"
                f"Story: {story.id} — {story.title}\n"
                f"Original type: {original_type}\n"
                f"Re-classified as: {new_type}\n"
                f"Description: {story.description[:200]}"
            )

            req = urllib.request.Request(
                url,
                data=message.encode("utf-8"),
                headers={
                    "Title": f"SAT: Story type re-classified ({original_type} → {new_type})",
                    "Priority": "high",
                    "Tags": "warning",
                },
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to send reclassification ntfy: {e}")

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
