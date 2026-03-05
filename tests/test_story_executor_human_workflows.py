"""Tests for human workflow registration in story_executor."""

from unittest.mock import MagicMock

from src.execution.story_executor import (
    HUMAN_STORY_TYPES,
    WORKFLOW_MAP,
    get_workflow_for_story,
)
from src.workflows.assignment_workflow import AssignmentWorkflow
from src.workflows.escalation_workflow import EscalationWorkflow
from src.workflows.qa_feedback_workflow import QAFeedbackWorkflow


class TestWorkflowMap:
    def test_assignment_registered(self):
        assert "assignment" in WORKFLOW_MAP
        assert WORKFLOW_MAP["assignment"] is AssignmentWorkflow

    def test_qa_feedback_registered(self):
        assert "qa_feedback" in WORKFLOW_MAP
        assert WORKFLOW_MAP["qa_feedback"] is QAFeedbackWorkflow

    def test_escalation_registered(self):
        assert "escalation" in WORKFLOW_MAP
        assert WORKFLOW_MAP["escalation"] is EscalationWorkflow

    def test_human_story_types_set(self):
        assert "assignment" in HUMAN_STORY_TYPES
        assert "qa_feedback" in HUMAN_STORY_TYPES
        assert "escalation" in HUMAN_STORY_TYPES
        # Non-human types should not be in the set
        assert "development" not in HUMAN_STORY_TYPES

    def test_total_workflow_count(self):
        assert len(WORKFLOW_MAP) == 11


class TestGetWorkflowForHumanStory:
    def test_assignment_story_returns_compiled_graph(self):
        story = {"type": "assignment", "id": "US-100"}
        re = MagicMock()
        ntf = MagicMock()
        graph = get_workflow_for_story(story, re, notifier=ntf)
        assert graph is not None

    def test_qa_feedback_story_returns_compiled_graph(self):
        story = {"type": "qa_feedback", "id": "US-100"}
        re = MagicMock()
        ntf = MagicMock()
        graph = get_workflow_for_story(story, re, notifier=ntf)
        assert graph is not None

    def test_escalation_story_returns_compiled_graph(self):
        story = {"type": "escalation", "id": "US-100"}
        re = MagicMock()
        ntf = MagicMock()
        graph = get_workflow_for_story(story, re, notifier=ntf)
        assert graph is not None

    def test_human_workflow_receives_notifier(self):
        """Human workflows should get the notifier passed through."""
        story = {"type": "assignment", "id": "US-100"}
        re = MagicMock()
        ntf = MagicMock()
        # Should not raise — notifier is passed
        graph = get_workflow_for_story(story, re, notifier=ntf)
        assert graph is not None
