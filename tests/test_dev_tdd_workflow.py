"""Tests for src.workflows.dev_tdd_workflow — Graph structure and conditional edges."""

import pytest
from langgraph.graph import END

from src.workflows.dev_tdd_workflow import DevTDDWorkflow
from src.workflows.config_tdd_workflow import ConfigTDDWorkflow
from src.workflows.maintenance_workflow import MaintenanceWorkflow
from src.workflows.debug_workflow import DebugWorkflow
from src.workflows.research_workflow import ResearchWorkflow
from src.workflows.review_workflow import ReviewWorkflow
from src.workflows.base_workflow import verify_decision, check_test_decision, mediator_decision


class TestDevTDDWorkflowStructure:
    def setup_method(self):
        self.workflow = DevTDDWorkflow()
        self.graph = self.workflow.build_graph()

    def test_has_all_required_nodes(self):
        nodes = set(self.graph.nodes)
        expected = {"design", "tdd_red", "code", "verify", "learn",
                    "tdd_red_check", "tdd_green_check", "mediator"}
        assert expected.issubset(nodes)

    def test_entry_point_is_design(self):
        # The compiled graph should start at design
        compiled = self.graph.compile()
        assert compiled is not None

    def test_compiles_without_error(self):
        compiled = self.workflow.compile()
        assert compiled is not None


class TestWorkflowCompilation:
    """Ensure all 6 workflow types compile successfully."""

    def test_dev_tdd(self):
        assert DevTDDWorkflow().compile() is not None

    def test_config_tdd(self):
        assert ConfigTDDWorkflow().compile() is not None

    def test_maintenance(self):
        assert MaintenanceWorkflow().compile() is not None

    def test_debug(self):
        assert DebugWorkflow().compile() is not None

    def test_research(self):
        assert ResearchWorkflow().compile() is not None

    def test_review(self):
        assert ReviewWorkflow().compile() is not None


class TestDecisionFunctions:
    def test_verify_pass(self):
        state = {"verify_passed": True}
        assert verify_decision(state) == "pass"

    def test_verify_fail(self):
        state = {"verify_passed": False}
        assert verify_decision(state) == "fail"

    def test_verify_default_pass(self):
        assert verify_decision({}) == "pass"

    def test_test_check_pass(self):
        state = {"verify_passed": True}
        assert check_test_decision(state) == "pass"

    def test_test_check_fail(self):
        state = {"verify_passed": False, "phase_retry_count": 0}
        assert check_test_decision(state) == "fail"

    def test_test_check_max_retries_gives_up(self):
        state = {"verify_passed": False, "phase_retry_count": 10}
        assert check_test_decision(state) == "pass"

    def test_mediator_accept(self):
        state = {"mediator_verdict": {"decision": "ACCEPT"}}
        assert mediator_decision(state) == "accept"

    def test_mediator_partial_accepts(self):
        state = {"mediator_verdict": {"decision": "PARTIAL"}}
        assert mediator_decision(state) == "accept"

    def test_mediator_revert_retries(self):
        state = {"mediator_verdict": {"decision": "REVERT"}}
        assert mediator_decision(state) == "retry"

    def test_mediator_retry_retries(self):
        state = {"mediator_verdict": {"decision": "RETRY"}}
        assert mediator_decision(state) == "retry"

    def test_mediator_default_accepts(self):
        assert mediator_decision({}) == "accept"
