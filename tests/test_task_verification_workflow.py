"""Tests for src.workflows.task_verification_workflow."""

from unittest.mock import MagicMock

from src.workflows.task_verification_workflow import (
    MAX_CRITIC_RETRIES,
    TaskVerificationWorkflow,
    gather_outputs_node,
    verification_decision,
)


class TestGatherOutputsNode:
    def test_gathers_complete_phases(self):
        state = {
            "story": {"id": "S1"},
            "working_directory": "/project",
            "phase_outputs": [
                {"phase": "DESIGN", "status": "complete", "output": "Design output"},
                {"phase": "CODE", "status": "complete", "output": "Code output"},
                {"phase": "VERIFY", "status": "failed", "output": "Failed"},
            ],
            "current_phase": "",
        }
        result = gather_outputs_node(state)
        assert result["current_phase"] == "GATHER_OUTPUTS"
        assert "Design output" in result["design_output"]
        assert "Code output" in result["design_output"]
        assert "Failed" not in result["design_output"]  # Failed phases excluded

    def test_handles_no_outputs(self):
        state = {
            "story": {"id": "S1"},
            "working_directory": "/project",
            "phase_outputs": [],
            "current_phase": "",
        }
        result = gather_outputs_node(state)
        assert "No phase outputs" in result["design_output"]


class TestVerificationDecision:
    def test_pass_routes_to_report(self):
        assert verification_decision({"critic_passed": True}) == "report"

    def test_fail_under_limit_routes_to_gather(self):
        state = {"critic_passed": False, "critic_retry_count": 1}
        assert verification_decision(state) == "gather"

    def test_fail_at_limit_routes_to_fail(self):
        state = {"critic_passed": False, "critic_retry_count": MAX_CRITIC_RETRIES}
        assert verification_decision(state) == "fail"


class TestTaskVerificationWorkflowGraph:
    def test_has_all_nodes(self):
        workflow = TaskVerificationWorkflow(routing_engine=MagicMock())
        graph = workflow.build_graph()
        node_names = {n for n in graph.nodes if not n.startswith("__")}
        expected = {"gather_outputs", "verify_acs", "report", "write_output"}
        assert expected == node_names

    def test_compiles_without_error(self):
        workflow = TaskVerificationWorkflow(routing_engine=MagicMock())
        compiled = workflow.compile()
        assert compiled is not None
