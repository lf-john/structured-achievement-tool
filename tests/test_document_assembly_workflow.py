"""Tests for src.workflows.document_assembly_workflow."""

from unittest.mock import MagicMock

from src.workflows.document_assembly_workflow import (
    MAX_CRITIC_RETRIES,
    DocumentAssemblyWorkflow,
    quality_check_decision,
)


class TestQualityCheckDecision:
    def test_pass_routes_to_write_output(self):
        assert quality_check_decision({"critic_passed": True}) == "write_output"

    def test_fail_under_limit_routes_to_assemble(self):
        state = {"critic_passed": False, "critic_retry_count": 1}
        assert quality_check_decision(state) == "assemble"

    def test_fail_at_limit_routes_to_fail(self):
        state = {"critic_passed": False, "critic_retry_count": MAX_CRITIC_RETRIES}
        assert quality_check_decision(state) == "fail"


class TestDocumentAssemblyWorkflowGraph:
    def test_has_all_nodes(self):
        workflow = DocumentAssemblyWorkflow(routing_engine=MagicMock())
        graph = workflow.build_graph()
        node_names = {n for n in graph.nodes if not n.startswith("__")}
        expected = {"gather_inputs", "design_layout", "request_images", "assemble", "quality_check", "write_output"}
        assert expected == node_names

    def test_compiles_without_error(self):
        workflow = DocumentAssemblyWorkflow(routing_engine=MagicMock())
        compiled = workflow.compile()
        assert compiled is not None

    def test_entry_point_is_gather_inputs(self):
        workflow = DocumentAssemblyWorkflow(routing_engine=MagicMock())
        graph = workflow.build_graph()
        assert "gather_inputs" in graph.nodes
