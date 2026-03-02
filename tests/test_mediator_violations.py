"""
Mediator Gate Violation Stress Tests — Test all 3 cases with real git state.

Uses git to create "illegal" states and verifies the mediator gate correctly
identifies violations and takes appropriate action.

Verdicts: ACCEPT, REVERT, PARTIAL, RETRY (all 4 tested per case).
"""

import os
import subprocess
import pytest
from unittest.mock import MagicMock, patch

from src.workflows.base_workflow import mediator_gate_node
from src.workflows.state import MediatorVerdict


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repo with initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, capture_output=True, check=True,
    )

    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "src" / "main.py").write_text("def hello(): return 'hello'\n")
    (repo / "tests" / "test_main.py").write_text("def test_hello(): assert True\n")

    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True, check=True,
    )
    return str(repo)


def _make_state(working_dir, phase, mediator_enabled=True):
    return {
        "story": {"id": "test-story-1", "description": "test", "complexity": 3},
        "working_directory": working_dir,
        "current_phase": phase,
        "mediator_enabled": mediator_enabled,
        "phase_outputs": [],
    }


def _mock_response(decision, confidence=0.9, reasoning="test", guidance=None):
    resp = MagicMock()
    resp.decision.value = decision
    resp.confidence = confidence
    resp.reasoning = reasoning
    resp.retryGuidance = guidance
    return resp


class TestCase1TddRed:
    """Case 1: TDD_RED — code files modified → auto-revert (no LLM).

    Only 1 test needed: auto-revert is deterministic, no LLM verdicts.
    """

    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["src/main.py", "tests/test_main.py"])
    def test_code_modified_during_tdd_red_is_reverted(self, mock_modified, git_repo):
        src_file = os.path.join(git_repo, "src", "main.py")
        with open(src_file, "w") as f:
            f.write("def hello(): return 'MODIFIED'\n")

        state = _make_state(git_repo, "TDD_RED")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        verdict = result["mediator_verdict"]
        assert verdict["decision"] == "REVERT"
        assert "Auto-reverted" in verdict["reasoning"]

        with open(src_file) as f:
            assert f.read() == "def hello(): return 'hello'\n"


class TestCase2CodeAllVerdicts:
    """Case 2: CODE — test files modified → Mediator Agent reviews.

    Tests all 4 verdicts: ACCEPT, REVERT, PARTIAL, RETRY.
    """

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py"])
    def test_accept_verdict(self, mock_modified, mock_review, git_repo):
        test_file = os.path.join(git_repo, "tests", "test_main.py")
        with open(test_file, "w") as f:
            f.write("def test_hello(): assert hello() == 'changed'\n")

        mock_review.return_value = _mock_response("ACCEPT")

        state = _make_state(git_repo, "CODE")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "ACCEPT"
        assert mock_review.called

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py"])
    def test_revert_verdict_restores_files(self, mock_modified, mock_review, git_repo):
        test_file = os.path.join(git_repo, "tests", "test_main.py")
        original = open(test_file).read()

        with open(test_file, "w") as f:
            f.write("def test_hello(): assert False\n")

        mock_review.return_value = _mock_response("REVERT", reasoning="Tests weakened")

        state = _make_state(git_repo, "CODE")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "REVERT"
        with open(test_file) as f:
            assert f.read() == original

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py"])
    def test_partial_verdict(self, mock_modified, mock_review, git_repo):
        test_file = os.path.join(git_repo, "tests", "test_main.py")
        with open(test_file, "w") as f:
            f.write("def test_partial(): pass\n")

        mock_review.return_value = _mock_response("PARTIAL", reasoning="Some changes OK")

        state = _make_state(git_repo, "CODE")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "PARTIAL"

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py"])
    def test_retry_verdict_with_guidance(self, mock_modified, mock_review, git_repo):
        test_file = os.path.join(git_repo, "tests", "test_main.py")
        with open(test_file, "w") as f:
            f.write("def test_retry(): pass\n")

        mock_review.return_value = _mock_response(
            "RETRY", guidance="Redo without modifying tests"
        )

        state = _make_state(git_repo, "CODE")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "RETRY"
        assert result["mediator_verdict"]["retry_guidance"] == "Redo without modifying tests"


class TestCase3VerifyAllVerdicts:
    """Case 3: VERIFY — dual-category review.

    Tests all 4 verdicts for test files and code files independently,
    plus key combinations where verdicts differ across categories.
    """

    # --- Single-category tests (all 4 verdicts for test files) ---

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py"])
    def test_test_files_accept(self, mock_modified, mock_review, git_repo):
        mock_review.return_value = _mock_response("ACCEPT")
        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] == "ACCEPT"

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py"])
    def test_test_files_revert(self, mock_modified, mock_review, git_repo):
        test_file = os.path.join(git_repo, "tests", "test_main.py")
        original = open(test_file).read()
        with open(test_file, "w") as f:
            f.write("CORRUPTED\n")

        mock_review.return_value = _mock_response("REVERT")
        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "REVERT"
        with open(test_file) as f:
            assert f.read() == original

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py"])
    def test_test_files_partial(self, mock_modified, mock_review, git_repo):
        mock_review.return_value = _mock_response("PARTIAL")
        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        # PARTIAL is treated like ACCEPT (not REVERT or RETRY)
        assert result["mediator_verdict"]["decision"] in ("PARTIAL", "ACCEPT")

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py"])
    def test_test_files_retry(self, mock_modified, mock_review, git_repo):
        mock_review.return_value = _mock_response("RETRY", guidance="Fix tests")
        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] == "RETRY"

    # --- Single-category tests (all 4 verdicts for code files) ---

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["src/main.py"])
    def test_code_files_accept(self, mock_modified, mock_review, git_repo):
        mock_review.return_value = _mock_response("ACCEPT")
        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] == "ACCEPT"

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["src/main.py"])
    def test_code_files_revert(self, mock_modified, mock_review, git_repo):
        src_file = os.path.join(git_repo, "src", "main.py")
        original = open(src_file).read()
        with open(src_file, "w") as f:
            f.write("CORRUPTED\n")

        mock_review.return_value = _mock_response("REVERT")
        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "REVERT"
        with open(src_file) as f:
            assert f.read() == original

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["src/main.py"])
    def test_code_files_partial(self, mock_modified, mock_review, git_repo):
        mock_review.return_value = _mock_response("PARTIAL")
        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] in ("PARTIAL", "ACCEPT")

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["src/main.py"])
    def test_code_files_retry(self, mock_modified, mock_review, git_repo):
        mock_review.return_value = _mock_response("RETRY", guidance="Fix code")
        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] == "RETRY"

    # --- Cross-category combination tests ---

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py", "src/main.py"])
    def test_both_accept(self, mock_modified, mock_review, git_repo):
        mock_review.return_value = _mock_response("ACCEPT")
        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] == "ACCEPT"
        assert mock_review.call_count == 2

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py", "src/main.py"])
    def test_test_accept_code_revert(self, mock_modified, mock_review, git_repo):
        """ACCEPT tests + REVERT code → combined REVERT."""
        src_file = os.path.join(git_repo, "src", "main.py")
        original_src = open(src_file).read()
        with open(src_file, "w") as f:
            f.write("BAD CODE\n")

        mock_review.side_effect = [
            _mock_response("ACCEPT"),
            _mock_response("REVERT"),
        ]

        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())

        assert result["mediator_verdict"]["decision"] == "REVERT"
        with open(src_file) as f:
            assert f.read() == original_src

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py", "src/main.py"])
    def test_test_retry_code_accept(self, mock_modified, mock_review, git_repo):
        """RETRY tests + ACCEPT code → combined RETRY."""
        mock_review.side_effect = [
            _mock_response("RETRY", guidance="Fix tests"),
            _mock_response("ACCEPT"),
        ]

        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] == "RETRY"

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py", "src/main.py"])
    def test_revert_overrides_retry(self, mock_modified, mock_review, git_repo):
        """RETRY tests + REVERT code → REVERT wins (stronger)."""
        mock_review.side_effect = [
            _mock_response("RETRY"),
            _mock_response("REVERT"),
        ]

        state = _make_state(git_repo, "VERIFY")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] == "REVERT"


class TestEdgeCases:
    """Disabled mediator, errors, no modifications."""

    def test_disabled_mediator_accepts(self, git_repo):
        state = _make_state(git_repo, "CODE", mediator_enabled=False)
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] == "ACCEPT"

    @patch("src.workflows.base_workflow._invoke_mediator_review")
    @patch("src.workflows.base_workflow.get_modified_files",
           return_value=["tests/test_main.py"])
    def test_error_falls_back_to_accept(self, mock_modified, mock_review, git_repo):
        mock_review.side_effect = Exception("LLM timeout")
        state = _make_state(git_repo, "CODE")
        result = mediator_gate_node(state, routing_engine=MagicMock())
        assert result["mediator_verdict"]["decision"] == "ACCEPT"
        assert "Error" in result["mediator_verdict"]["reasoning"]
