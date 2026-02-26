"""Tests for the Approval Workflow (3.10 redesign).

Covers:
- ApprovalConfig defaults and customization
- Normal path: PAUSE → FOLLOW_UP → ESCALATION
- Emergency path: PAUSE → ESCALATION (skip follow-up, auto-approve on timeout)
- Human response at each stage
- Decision routing functions
- Graph structure for both paths
"""

import pytest
from unittest.mock import MagicMock, patch, call

from src.workflows.state import create_initial_state, PhaseStatus
from src.workflows.approval_workflow import (
    ApprovalConfig,
    ApprovalWorkflow,
    approval_pause_node,
    approval_follow_up_node,
    approval_escalation_node,
    pause_initial_decision,
    follow_up_decision,
    response_decision,
)


# --- Helpers ---

def _make_state(**overrides) -> dict:
    base = create_initial_state(
        story={"id": "US-100", "title": "Test approval", "complexity": 3},
        task_id="task-100",
        task_description="Test approval workflow",
        working_directory="/tmp/test",
    )
    base = dict(base)
    base.update(overrides)
    return base


def _mock_notifier():
    ntf = MagicMock()
    ntf.send_ntfy.return_value = True
    ntf.send_email.return_value = True
    return ntf


def _noop_sleep(seconds):
    pass


def _noop_write(path, content):
    pass


# ============================================================
# ApprovalConfig
# ============================================================

class TestApprovalConfig:
    def test_defaults(self):
        cfg = ApprovalConfig()
        assert cfg.poll_interval == 30
        assert cfg.follow_up_after == 3600
        assert cfg.escalation_after == 7200
        assert cfg.auto_timeout == 14400
        assert cfg.emergency is False
        assert cfg.auto_approve_on_timeout is False

    def test_emergency_config(self):
        cfg = ApprovalConfig(emergency=True, auto_approve_on_timeout=True)
        assert cfg.emergency is True
        assert cfg.auto_approve_on_timeout is True

    def test_custom_timing(self):
        cfg = ApprovalConfig(poll_interval=10, follow_up_after=60, escalation_after=120)
        assert cfg.poll_interval == 10
        assert cfg.follow_up_after == 60
        assert cfg.escalation_after == 120


# ============================================================
# approval_pause_node
# ============================================================

class TestApprovalPauseNode:
    def test_immediate_response(self):
        """Human responds during initial pause."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=10)
        state = _make_state()

        call_count = [0]
        def read_fn(path):
            call_count[0] += 1
            if call_count[0] >= 2:
                return "Approved\n\n---\n\nLooks good\n\n<Pending>"
            return None

        result = approval_pause_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _write_fn=_noop_write, _read_fn=read_fn,
        )

        assert result["approval_status"] == "responded"
        assert result["pause_response"] == "Looks good"

    def test_no_response_returns_waiting(self):
        """No human response within follow_up_after returns 'waiting'."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=3)
        state = _make_state()

        result = approval_pause_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _write_fn=_noop_write,
            _read_fn=lambda p: None,
        )

        assert result["approval_status"] == "waiting"
        assert result["pause_response"] == "no_response"

    def test_signal_file_written(self):
        """Signal file should be written with correct path."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=2, signal_dir="/tmp/test-signals")
        state = _make_state()

        written_paths = []
        def write_fn(path, content):
            written_paths.append(path)

        approval_pause_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _write_fn=write_fn,
            _read_fn=lambda p: None,
        )

        assert len(written_paths) == 1
        assert "US-100_approval.md" in written_paths[0]

    def test_notification_sent(self):
        """Initial notification should be sent via ntfy."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=2)
        state = _make_state()

        approval_pause_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _write_fn=_noop_write,
            _read_fn=lambda p: None,
        )

        ntf.send_ntfy.assert_called_once()
        call_kwargs = ntf.send_ntfy.call_args[1]
        assert "US-100" in call_kwargs["title"]

    def test_emergency_priority(self):
        """Emergency config should use urgent priority."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=2, emergency=True, escalation_after=3)
        state = _make_state()

        approval_pause_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _write_fn=_noop_write,
            _read_fn=lambda p: None,
        )

        call_kwargs = ntf.send_ntfy.call_args[1]
        assert call_kwargs["priority"] == "urgent"
        assert "EMERGENCY" in call_kwargs["title"]


# ============================================================
# approval_follow_up_node
# ============================================================

class TestApprovalFollowUpNode:
    def test_response_during_follow_up(self):
        """Human responds during follow-up period."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=10, escalation_after=20)
        state = _make_state(approval_signal_path="/tmp/signal.md", approval_elapsed=10)

        call_count = [0]
        def read_fn(path):
            call_count[0] += 1
            if call_count[0] >= 3:
                return "Approved\n\n---\n\nOK\n\n<Pending>"
            return None

        result = approval_follow_up_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _read_fn=read_fn,
        )

        assert result["approval_status"] == "responded"

    def test_no_response_returns_waiting(self):
        """No response during follow-up returns waiting."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=5, escalation_after=10)
        state = _make_state(approval_signal_path="/tmp/signal.md", approval_elapsed=5)

        result = approval_follow_up_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _read_fn=lambda p: None,
        )

        assert result["approval_status"] == "waiting"

    def test_follow_up_notification_sent(self):
        """Follow-up notification should be sent."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=5, escalation_after=8)
        state = _make_state(approval_signal_path="/tmp/signal.md", approval_elapsed=5)

        approval_follow_up_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _read_fn=lambda p: None,
        )

        ntf.send_ntfy.assert_called_once()
        assert "Follow-up" in ntf.send_ntfy.call_args[1]["title"]


# ============================================================
# approval_escalation_node
# ============================================================

class TestApprovalEscalationNode:
    def test_response_during_escalation(self):
        """Human responds during escalation period."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, escalation_after=10, auto_timeout=20)
        state = _make_state(approval_signal_path="/tmp/signal.md", approval_elapsed=10)

        call_count = [0]
        def read_fn(path):
            call_count[0] += 1
            if call_count[0] >= 2:
                return "Response\n\n---\n\napproved\n\n<Pending>"
            return None

        result = approval_escalation_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _read_fn=read_fn,
        )

        assert result["approval_status"] == "responded"
        assert result["pause_escalated"] is True

    def test_timeout_no_auto_approve(self):
        """Normal path: timeout without auto-approve returns 'timeout'."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(
            poll_interval=1, escalation_after=5, auto_timeout=10,
            auto_approve_on_timeout=False,
        )
        state = _make_state(approval_signal_path="/tmp/signal.md", approval_elapsed=5)

        result = approval_escalation_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _read_fn=lambda p: None,
        )

        assert result["approval_status"] == "timeout"
        assert result["pause_response"] == "no_response"

    def test_timeout_auto_approve(self):
        """Emergency path: timeout with auto-approve returns 'auto_approved'."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(
            poll_interval=1, escalation_after=5, auto_timeout=10,
            auto_approve_on_timeout=True, emergency=True,
        )
        state = _make_state(approval_signal_path="/tmp/signal.md", approval_elapsed=5)

        result = approval_escalation_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _read_fn=lambda p: None,
        )

        assert result["approval_status"] == "auto_approved"
        assert result["pause_response"] == "auto_approved"

    def test_escalation_notification_sent(self):
        """Escalation notification should be urgent."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, escalation_after=5, auto_timeout=8)
        state = _make_state(approval_signal_path="/tmp/signal.md", approval_elapsed=5)

        approval_escalation_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _read_fn=lambda p: None,
        )

        call_kwargs = ntf.send_ntfy.call_args[1]
        assert call_kwargs["priority"] == "urgent"
        assert "ESCALATION" in call_kwargs["title"]

    def test_escalation_contacts_emailed(self):
        """Additional escalation contacts should receive email."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(
            poll_interval=1, escalation_after=5, auto_timeout=8,
            escalation_contacts=["admin@example.com", "ops@example.com"],
        )
        state = _make_state(approval_signal_path="/tmp/signal.md", approval_elapsed=5)

        approval_escalation_node(
            state, ntf, cfg,
            _sleep_fn=_noop_sleep, _read_fn=lambda p: None,
        )

        assert ntf.send_email.call_count == 2


# ============================================================
# Decision Functions
# ============================================================

class TestPauseInitialDecision:
    def test_responded(self):
        assert pause_initial_decision({"approval_status": "responded"}) == "responded"

    def test_waiting_goes_to_follow_up(self):
        assert pause_initial_decision({"approval_status": "waiting"}) == "follow_up"

    def test_default_goes_to_follow_up(self):
        assert pause_initial_decision({}) == "follow_up"


class TestFollowUpDecision:
    def test_responded(self):
        assert follow_up_decision({"approval_status": "responded"}) == "responded"

    def test_waiting_escalates(self):
        assert follow_up_decision({"approval_status": "waiting"}) == "escalate"


class TestResponseDecision:
    def test_approved(self):
        assert response_decision({"pause_response": "looks good"}) == "approved"

    def test_rejected(self):
        assert response_decision({"pause_response": "REJECTED: bad code"}) == "rejected"

    def test_timeout(self):
        assert response_decision({"pause_response": "no_response"}) == "timeout"

    def test_auto_approved(self):
        assert response_decision({"pause_response": "auto_approved"}) == "approved"

    def test_default_timeout(self):
        assert response_decision({}) == "timeout"


# ============================================================
# Workflow Graph Structure
# ============================================================

class TestApprovalWorkflowNormalPath:
    """Test the Normal path graph structure."""

    def setup_method(self):
        ntf = _mock_notifier()
        cfg = ApprovalConfig(emergency=False)
        self.workflow = ApprovalWorkflow(notifier=ntf, config=cfg)
        self.graph = self.workflow.build_graph()

    def test_has_pause_node(self):
        assert "pause" in self.graph.nodes

    def test_has_follow_up_node(self):
        assert "follow_up" in self.graph.nodes

    def test_has_escalation_node(self):
        assert "escalation" in self.graph.nodes

    def test_has_3_nodes(self):
        our_nodes = {n for n in self.graph.nodes if not n.startswith("__")}
        assert len(our_nodes) == 3

    def test_compiles(self):
        assert self.workflow.compile() is not None


class TestApprovalWorkflowEmergencyPath:
    """Test the Emergency path graph structure."""

    def setup_method(self):
        ntf = _mock_notifier()
        cfg = ApprovalConfig(emergency=True, auto_approve_on_timeout=True)
        self.workflow = ApprovalWorkflow(notifier=ntf, config=cfg)
        self.graph = self.workflow.build_graph()

    def test_has_pause_node(self):
        assert "pause" in self.graph.nodes

    def test_has_escalation_node(self):
        assert "escalation" in self.graph.nodes

    def test_has_follow_up_node_but_not_used(self):
        """Follow-up node exists but emergency path skips it."""
        assert "follow_up" in self.graph.nodes

    def test_compiles(self):
        assert self.workflow.compile() is not None

    def test_emergency_auto_approve(self):
        """Emergency with auto_approve should set config correctly."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(emergency=True, auto_approve_on_timeout=True)
        wf = ApprovalWorkflow(notifier=ntf, config=cfg)
        assert wf.config.auto_approve_on_timeout is True
