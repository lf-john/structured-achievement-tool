"""Tests for Pydantic cross-component boundary models."""

import pytest
from pydantic import ValidationError

from src.workflows.state import (
    EscalationPackage,
    ExecutionConfig,
    QAFeedback,
    StoryModel,
    ValidationResult,
    create_initial_state,
)


class TestStoryModel:
    """Test StoryModel validation and conversions."""

    def test_minimal_valid_story(self):
        story = StoryModel(id="s1", title="Test", description="A test story")
        assert story.id == "s1"
        assert story.type == "development"
        assert story.complexity == 5

    def test_full_story(self):
        story = StoryModel(
            id="s2",
            title="Add auth",
            description="Implement JWT authentication",
            type="development",
            dependsOn=["s1"],
            acceptanceCriteria=["JWT tokens issued", "Tokens verified"],
            complexity=7,
            verification_agents=["pytest"],
        )
        assert len(story.dependsOn) == 1
        assert story.complexity == 7

    def test_from_dict(self):
        data = {"id": "s1", "title": "T", "description": "D", "extra_field": "ignored"}
        story = StoryModel.from_dict(data)
        assert story.id == "s1"

    def test_to_dict(self):
        story = StoryModel(id="s1", title="T", description="D")
        d = story.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "s1"
        assert d["type"] == "development"

    def test_roundtrip(self):
        original = StoryModel(id="s1", title="T", description="D", complexity=8)
        d = original.to_dict()
        restored = StoryModel.from_dict(d)
        assert restored == original

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            StoryModel(id="s1")  # Missing title

    def test_complexity_bounds(self):
        with pytest.raises(ValidationError):
            StoryModel(id="s1", title="T", description="D", complexity=15)
        with pytest.raises(ValidationError):
            StoryModel(id="s1", title="T", description="D", complexity=-1)

    def test_complexity_edge_values(self):
        s0 = StoryModel(id="s1", title="T", description="D", complexity=0)
        s10 = StoryModel(id="s2", title="T", description="D", complexity=10)
        assert s0.complexity == 0
        assert s10.complexity == 10


class TestValidationResult:
    def test_passed(self):
        vr = ValidationResult(passed=True, reason="All checks passed")
        assert vr.passed is True
        assert vr.issues == []

    def test_failed_with_issues(self):
        vr = ValidationResult(
            passed=False,
            reason="Checks failed",
            checks_run=["lint", "type_check"],
            issues=["Type error in auth.py"],
        )
        assert vr.passed is False
        assert len(vr.issues) == 1


class TestQAFeedback:
    def test_approved(self):
        qa = QAFeedback(verdict="approved", comments="LGTM")
        assert qa.verdict == "approved"
        assert qa.bugs == []

    def test_needs_changes(self):
        qa = QAFeedback(
            verdict="needs_changes",
            bugs=["Missing null check"],
            suggestions=["Add logging"],
        )
        assert len(qa.bugs) == 1
        assert len(qa.suggestions) == 1


class TestEscalationPackage:
    def test_basic(self):
        ep = EscalationPackage(
            reason="Persistent test failure",
            severity="high",
            failed_phases=["CODE", "VERIFY"],
            error_summary="TypeError: cannot read property of undefined",
        )
        assert ep.severity == "high"
        assert len(ep.failed_phases) == 2

    def test_defaults(self):
        ep = EscalationPackage(reason="Unknown error")
        assert ep.severity == "medium"
        assert ep.failed_phases == []


class TestExecutionConfig:
    def test_defaults(self):
        config = ExecutionConfig()
        assert config.max_attempts == 5
        assert config.mediator_enabled is False
        assert config.worktree_enabled is False

    def test_custom(self):
        config = ExecutionConfig(
            max_attempts=3,
            mediator_enabled=True,
            phase_models={"CODE": "claude-sonnet"},
        )
        assert config.max_attempts == 3
        assert config.phase_models["CODE"] == "claude-sonnet"


class TestCreateInitialStateWithStoryModel:
    """Test that create_initial_state validates through StoryModel."""

    def test_with_story_model(self):
        story = StoryModel(id="s1", title="T", description="D")
        state = create_initial_state(
            story=story,
            task_id="task-1",
            task_description="Test task",
            working_directory="/tmp/work",
        )
        assert state["story"]["id"] == "s1"
        assert state["task_id"] == "task-1"

    def test_with_raw_dict(self):
        story_dict = {"id": "s1", "title": "T", "description": "D", "complexity": 3}
        state = create_initial_state(
            story=story_dict,
            task_id="task-1",
            task_description="Test task",
            working_directory="/tmp/work",
        )
        # Should have been validated and normalized through StoryModel
        assert state["story"]["id"] == "s1"
        assert state["story"]["complexity"] == 3
        assert state["story"]["type"] == "development"  # Default filled in

    def test_with_invalid_dict_raises(self):
        # Missing required 'id' and 'title'
        with pytest.raises(ValidationError):
            create_initial_state(
                story={"description": "only desc"},
                task_id="task-1",
                task_description="Test",
                working_directory="/tmp",
            )

    def test_with_extra_fields_tolerant(self):
        story_dict = {
            "id": "s1", "title": "T", "description": "D",
            "some_extra_field": "value",
        }
        state = create_initial_state(
            story=story_dict,
            task_id="task-1",
            task_description="Test",
            working_directory="/tmp",
        )
        assert state["story"]["id"] == "s1"
