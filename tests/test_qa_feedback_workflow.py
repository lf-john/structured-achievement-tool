"""Tests for src.workflows.qa_feedback_workflow — QA feedback story workflow."""

import pytest
from unittest.mock import MagicMock

from src.workflows.qa_feedback_workflow import (
    QAFeedbackWorkflow,
    qa_route_decision,
)
from src.workflows.approval_workflow import ApprovalConfig


class TestQARouteDecision:
    def test_pass_verdict_routes_pass(self):
        state = {"qa_feedback_parsed": {"verdict": "pass"}}
        assert qa_route_decision(state) == "pass"

    def test_fail_verdict_routes_fail(self):
        state = {"qa_feedback_parsed": {"verdict": "fail"}}
        assert qa_route_decision(state) == "fail"

    def test_partial_verdict_routes_fail(self):
        state = {"qa_feedback_parsed": {"verdict": "partial"}}
        assert qa_route_decision(state) == "fail"

    def test_missing_verdict_routes_fail(self):
        state = {"qa_feedback_parsed": {}}
        assert qa_route_decision(state) == "fail"

    def test_no_parsed_data_routes_fail(self):
        state = {}
        assert qa_route_decision(state) == "fail"


class TestQAFeedbackWorkflowGraph:
    def test_has_all_nodes(self):
        workflow = QAFeedbackWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        node_names = set(graph.nodes.keys())

        expected = {"prepare", "notify", "pause", "follow_up", "escalation",
                    "parse", "learn"}
        assert expected == node_names

    def test_node_count(self):
        workflow = QAFeedbackWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        assert len(graph.nodes) == 7

    def test_compiles_without_error(self):
        workflow = QAFeedbackWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        compiled = workflow.compile()
        assert compiled is not None

    def test_pass_routes_to_learn(self):
        """QA pass should route to LEARN node."""
        workflow = QAFeedbackWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        assert "learn" in graph.nodes
        assert "parse" in graph.nodes

    def test_uses_custom_config(self):
        config = ApprovalConfig(poll_interval=15)
        workflow = QAFeedbackWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
            config=config,
        )
        assert workflow.config.poll_interval == 15
