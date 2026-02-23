"""
Response Parser — JSON extraction + Pydantic validation for LLM agent responses.

Handles messy LLM output: extracts JSON from markdown fences, mixed text, etc.
Validates against Pydantic models for type safety and hallucination reduction.
"""

import json
import re
import logging
from typing import Type, TypeVar, Optional, List
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# --- Pydantic Models ---

class AgentStatus(str, Enum):
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"
    RETRY = "retry"


class AgentResponse(BaseModel):
    """Standard response format for all LLM agents."""
    thinking: str = ""
    status: AgentStatus
    output: str
    artifacts: dict = Field(default_factory=dict)
    claims: List[str] = Field(default_factory=list)


class ClassifyResponse(BaseModel):
    """Response from the Classifier agent."""
    task_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class StorySchema(BaseModel):
    """A single user story from decomposition."""
    id: str
    title: str
    description: str
    type: str = "development"
    tdd: bool = True
    status: str = "pending"
    dependsOn: List[str] = Field(default_factory=list)
    acceptanceCriteria: List[str] = Field(default_factory=list)
    complexity: int = Field(default=5, ge=1, le=10)


class DecomposeResponse(BaseModel):
    """Response from the Decompose/StoryAgent."""
    stories: List[StorySchema]


class VerifyResponse(BaseModel):
    """Response from the Verify phase."""
    status: str  # "pass", "fail", "retry_with_fixes"
    issues: List[str] = Field(default_factory=list)
    feedback: str = ""


class MediatorDecision(str, Enum):
    ACCEPT = "ACCEPT"
    REVERT = "REVERT"
    PARTIAL = "PARTIAL"
    RETRY = "RETRY"


class MediatorAction(BaseModel):
    file: str
    action: str  # "KEEP" or "REVERT"
    reason: str = ""


class MediatorResponse(BaseModel):
    """Response from the Mediator agent."""
    decision: MediatorDecision
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""
    testRegression: dict = Field(default_factory=dict)
    scopeAnalysis: dict = Field(default_factory=dict)
    actions: List[MediatorAction] = Field(default_factory=list)
    retryGuidance: Optional[str] = None


# --- JSON Extraction ---

def extract_json(text: str) -> dict:
    """Extract JSON object from LLM output.

    Handles:
    - Raw JSON
    - JSON wrapped in ```json ... ``` fences
    - JSON embedded in surrounding text
    - Multiple JSON blocks (takes the first valid one)
    """
    if not text or not text.strip():
        raise ValueError("Empty response text")

    # Try 1: Direct JSON parse
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Try 2: Extract from markdown code fences (multiline or inline)
    fence_pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
    matches = re.findall(fence_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try 3: Find first { ... } block (greedy matching for outermost braces)
    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[brace_start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"No valid JSON found in response (length={len(text)})")


def validate_response(data: dict, model: Type[T]) -> T:
    """Validate a dict against a Pydantic model.

    Args:
        data: Parsed JSON dict
        model: Pydantic model class to validate against

    Returns:
        Validated Pydantic model instance

    Raises:
        pydantic.ValidationError on validation failure
    """
    return model.model_validate(data)


def parse_and_validate(text: str, model: Type[T]) -> T:
    """Extract JSON from text and validate against a Pydantic model.

    Convenience function combining extract_json + validate_response.
    """
    data = extract_json(text)
    return validate_response(data, model)
