"""
Shared Workflow State Models — Pydantic-validated state for all LangGraph workflows.

The StoryState TypedDict is the central state object flowing through all workflow graphs.
PhaseOutput captures the result of each phase execution.
"""

from typing import TypedDict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class PhaseOutput(BaseModel):
    """Result of a single phase execution."""
    phase: str
    status: PhaseStatus
    output: str = ""
    exit_code: int = 0
    provider_used: str = ""
    duration_seconds: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    artifacts: dict = Field(default_factory=dict)


class TestResult(BaseModel):
    """Result of test execution."""
    passed: bool
    total: int = 0
    failures: int = 0
    output: str = ""
    exit_code: int = 0
    framework: str = ""


class MediatorVerdict(BaseModel):
    """Result of a Mediator review."""
    decision: str  # ACCEPT, REVERT, PARTIAL, RETRY
    confidence: float = 0.0
    reasoning: str = ""
    retry_guidance: Optional[str] = None


class StoryState(TypedDict):
    """Central state object for LangGraph workflows.

    Flows through all nodes. Each node reads what it needs and updates
    relevant fields. LangGraph handles state persistence via checkpointing.
    """
    # Story identity
    story: dict  # Full story dict from PRD (id, title, description, type, tdd, acceptanceCriteria, etc.)
    task_id: str  # Parent task identifier
    task_description: str  # Original user request

    # Phase tracking
    current_phase: str
    phase_outputs: List[dict]  # List of PhaseOutput.model_dump() dicts
    phase_retry_count: int  # Retries within current phase (resets per phase)

    # Verification state
    verify_passed: Optional[bool]
    test_results: Optional[dict]  # TestResult.model_dump() dict

    # Failure handling
    failure_context: str  # Error output from last failure, fed to retry
    story_attempt: int  # Which attempt of this story (1-5)
    max_attempts: int

    # Mediator
    mediator_verdict: Optional[dict]  # MediatorVerdict.model_dump() dict
    mediator_enabled: bool

    # Git state
    working_directory: str
    git_base_commit: Optional[str]  # Commit hash to reset to on retry

    # Context for progressive disclosure
    design_output: str  # Architecture decisions from DESIGN phase
    test_files: str  # Test file content from TDD_RED phase
    plan_output: str  # Plan from PLAN phase (config/maint workflows)
    reproduction_status: Optional[str]
    reproduction_details: Optional[str]
    diagnosis_category: Optional[str]  # Category from DIAGNOSE phase (Dev, Config, Maint, Report)
    diagnosis_reasoning: Optional[str]  # Reasoning for diagnosis categorization


def create_initial_state(
    story: dict,
    task_id: str,
    task_description: str,
    working_directory: str,
    max_attempts: int = 5,
    mediator_enabled: bool = False,
) -> StoryState:
    """Create the initial state for a story workflow execution."""
    return StoryState(
        story=story,
        task_id=task_id,
        task_description=task_description,
        current_phase="",
        phase_outputs=[],
        phase_retry_count=0,
        verify_passed=None,
        test_results=None,
        failure_context="",
        story_attempt=1,
        max_attempts=max_attempts,
        mediator_verdict=None,
        mediator_enabled=mediator_enabled,
        working_directory=working_directory,
        git_base_commit=None,
        design_output="",
        test_files="",
        plan_output="",
        reproduction_status=None,
        reproduction_details=None,
        diagnosis_category=None,
        diagnosis_reasoning=None,
    )
