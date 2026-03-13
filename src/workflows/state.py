"""
Shared Workflow State Models — Pydantic-validated state for all LangGraph workflows.

The StoryState TypedDict is the central state object flowing through all workflow graphs.
PhaseOutput captures the result of each phase execution.
Pydantic models enforce typed interfaces at all cross-component boundaries.
"""

from datetime import datetime
from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, Field


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
    retry_guidance: str | None = None


# --- Cross-component boundary models (Phase 163 Pydantic improvements) ---


class StoryModel(BaseModel):
    """Typed representation of a story flowing through execution.

    Replaces raw story dicts passed between orchestrator, story_executor,
    workflows, and agents. Created from StorySchema after decomposition.
    """

    id: str
    title: str
    description: str = ""
    type: str = "development"
    status: str = "pending"
    dependsOn: list[str] = Field(default_factory=list)
    acceptanceCriteria: list[str] = Field(default_factory=list)
    complexity: int = Field(default=5, ge=0, le=10)
    verification_agents: list[str] = Field(default_factory=list)
    outcome_verification: bool = False
    output_path: str | None = None
    output_format: str | None = None
    doc_type: str | None = None
    store: bool = False  # If True, persist output to file + vector memory

    # Execution-time fields (not from decomposition)
    working_directory: str | None = None
    git_branch: str | None = None

    def to_dict(self) -> dict:
        """Convert to dict for backward compatibility with code expecting raw dicts."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "StoryModel":
        """Create from a raw dict, tolerating extra keys."""
        return cls.model_validate(data)


class ValidationResult(BaseModel):
    """Result from workflow VALIDATE nodes.

    Replaces raw validation_result dicts in StoryState.
    """

    passed: bool
    reason: str = ""
    checks_run: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class QAFeedback(BaseModel):
    """Parsed QA feedback from human reviewers.

    Replaces raw qa_feedback_parsed dicts in StoryState.
    """

    verdict: str = ""  # "approved", "needs_changes", "rejected"
    bugs: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    comments: str = ""


class EscalationPackage(BaseModel):
    """Diagnostic package for escalation stories.

    Replaces raw escalation_package dicts in StoryState.
    """

    reason: str
    severity: str = "medium"  # low, medium, high, critical
    context: str = ""
    failed_phases: list[str] = Field(default_factory=list)
    error_summary: str = ""
    recommended_action: str = ""


class ExecutionConfig(BaseModel):
    """Configuration for story execution.

    Replaces raw config dicts passed to story_executor and workflows.
    """

    max_attempts: int = 5
    mediator_enabled: bool = False
    checkpoint_db: str = ""
    worktree_enabled: bool = False  # Controlled by config.json execution.use_worktree
    phase_models: dict = Field(default_factory=dict)  # phase_name -> model override
    timeout_seconds: int = 600


class StoryState(TypedDict):
    """Central state object for LangGraph workflows.

    Flows through all nodes. Each node reads what it needs and updates
    relevant fields. LangGraph handles state persistence via checkpointing.

    Note: TypedDict values are dicts at runtime (for LangGraph serialization),
    but the Pydantic models above define the schema. Use StoryModel.from_dict()
    and .to_dict() for conversions at component boundaries.
    """

    # Story identity — use StoryModel.from_dict(state["story"]) at boundaries
    story: dict  # StoryModel.model_dump() — typed via StoryModel
    task_id: str  # Parent task identifier
    task_description: str  # Original user request

    # Phase tracking — use PhaseOutput.model_validate(d) for each entry
    current_phase: str
    phase_outputs: list[dict]  # List of PhaseOutput.model_dump() dicts
    phase_retry_count: int  # Retries within current phase (resets per phase)

    # Verification state — use TestResult.model_validate(state["test_results"])
    verify_passed: bool | None
    test_results: dict | None  # TestResult.model_dump() dict

    # Failure handling
    failure_context: str  # Error output from last failure, fed to retry
    story_attempt: int  # Which attempt of this story (1-5)
    max_attempts: int

    # Mediator — use MediatorVerdict.model_validate(state["mediator_verdict"])
    mediator_verdict: dict | None  # MediatorVerdict.model_dump() dict
    mediator_enabled: bool

    # Git state
    working_directory: str
    git_base_commit: str | None  # Commit hash to reset to on retry

    # Context for progressive disclosure
    design_output: str  # Architecture decisions from DESIGN phase
    test_files: str  # Test file content from TDD_RED phase
    plan_output: str  # Plan from PLAN phase (config/maint workflows)
    reproduction_status: str | None
    reproduction_details: str | None
    diagnosis_category: str | None  # Category from DIAGNOSE phase (Dev, Config, Maint, Report)
    diagnosis_reasoning: str | None  # Reasoning for diagnosis categorization

    # Parallel gather/verify results (Phase 3 enhancements)
    gather_results: dict | None  # Merged results from parallel gather channels
    verify_check_results: dict | None  # Results from parallel verification checks
    config_validation_result: dict | None  # Config syntax validation result
    dependency_check_result: dict | None  # Dependency verification result

    # Approval workflow state
    pause_response: str | None  # Human response text from approval
    pause_escalated: bool | None  # Whether escalation was triggered
    approval_status: str | None  # responded, waiting, timeout, auto_approved
    approval_signal_path: str | None  # Path to the approval signal file
    approval_elapsed: int | None  # Total elapsed time in approval

    # Human workflow state (Phase 5)
    # Use ValidationResult.model_validate(), QAFeedback.model_validate(),
    # EscalationPackage.model_validate() at boundaries
    human_summary: str | None  # Prepared human-readable brief from PREPARE node
    human_deliverables: str | None  # Human's work output from INTEGRATE node
    qa_feedback_parsed: dict | None  # QAFeedback.model_dump() dict
    escalation_package: dict | None  # EscalationPackage.model_dump() dict
    validation_result: dict | None  # ValidationResult.model_dump() dict

    # Snapshot state (config/maintenance workflows)
    snapshot_hash: str | None  # Git commit hash for pre-execute snapshot

    # Failure classification (debug workflow)
    failure_classification: dict | None  # FailureClassification from failure_classifier

    # Critic review state (post-agentic-verify quality gate)
    critic_passed: bool | None  # Whether critic review passed thresholds
    critic_ratings: list[dict] | None  # List of ACRating dicts from CriticResponse
    critic_average: float | None  # Average rating across all ACs
    critic_validation: dict | None  # ValidationResult dict from validate_ratings()
    critic_retry_count: int  # Number of critic-triggered rewrites


def create_initial_state(
    story: "dict | StoryModel",
    task_id: str,
    task_description: str,
    working_directory: str,
    max_attempts: int = 5,
    mediator_enabled: bool = False,
) -> StoryState:
    """Create the initial state for a story workflow execution.

    Accepts either a StoryModel instance or a raw dict. If a dict is passed,
    it is validated through StoryModel to catch schema errors early.
    """
    if isinstance(story, StoryModel):
        story_dict = story.to_dict()
    else:
        # Validate the raw dict through StoryModel — catches missing/wrong fields
        story_dict = StoryModel.from_dict(story).to_dict()

    return StoryState(
        story=story_dict,
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
        gather_results=None,
        verify_check_results=None,
        config_validation_result=None,
        dependency_check_result=None,
        pause_response=None,
        pause_escalated=None,
        approval_status=None,
        approval_signal_path=None,
        approval_elapsed=None,
        human_summary=None,
        human_deliverables=None,
        qa_feedback_parsed=None,
        escalation_package=None,
        validation_result=None,
        snapshot_hash=None,
        failure_classification=None,
        critic_passed=None,
        critic_ratings=None,
        critic_average=None,
        critic_validation=None,
        critic_retry_count=0,
    )
