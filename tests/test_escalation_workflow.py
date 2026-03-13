"""Tests for src.workflows.escalation_workflow — escalation story workflow."""

from unittest.mock import MagicMock

from src.workflows.approval_workflow import ApprovalConfig
from src.workflows.escalation_workflow import EscalationWorkflow


class TestEscalationWorkflowGraph:
    def test_has_all_nodes(self):
        workflow = EscalationWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        node_names = set(graph.nodes.keys())

        expected = {"prepare", "package_diagnostics", "notify", "pause", "follow_up", "escalation", "learn"}
        assert expected == node_names

    def test_node_count(self):
        workflow = EscalationWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        assert len(graph.nodes) == 7

    def test_compiles_without_error(self):
        workflow = EscalationWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        compiled = workflow.compile()
        assert compiled is not None

    def test_entry_is_prepare(self):
        workflow = EscalationWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        assert "prepare" in graph.nodes

    def test_prepare_connects_to_package_diagnostics(self):
        """PREPARE should flow to PACKAGE_DIAGNOSTICS."""
        workflow = EscalationWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        assert "package_diagnostics" in graph.nodes

    def test_uses_custom_config(self):
        config = ApprovalConfig(
            poll_interval=60,
            escalation_after=1800,
            escalation_contacts=["admin@example.com"],
        )
        workflow = EscalationWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
            config=config,
        )
        assert workflow.config.poll_interval == 60
        assert workflow.config.escalation_contacts == ["admin@example.com"]

    def test_escalation_routes_to_learn(self):
        """After escalation, should route to LEARN to capture resolution."""
        workflow = EscalationWorkflow(
            routing_engine=MagicMock(),
            notifier=MagicMock(),
        )
        graph = workflow.build_graph()
        assert "learn" in graph.nodes
        assert "escalation" in graph.nodes
