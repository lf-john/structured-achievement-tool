"""Tests for Phase 3 workflow enhancements (3.1-3.5).

Covers:
- 3.1 Dev TDD: architect_code/plan_code subagents + parallel_verify_node
- 3.2 Config TDD: TDD pattern (test_writer + tdd_red_check + tdd_green_check)
- 3.3 Maintenance: TDD pattern (test_writer + tdd_red_check + tdd_green_check)
- 3.4 Research: parallel gather channels
- 3.5 Review: unchanged (compile-only sanity check)
"""

import os
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from dataclasses import dataclass
from functools import partial

from langgraph.graph import END

from src.workflows.dev_tdd_workflow import DevTDDWorkflow
from src.workflows.config_tdd_workflow import ConfigTDDWorkflow
from src.workflows.maintenance_workflow import MaintenanceWorkflow
from src.workflows.research_workflow import ResearchWorkflow
from src.workflows.review_workflow import ReviewWorkflow
from src.workflows.state import StoryState, create_initial_state, PhaseStatus
from src.workflows.base_workflow import (
    parallel_verify_node,
    config_validate_node,
    dependency_check_node,
    parallel_gather_node,
    config_validate_decision,
    verify_decision,
    check_test_decision,
)


# --- Fixtures ---

def _make_state(**overrides) -> dict:
    """Create a minimal StoryState dict for testing node functions."""
    base = create_initial_state(
        story={"id": "TEST-001", "title": "Test story", "complexity": 3},
        task_id="task-001",
        task_description="Test task",
        working_directory="/tmp/test-workdir",
    )
    base = dict(base)
    base.update(overrides)
    return base


def _mock_routing_engine():
    """Create a mock RoutingEngine that returns a mock provider."""
    re = MagicMock()
    provider = MagicMock()
    provider.name = "mock-provider"
    re.select.return_value = provider
    return re


@dataclass
class FakeCLIResult:
    stdout: str = '{"status": "ok"}'
    stderr: str = ""
    exit_code: int = 0
    is_api_error: bool = False
    api_error_code: int = 0


# ============================================================
# 3.1 Dev TDD Workflow — architect_code/plan_code + parallel verify
# ============================================================

class TestDevTDDWorkflowStructure:
    """Verify the enhanced Dev TDD graph has the correct node set and edges."""

    def setup_method(self):
        self.workflow = DevTDDWorkflow()
        self.graph = self.workflow.build_graph()

    def test_has_architect_code_node(self):
        assert "architect_code" in self.graph.nodes

    def test_has_plan_code_node(self):
        assert "plan_code" in self.graph.nodes

    def test_has_test_writer_node(self):
        assert "test_writer" in self.graph.nodes

    def test_has_parallel_verify_node(self):
        assert "parallel_verify" in self.graph.nodes

    def test_does_not_have_old_design_node(self):
        """DESIGN was merged into architect_code."""
        assert "design" not in self.graph.nodes

    def test_does_not_have_old_plan_red_node(self):
        """plan_red was renamed to plan_code."""
        assert "plan_red" not in self.graph.nodes

    def test_does_not_have_old_architect_red_node(self):
        """architect_red was renamed to architect_code."""
        assert "architect_red" not in self.graph.nodes

    def test_does_not_have_old_tdd_red_node(self):
        """tdd_red was renamed to test_writer."""
        assert "tdd_red" not in self.graph.nodes

    def test_has_all_enhanced_nodes(self):
        nodes = set(self.graph.nodes)
        expected = {
            "architect_code", "plan_code", "test_writer",
            "code", "parallel_verify", "learn",
            "tdd_red_check", "tdd_green_check",
            "mediator_code", "mediator_verify",
        }
        assert expected.issubset(nodes)

    def test_compiles_without_error(self):
        compiled = self.workflow.compile()
        assert compiled is not None

    def test_entry_point_is_architect_code(self):
        """Entry point should be architect_code (not design)."""
        compiled = self.graph.compile()
        assert compiled is not None

    def test_has_mediator_after_code(self):
        """mediator_code should exist for post-CODE review."""
        assert "mediator_code" in self.graph.nodes

    def test_has_mediator_after_verify(self):
        """mediator_verify should exist for post-VERIFY review."""
        assert "mediator_verify" in self.graph.nodes

    def test_node_count(self):
        """Should have exactly 10 nodes (architect_code, plan_code, test_writer,
        code, parallel_verify, learn, tdd_red_check, tdd_green_check,
        mediator_code, mediator_verify)."""
        our_nodes = {n for n in self.graph.nodes if not n.startswith("__")}
        assert len(our_nodes) == 10


class TestParallelVerifyNode:
    """Test the parallel_verify_node function with mocked LLM calls."""

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_all_checks_pass(self, mock_invoke, mock_prompt, mock_pool):
        """When all 4 checks return exit_code=0, verify_passed should be True."""
        re = _mock_routing_engine()
        state = _make_state()

        # Each future.result() returns a successful CLI result
        mock_future = MagicMock()
        mock_future.result.return_value = FakeCLIResult(stdout='{"passed": true}', exit_code=0)
        mock_pool.submit.return_value = mock_future

        result = parallel_verify_node(state, re)

        assert result["verify_passed"] is True
        assert result["verify_check_results"] is not None
        assert len(result["verify_check_results"]) == 4
        for check in result["verify_check_results"].values():
            assert check["passed"] is True

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_one_check_fails(self, mock_invoke, mock_prompt, mock_pool):
        """When one check fails, verify_passed should be False."""
        re = _mock_routing_engine()
        state = _make_state()

        call_count = [0]

        def make_future(*args, **kwargs):
            call_count[0] += 1
            future = MagicMock()
            if call_count[0] == 2:  # Second check fails
                future.result.return_value = FakeCLIResult(
                    stdout='{"passed": false}', exit_code=1
                )
            else:
                future.result.return_value = FakeCLIResult(
                    stdout='{"passed": true}', exit_code=0
                )
            return future

        mock_pool.submit.side_effect = make_future

        result = parallel_verify_node(state, re)

        assert result["verify_passed"] is False
        assert "failure_context" in result
        assert result["verify_retry_count"] == 1

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_check_exception_is_handled(self, mock_invoke, mock_prompt, mock_pool):
        """When a check raises an exception, it should be caught and marked failed."""
        re = _mock_routing_engine()
        state = _make_state()

        call_count = [0]

        def make_future(*args, **kwargs):
            call_count[0] += 1
            future = MagicMock()
            if call_count[0] == 3:
                future.result.side_effect = TimeoutError("LLM timeout")
            else:
                future.result.return_value = FakeCLIResult(stdout="ok", exit_code=0)
            return future

        mock_pool.submit.side_effect = make_future

        result = parallel_verify_node(state, re)

        assert result["verify_passed"] is False
        failed_checks = [k for k, v in result["verify_check_results"].items() if not v["passed"]]
        assert len(failed_checks) == 1

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_all_checks_fail(self, mock_invoke, mock_prompt, mock_pool):
        """When all checks fail, all should be marked failed."""
        re = _mock_routing_engine()
        state = _make_state()

        mock_future = MagicMock()
        mock_future.result.return_value = FakeCLIResult(stdout='{"passed": false}', exit_code=1)
        mock_pool.submit.return_value = mock_future

        result = parallel_verify_node(state, re)

        assert result["verify_passed"] is False
        assert all(not v["passed"] for v in result["verify_check_results"].values())

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_phase_output_recorded(self, mock_invoke, mock_prompt, mock_pool):
        """parallel_verify should record a PARALLEL_VERIFY phase output."""
        re = _mock_routing_engine()
        state = _make_state()

        mock_future = MagicMock()
        mock_future.result.return_value = FakeCLIResult(stdout="ok", exit_code=0)
        mock_pool.submit.return_value = mock_future

        result = parallel_verify_node(state, re)

        phase_outputs = result["phase_outputs"]
        verify_outputs = [p for p in phase_outputs if p["phase"] == "PARALLEL_VERIFY"]
        assert len(verify_outputs) == 1
        assert verify_outputs[0]["status"] == PhaseStatus.COMPLETE.value

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_routes_to_4_agents(self, mock_invoke, mock_prompt, mock_pool):
        """Should call routing_engine.select for 4 different agents."""
        re = _mock_routing_engine()
        state = _make_state()

        mock_future = MagicMock()
        mock_future.result.return_value = FakeCLIResult(stdout="ok", exit_code=0)
        mock_pool.submit.return_value = mock_future

        parallel_verify_node(state, re)

        agent_names = [call[0][0] for call in re.select.call_args_list]
        assert "linter" in agent_names
        assert "test_runner" in agent_names
        assert "security_checker" in agent_names
        assert "arch_reviewer" in agent_names


# ============================================================
# 3.2 Config TDD — TDD pattern with test_writer + checks
# ============================================================

class TestConfigTDDWorkflowStructure:
    """Verify the Config TDD graph has the TDD pattern nodes."""

    def setup_method(self):
        self.workflow = ConfigTDDWorkflow()
        self.graph = self.workflow.build_graph()

    def test_has_test_writer_node(self):
        assert "test_writer" in self.graph.nodes

    def test_has_tdd_red_check_node(self):
        assert "tdd_red_check" in self.graph.nodes

    def test_has_tdd_green_check_node(self):
        assert "tdd_green_check" in self.graph.nodes

    def test_does_not_have_old_config_validate_node(self):
        """config_validate was replaced by TDD pattern."""
        assert "config_validate" not in self.graph.nodes

    def test_has_all_nodes(self):
        nodes = set(self.graph.nodes)
        expected = {"plan", "test_writer", "tdd_red_check", "execute",
                    "tdd_green_check", "verify_script", "learn"}
        assert expected.issubset(nodes)

    def test_compiles_without_error(self):
        compiled = self.workflow.compile()
        assert compiled is not None

    def test_node_count(self):
        """Should have exactly 7 nodes."""
        our_nodes = {n for n in self.graph.nodes if not n.startswith("__")}
        assert len(our_nodes) == 7


# ============================================================
# 3.3 Maintenance — TDD pattern with test_writer + checks
# ============================================================

class TestMaintenanceWorkflowStructure:
    """Verify the Maintenance graph has the TDD pattern nodes."""

    def setup_method(self):
        self.workflow = MaintenanceWorkflow()
        self.graph = self.workflow.build_graph()

    def test_has_test_writer_node(self):
        assert "test_writer" in self.graph.nodes

    def test_has_tdd_red_check_node(self):
        assert "tdd_red_check" in self.graph.nodes

    def test_has_tdd_green_check_node(self):
        assert "tdd_green_check" in self.graph.nodes

    def test_does_not_have_old_dependency_check_node(self):
        """dependency_check was replaced by TDD pattern."""
        assert "dependency_check" not in self.graph.nodes

    def test_has_all_nodes(self):
        nodes = set(self.graph.nodes)
        expected = {"plan", "test_writer", "tdd_red_check", "execute",
                    "tdd_green_check", "verify", "learn"}
        assert expected.issubset(nodes)

    def test_compiles_without_error(self):
        compiled = self.workflow.compile()
        assert compiled is not None

    def test_node_count(self):
        """Should have exactly 7 nodes."""
        our_nodes = {n for n in self.graph.nodes if not n.startswith("__")}
        assert len(our_nodes) == 7


# ============================================================
# 3.4 Research — parallel gather channels
# ============================================================

class TestResearchWorkflowStructure:
    """Verify the Research graph uses parallel_gather instead of single gather."""

    def setup_method(self):
        self.workflow = ResearchWorkflow()
        self.graph = self.workflow.build_graph()

    def test_has_parallel_gather_node(self):
        assert "parallel_gather" in self.graph.nodes

    def test_does_not_have_old_gather_node(self):
        """The old single 'gather' node should be replaced."""
        assert "gather" not in self.graph.nodes

    def test_has_all_nodes(self):
        nodes = set(self.graph.nodes)
        expected = {"parallel_gather", "parallel_analyze", "synthesize"}
        assert expected.issubset(nodes)

    def test_compiles_without_error(self):
        compiled = self.workflow.compile()
        assert compiled is not None


class TestParallelGatherNode:
    """Test the parallel_gather_node function with mocked LLM calls."""

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_all_channels_succeed(self, mock_invoke, mock_prompt, mock_pool):
        """All 3 gather channels should return results."""
        re = _mock_routing_engine()
        state = _make_state()

        mock_future = MagicMock()
        mock_future.result.return_value = FakeCLIResult(stdout="gathered data", exit_code=0)
        mock_pool.submit.return_value = mock_future

        result = parallel_gather_node(state, re)

        assert result["gather_results"] is not None
        assert len(result["gather_results"]) == 3
        assert "gatherer_web" in result["gather_results"]
        assert "gatherer_code" in result["gather_results"]
        assert "gatherer_docs" in result["gather_results"]

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_one_channel_fails_others_succeed(self, mock_invoke, mock_prompt, mock_pool):
        """If one channel errors, others should still return results."""
        re = _mock_routing_engine()
        state = _make_state()

        call_count = [0]

        def make_future(*args, **kwargs):
            call_count[0] += 1
            future = MagicMock()
            if call_count[0] == 2:
                future.result.side_effect = Exception("Network error")
            else:
                future.result.return_value = FakeCLIResult(stdout="data", exit_code=0)
            return future

        mock_pool.submit.side_effect = make_future

        result = parallel_gather_node(state, re)

        # Should still have 3 entries (failed one has error)
        assert len(result["gather_results"]) == 3
        error_channels = [k for k, v in result["gather_results"].items() if v["exit_code"] == -1]
        assert len(error_channels) == 1

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_merged_output_in_design_output(self, mock_invoke, mock_prompt, mock_pool):
        """Merged gather output should be stored in design_output for downstream."""
        re = _mock_routing_engine()
        state = _make_state()

        mock_future = MagicMock()
        mock_future.result.return_value = FakeCLIResult(stdout="channel output", exit_code=0)
        mock_pool.submit.return_value = mock_future

        result = parallel_gather_node(state, re)

        assert "channel output" in result["design_output"]

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_phase_output_recorded(self, mock_invoke, mock_prompt, mock_pool):
        """Should record a PARALLEL_GATHER phase output."""
        re = _mock_routing_engine()
        state = _make_state()

        mock_future = MagicMock()
        mock_future.result.return_value = FakeCLIResult(stdout="data", exit_code=0)
        mock_pool.submit.return_value = mock_future

        result = parallel_gather_node(state, re)

        gather_outputs = [p for p in result["phase_outputs"] if p["phase"] == "PARALLEL_GATHER"]
        assert len(gather_outputs) == 1
        assert gather_outputs[0]["status"] == PhaseStatus.COMPLETE.value

    @patch("src.workflows.base_workflow._thread_pool")
    @patch("src.workflows.base_workflow.build_prompt", return_value="mock prompt")
    @patch("src.workflows.base_workflow.cli_invoke")
    def test_routes_to_3_gather_agents(self, mock_invoke, mock_prompt, mock_pool):
        """Should call routing_engine.select for 3 different gather agents."""
        re = _mock_routing_engine()
        state = _make_state()

        mock_future = MagicMock()
        mock_future.result.return_value = FakeCLIResult(stdout="data", exit_code=0)
        mock_pool.submit.return_value = mock_future

        parallel_gather_node(state, re)

        agent_names = [call[0][0] for call in re.select.call_args_list]
        assert "gatherer_web" in agent_names
        assert "gatherer_code" in agent_names
        assert "gatherer_docs" in agent_names


# ============================================================
# 3.5 Review — No changes, sanity check
# ============================================================

class TestReviewWorkflowUnchanged:
    """Verify the Review workflow still compiles and has its original nodes."""

    def test_compiles_without_error(self):
        assert ReviewWorkflow().compile() is not None

    def test_has_original_nodes(self):
        graph = ReviewWorkflow().build_graph()
        nodes = set(graph.nodes)
        expected = {"analyze", "review", "report"}
        assert expected.issubset(nodes)


# ============================================================
# Decision function tests
# ============================================================

class TestConfigValidateDecision:
    def test_pass_when_verified(self):
        assert config_validate_decision({"verify_passed": True}) == "pass"

    def test_fail_when_not_verified(self):
        assert config_validate_decision({"verify_passed": False}) == "fail"

    def test_default_passes(self):
        assert config_validate_decision({}) == "pass"
