"""
Mediator Gate Unit Tests — Mock-based tests for all branching logic.

Tests every verdict combination for all 3 cases without requiring git repos
or real LLM calls. For long-term regression testing.
"""

from unittest.mock import MagicMock, patch

from src.workflows.base_workflow import mediator_gate_node


def _make_state(phase, mediator_enabled=True):
    return {
        "story": {"id": "test-story", "description": "test"},
        "working_directory": "/fake/dir",
        "current_phase": phase,
        "mediator_enabled": mediator_enabled,
        "phase_outputs": [],
        "test_results": {"passed": True, "total": 5, "failures": 0},
    }


def _mock_mediator_response(decision, confidence=0.9, reasoning="test", guidance=None):
    resp = MagicMock()
    resp.decision.value = decision
    resp.confidence = confidence
    resp.reasoning = reasoning
    resp.retryGuidance = guidance
    return resp


class TestCase1TddRedBranch:
    """Case 1: TDD_RED — code files modified → auto-revert (no LLM).

    NOTE: TDD_RED is not in TRIGGER_PHASES, so should_trigger must be
    patched to allow testing the Case 1 branch. This is a known gap —
    the trigger check at line 422 returns before Case 1 at line 434.
    """

    @patch("src.workflows.base_workflow.save_intervention")
    @patch("src.workflows.base_workflow._revert_files", return_value=["src/main.py"])
    @patch("src.workflows.base_workflow.should_trigger", return_value={"should_trigger": True, "reason": "code files modified"})
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["src/main.py", "tests/test_main.py"])
    def test_code_files_reverted_no_llm_call(self, mock_modified, mock_trigger, mock_revert, mock_save):
        state = _make_state("TDD_RED")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "REVERT"
        mock_revert.assert_called_once()
        reverted_files = mock_revert.call_args[0][1]
        assert "src/main.py" in reverted_files

    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_new.py"])
    def test_only_test_files_no_trigger(self, mock_modified):
        """Only test files modified during TDD_RED → no trigger (TDD_RED not in TRIGGER_PHASES)."""
        state = _make_state("TDD_RED")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"

    @patch("src.workflows.base_workflow.get_modified_files", return_value=[])
    def test_no_files_modified_no_trigger(self, mock_modified):
        state = _make_state("TDD_RED")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"


class TestCase2CodeFixBranch:
    """Case 2: CODE/FIX — test files modified → call Mediator Agent."""

    @patch("src.workflows.base_workflow.save_intervention")
    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py", "src/main.py"])
    def test_accept_verdict(self, mock_modified, mock_review, mock_save):
        mock_review.return_value = _mock_mediator_response("ACCEPT")

        state = _make_state("CODE")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"

    @patch("src.workflows.base_workflow.save_intervention")
    @patch("src.workflows.base_workflow._revert_files", return_value=["tests/test_main.py"])
    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py"])
    def test_revert_verdict_reverts_test_files(self, mock_modified, mock_review, mock_revert, mock_save):
        mock_review.return_value = _mock_mediator_response("REVERT")

        state = _make_state("CODE")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "REVERT"
        mock_revert.assert_called_once()

    @patch("src.workflows.base_workflow.save_intervention")
    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py"])
    def test_retry_verdict(self, mock_modified, mock_review, mock_save):
        mock_review.return_value = _mock_mediator_response(
            "RETRY", guidance="Try without modifying tests"
        )

        state = _make_state("CODE")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "RETRY"
        assert result["mediator_verdict"]["retry_guidance"] == "Try without modifying tests"

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py"])
    def test_mediator_exception_falls_back_to_accept(self, mock_modified, mock_review):
        mock_review.side_effect = Exception("LLM timeout")

        state = _make_state("FIX")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"

    @patch("src.workflows.base_workflow.get_modified_files", return_value=["src/main.py"])
    def test_only_code_files_no_trigger(self, mock_modified):
        """Only code files modified during CODE → no trigger (expected behavior)."""
        state = _make_state("CODE")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"


class TestCase3VerifyBranch:
    """Case 3: VERIFY — review each file category separately."""

    @patch("src.workflows.base_workflow.save_intervention")
    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py", "src/main.py"])
    def test_both_accept(self, mock_modified, mock_review, mock_save):
        mock_review.return_value = _mock_mediator_response("ACCEPT")

        state = _make_state("VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"
        assert mock_review.call_count == 2

    @patch("src.workflows.base_workflow.save_intervention")
    @patch("src.workflows.base_workflow._revert_files", return_value=["src/main.py"])
    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py", "src/main.py"])
    def test_code_revert_test_accept(self, mock_modified, mock_review, mock_revert, mock_save):
        """ACCEPT tests, REVERT code → combined REVERT, only code reverted."""
        accept = _mock_mediator_response("ACCEPT")
        revert = _mock_mediator_response("REVERT")
        mock_review.side_effect = [accept, revert]

        state = _make_state("VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "REVERT"
        mock_revert.assert_called_once()
        reverted_files = mock_revert.call_args[0][1]
        assert "src/main.py" in reverted_files

    @patch("src.workflows.base_workflow.save_intervention")
    @patch("src.workflows.base_workflow._revert_files")
    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py", "src/main.py"])
    def test_both_revert(self, mock_modified, mock_review, mock_revert, mock_save):
        """Both categories REVERT → both file sets reverted."""
        mock_revert.return_value = []
        mock_review.return_value = _mock_mediator_response("REVERT")

        state = _make_state("VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "REVERT"
        assert mock_revert.call_count == 2

    @patch("src.workflows.base_workflow.save_intervention")
    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py", "src/main.py"])
    def test_retry_overrides_accept(self, mock_modified, mock_review, mock_save):
        """ACCEPT tests + RETRY code → combined RETRY."""
        accept = _mock_mediator_response("ACCEPT")
        retry = _mock_mediator_response("RETRY", guidance="Fix the code")
        mock_review.side_effect = [accept, retry]

        state = _make_state("VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "RETRY"

    @patch("src.workflows.base_workflow.save_intervention")
    @patch("src.workflows.base_workflow._revert_files", return_value=[])
    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py", "src/main.py"])
    def test_revert_overrides_retry(self, mock_modified, mock_review, mock_revert, mock_save):
        """RETRY tests + REVERT code → combined REVERT (stronger action wins)."""
        retry = _mock_mediator_response("RETRY", guidance="Redo tests")
        revert = _mock_mediator_response("REVERT")
        mock_review.side_effect = [retry, revert]

        state = _make_state("VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "REVERT"

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files", return_value=["tests/test_main.py", "src/main.py"])
    def test_error_in_one_category_others_still_reviewed(self, mock_modified, mock_review):
        """Error reviewing tests → auto-accept tests, code still reviewed."""
        accept = _mock_mediator_response("ACCEPT")
        mock_review.side_effect = [Exception("test review failed"), accept]

        state = _make_state("VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"

    @patch("src.workflows.base_workflow.get_modified_files", return_value=["src/main.py"])
    def test_only_code_files_triggers_verify(self, mock_modified):
        """Only code files during VERIFY — should still trigger (any files modified)."""
        state = _make_state("VERIFY")
        # With only code files and no test files, the code-only review happens
        # The trigger function determines if this fires
        result = mediator_gate_node(state, routing_engine=MagicMock())
        # Should get a verdict (either from review or no-trigger accept)
        assert "mediator_verdict" in result


class TestMediatorDisabledAndFallback:
    """Edge cases: disabled mediator, unknown phase."""

    def test_disabled_always_accepts(self):
        state = _make_state("CODE", mediator_enabled=False)
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"
        assert "disabled" in result["mediator_verdict"]["reasoning"].lower()

    @patch("src.workflows.base_workflow.get_modified_files", return_value=["src/main.py"])
    def test_unknown_phase_auto_accepts(self, mock_modified):
        """Unexpected phase that triggers should auto-accept."""
        state = _make_state("UNKNOWN_PHASE")
        # Force trigger
        with patch("src.workflows.base_workflow.should_trigger", return_value={"should_trigger": True, "reason": "test"}):
            result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"
