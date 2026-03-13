"""
Critic Agent — Reviews and critiques generated content or code against
acceptance criteria.

Supports escalation: when escalation > 0, routes to higher-tier models
via select_with_escalation for more thorough review.

Modes:
- content_critic: Reviews content quality (documents, research)
- dev_critic: Reviews code changes (development, config, maintenance)

Quality thresholds:
- Minimum individual AC rating: 5/10
- Minimum average across all ACs: 7.0/10

Complexity: 6 (Critic). Routes to mid-tier models by default.
"""

import logging
from typing import NamedTuple

from pydantic import BaseModel, Field

from src.agents.base_agent import BaseAgent
from src.llm.providers import ProviderConfig
from src.llm.routing_engine import RoutingEngine

logger = logging.getLogger(__name__)

# Quality thresholds
MIN_INDIVIDUAL_RATING = 5
MIN_AVERAGE_RATING = 7.0


class ACRating(BaseModel):
    """Rating for a single acceptance criterion."""

    ac_id: str = ""
    ac_name: str = ""
    rating: int = Field(ge=1, le=10)
    justification: str = ""


class CriticResponse(BaseModel):
    """Structured response from critic evaluation."""

    ratings: list[ACRating] = Field(default_factory=list)
    overall_assessment: str = ""
    recommendations: list[str] = Field(default_factory=list)


class ValidationResult(NamedTuple):
    """Result of validating critic ratings against thresholds."""

    passed: bool
    average: float
    missing_acs: list[str]
    failing_acs: list[dict]
    message: str


def validate_ratings(
    response: CriticResponse,
    acceptance_criteria: list[str],
) -> ValidationResult:
    """Validate critic ratings against quality thresholds.

    Returns ValidationResult with pass/fail status and details about
    any missing or failing acceptance criteria.
    """
    if not response.ratings:
        return ValidationResult(
            passed=True,
            average=0.0,
            missing_acs=[],
            failing_acs=[],
            message="No ratings provided — passing by default",
        )

    # Check for missing ACs
    rated_ids = {r.ac_id for r in response.ratings if r.ac_id}
    rated_names = {r.ac_name.lower() for r in response.ratings if r.ac_name}
    missing_acs = []
    for i, ac in enumerate(acceptance_criteria):
        ac_id = f"AC-{i + 1}"
        if ac_id not in rated_ids and ac.lower() not in rated_names:
            missing_acs.append(ac_id)

    # Calculate average
    ratings_values = [r.rating for r in response.ratings]
    average = sum(ratings_values) / len(ratings_values)

    # Find failing ACs (below minimum individual threshold)
    failing_acs = []
    for r in response.ratings:
        if r.rating < MIN_INDIVIDUAL_RATING:
            failing_acs.append(
                {
                    "ac_id": r.ac_id,
                    "ac_name": r.ac_name,
                    "rating": r.rating,
                    "justification": r.justification,
                }
            )

    # Determine pass/fail
    passed = average >= MIN_AVERAGE_RATING and len(failing_acs) == 0

    # Build message
    parts = []
    if average < MIN_AVERAGE_RATING:
        parts.append(f"Average rating {average:.1f} below threshold {MIN_AVERAGE_RATING}")
    if failing_acs:
        parts.append(f"{len(failing_acs)} AC(s) below minimum {MIN_INDIVIDUAL_RATING}")
    if missing_acs:
        parts.append(f"{len(missing_acs)} AC(s) not rated: {', '.join(missing_acs)}")

    message = "; ".join(parts) if parts else f"All criteria met (avg={average:.1f})"

    return ValidationResult(
        passed=passed,
        average=average,
        missing_acs=missing_acs,
        failing_acs=failing_acs,
        message=message,
    )


class CriticAgent(BaseAgent):
    def __init__(
        self,
        mode: str = "content_critic",
        routing_engine: RoutingEngine | None = None,
        config_path: str | None = None,
        escalation: int = 0,
    ):
        super().__init__(routing_engine=routing_engine, config_path=config_path)
        self.mode = mode
        self.escalation = escalation

    @property
    def agent_name(self) -> str:
        return "critic"

    @property
    def response_model(self) -> type[BaseModel]:
        return CriticResponse

    def get_provider(
        self,
        story_complexity: int | None = None,
        is_code_task: bool = False,
    ) -> ProviderConfig:
        """Get the routed provider for this critic mode, with escalation offset."""
        if self.escalation > 0:
            return self.routing_engine.select_with_escalation(
                self.agent_name,
                attempt_number=(self.escalation // 5) + 1,
                failure_is_persistent=True,
            )
        return self.routing_engine.select(self.agent_name, story_complexity=story_complexity)

    async def evaluate(
        self,
        acceptance_criteria: list[str],
        output_content: str,
        task_description: str = "",
        working_directory: str = "",
    ) -> CriticResponse:
        """Evaluate output against acceptance criteria.

        Builds a critic prompt with the ACs and output content, invokes
        the LLM, and returns structured ratings.
        """
        # Build AC list for the prompt
        ac_list = "\n".join(f"- AC-{i + 1}: {ac}" for i, ac in enumerate(acceptance_criteria))

        # Truncate output to avoid token limits
        max_content = 15000
        content_preview = output_content[:max_content]
        if len(output_content) > max_content:
            content_preview += "\n[...truncated...]"

        story = {
            "id": "CRITIC",
            "title": f"Critic Review ({self.mode})",
            "description": (
                f"Review the following output against these acceptance criteria.\n\n"
                f"## Acceptance Criteria\n{ac_list}\n\n"
                f"## Task Description\n{task_description}\n\n"
                f"## Output to Review\n```\n{content_preview}\n```\n\n"
                f"Rate each acceptance criterion from 1-10. Respond with JSON:\n"
                f'{{"ratings": [{{"ac_id": "AC-1", "ac_name": "...", '
                f'"rating": N, "justification": "..."}}], '
                f'"overall_assessment": "...", "recommendations": ["..."]}}'
            ),
        }

        result = await self.execute(
            story=story,
            phase="VERIFY",
            working_directory=working_directory or ".",
            context={"task_description": task_description},
        )

        # Ensure we return a CriticResponse
        if isinstance(result, CriticResponse):
            return result

        # If base_agent returned a generic BaseModel, try to convert
        try:
            return CriticResponse.model_validate(result.model_dump())
        except Exception:
            logger.warning("Could not convert response to CriticResponse, returning empty")
            return CriticResponse(
                ratings=[],
                overall_assessment="Evaluation failed",
            )
