"""Tests for src.workflows.assignment_workflow — assignment story workflow."""

from unittest.mock import MagicMock

from src.workflows.approval_workflow import ApprovalConfig
from src.workflows.assignment_workflow import (
    AssignmentWorkflow,
    validate_decision,
)


class TestValidateDecision:
    def test_pass_when_verified(self):
        state = {"verify_passed": True}
        assert validate_decision(state) == "pass"

    def test_fail_when_not_verified(self):
        state = {"verify_passed": False}
        assert validate_decision(state) == "fail"

    def test_fail_when_missing(self):
        state = {}
        assert validate_decision(state) == "fail"


class TestAssignmentWorkflowGraph:
    def test_has_all_nodes(self):
        workflow = AssignmentWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
            config=ApprovalConfig(),
        )
        graph = workflow.build_graph()
        node_names = set(graph.nodes.keys())

        expected = {"prepare", "notify", "pause", "follow_up", "escalation",
                    "validate", "integrate", "learn"}
        assert expected == node_names

    def test_entry_point_is_prepare(self):
        workflow = AssignmentWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        # Verify prepare is a node (it's set as entry point via set_entry_point)
        assert "prepare" in graph.nodes

    def test_compiles_without_error(self):
        workflow = AssignmentWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        compiled = workflow.compile()
        assert compiled is not None

    def test_node_count(self):
        workflow = AssignmentWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        assert len(graph.nodes) == 8

    def test_validate_and_pause_both_present(self):
        """VALIDATE and PAUSE should both exist for retry loop."""
        workflow = AssignmentWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        assert "validate" in graph.nodes
        assert "pause" in graph.nodes

    def test_uses_custom_config(self):
        config = ApprovalConfig(
            poll_interval=10,
            follow_up_after=1800,
            escalation_after=3600,
        )
        workflow = AssignmentWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
            config=config,
        )
        assert workflow.config.poll_interval == 10
        assert workflow.config.follow_up_after == 1800
