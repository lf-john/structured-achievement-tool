"""Tests for web-based approval forms and workflow integration.

Covers:
- Database CRUD for the approvals table
- Dashboard API endpoints (GET/POST approvals)
- Approval creation from human_task_workflow
- Approval completion updates workflow state
- Backward compatibility: signal file fallback when DB unavailable
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from src.db.database_manager import DatabaseManager
from src.workflows.approval_workflow import (
    ApprovalConfig,
    _create_db_approval,
    _poll_db_approval,
    approval_pause_node,
)
from src.workflows.human_task_workflow import generate_instructions_node
from src.workflows.state import create_initial_state

# --- Helpers ---


def _make_state(**overrides) -> dict:
    base = create_initial_state(
        story={"id": "US-200", "title": "Test web approval", "complexity": 3},
        task_id="task-200",
        task_description="Test web approval workflow",
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


def _temp_db() -> DatabaseManager:
    """Create a DatabaseManager backed by a temporary file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return DatabaseManager(db_path=path)


# ============================================================
# Database CRUD for Approvals
# ============================================================


class TestApprovalsCRUD:
    def setup_method(self):
        self.db = _temp_db()

    def test_create_approval(self):
        approval_id = self.db.create_approval(
            task_id="task-1",
            story_id="story-1",
            approval_type="human_action",
            title="Test Approval",
            instructions="Do the thing",
            form_fields=[{"name": "done", "type": "checkbox", "label": "Done?", "required": True}],
        )
        assert approval_id is not None
        assert len(approval_id) == 32  # uuid hex

    def test_get_approval(self):
        approval_id = self.db.create_approval(
            task_id="task-1",
            story_id="story-1",
            title="Test",
            instructions="Instructions here",
        )
        approval = self.db.get_approval(approval_id)
        assert approval is not None
        assert approval["title"] == "Test"
        assert approval["instructions"] == "Instructions here"
        assert approval["status"] == "pending"
        assert approval["task_id"] == "task-1"
        assert approval["story_id"] == "story-1"

    def test_get_approval_not_found(self):
        assert self.db.get_approval("nonexistent") is None

    def test_get_pending_approvals(self):
        self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        self.db.create_approval(task_id="t2", story_id="s2", title="A2")
        pending = self.db.get_pending_approvals()
        assert len(pending) == 2

    def test_get_pending_excludes_resolved(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        self.db.respond_to_approval(aid, "approved")
        self.db.create_approval(task_id="t2", story_id="s2", title="A2")
        pending = self.db.get_pending_approvals()
        assert len(pending) == 1
        assert pending[0]["title"] == "A2"

    def test_respond_to_approval_approve(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        result = self.db.respond_to_approval(aid, "approved", {"comment": "looks good"})
        assert result is True
        approval = self.db.get_approval(aid)
        assert approval["status"] == "approved"
        assert approval["response_data"]["comment"] == "looks good"

    def test_respond_to_approval_reject(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        result = self.db.respond_to_approval(aid, "rejected", {"comment": "bad plan"})
        assert result is True
        approval = self.db.get_approval(aid)
        assert approval["status"] == "rejected"

    def test_respond_to_approval_completed(self):
        aid = self.db.create_approval(
            task_id="t1",
            story_id="s1",
            approval_type="human_action",
            title="A1",
        )
        result = self.db.respond_to_approval(aid, "completed", {"completed": True, "notes": "done"})
        assert result is True
        approval = self.db.get_approval(aid)
        assert approval["status"] == "completed"

    def test_respond_to_already_resolved(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        self.db.respond_to_approval(aid, "approved")
        # Second response should fail
        result = self.db.respond_to_approval(aid, "rejected")
        assert result is False

    def test_respond_to_nonexistent(self):
        result = self.db.respond_to_approval("nonexistent", "approved")
        assert result is False

    def test_poll_approval_status_pending(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        assert self.db.poll_approval_status(aid) == "pending"

    def test_poll_approval_status_approved(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        self.db.respond_to_approval(aid, "approved")
        assert self.db.poll_approval_status(aid) == "approved"

    def test_poll_approval_status_nonexistent(self):
        assert self.db.poll_approval_status("nonexistent") is None

    def test_get_approvals_for_story(self):
        self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        self.db.create_approval(task_id="t1", story_id="s1", title="A2")
        self.db.create_approval(task_id="t2", story_id="s2", title="A3")
        approvals = self.db.get_approvals_for_story("s1")
        assert len(approvals) == 2

    def test_form_fields_json_roundtrip(self):
        fields = [
            {"name": "done", "type": "checkbox", "label": "Done?", "required": True},
            {"name": "notes", "type": "textarea", "label": "Notes", "required": False},
        ]
        aid = self.db.create_approval(
            task_id="t1",
            story_id="s1",
            title="A1",
            form_fields=fields,
        )
        approval = self.db.get_approval(aid)
        assert approval["form_fields"] == fields

    def test_system_status_includes_pending_approvals(self):
        self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        self.db.create_approval(task_id="t2", story_id="s2", title="A2")
        status = self.db.get_system_status()
        assert status["pending_approvals"] == 2

    def test_approval_creates_event(self):
        self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        events = self.db.get_recent_events()
        approval_events = [e for e in events if e["event_type"] == "approval_created"]
        assert len(approval_events) == 1

    def test_respond_creates_event(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        self.db.respond_to_approval(aid, "approved")
        events = self.db.get_recent_events()
        responded_events = [e for e in events if e["event_type"] == "approval_responded"]
        assert len(responded_events) == 1


# ============================================================
# Dashboard API Endpoints
# ============================================================


class TestDashboardApprovalAPI:
    def setup_method(self):
        self.db = _temp_db()
        # Patch the dashboard's _get_db to use our temp DB
        from src import dashboard

        self._original_db = dashboard._db
        dashboard._db = self.db
        dashboard.app.config["TESTING"] = True
        self.client = dashboard.app.test_client()

    def teardown_method(self):
        from src import dashboard

        dashboard._db = self._original_db

    def test_get_approvals_empty(self):
        resp = self.client.get("/api/approvals")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_get_approvals_with_pending(self):
        self.db.create_approval(task_id="t1", story_id="s1", title="Approval A")
        resp = self.client.get("/api/approvals")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Approval A"

    def test_get_approval_detail(self):
        aid = self.db.create_approval(
            task_id="t1",
            story_id="s1",
            title="Detail Test",
            form_fields=[{"name": "ok", "type": "checkbox", "label": "OK?"}],
        )
        resp = self.client.get(f"/api/approvals/{aid}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Detail Test"
        assert len(data["form_fields"]) == 1

    def test_get_approval_detail_not_found(self):
        resp = self.client.get("/api/approvals/nonexistent")
        assert resp.status_code == 404

    def test_post_approve(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        resp = self.client.post(
            f"/api/approvals/{aid}/respond",
            data=json.dumps({"status": "approved", "response_data": {"comment": "good"}}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["status"] == "approved"

    def test_post_reject(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        resp = self.client.post(
            f"/api/approvals/{aid}/respond",
            data=json.dumps({"status": "rejected", "response_data": {"comment": "bad"}}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "rejected"

    def test_post_completed(self):
        aid = self.db.create_approval(
            task_id="t1",
            story_id="s1",
            approval_type="human_action",
            title="A1",
        )
        resp = self.client.post(
            f"/api/approvals/{aid}/respond",
            data=json.dumps({"status": "completed", "response_data": {"completed": True}}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "completed"

    def test_post_missing_status(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        resp = self.client.post(
            f"/api/approvals/{aid}/respond",
            data=json.dumps({"response_data": {}}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_post_invalid_status(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        resp = self.client.post(
            f"/api/approvals/{aid}/respond",
            data=json.dumps({"status": "invalid"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_post_not_found(self):
        resp = self.client.post(
            "/api/approvals/nonexistent/respond",
            data=json.dumps({"status": "approved"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_post_already_resolved(self):
        aid = self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        self.db.respond_to_approval(aid, "approved")
        resp = self.client.post(
            f"/api/approvals/{aid}/respond",
            data=json.dumps({"status": "rejected"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_approvals_html_page(self):
        resp = self.client.get("/approvals")
        assert resp.status_code == 200
        assert b"SAT Approvals" in resp.data

    def test_dashboard_has_approvals_link(self):
        resp = self.client.get("/")
        assert resp.status_code == 200
        assert b"/approvals" in resp.data

    def test_status_includes_pending_approvals(self):
        self.db.create_approval(task_id="t1", story_id="s1", title="A1")
        resp = self.client.get("/api/status")
        data = resp.get_json()
        assert data["pending_approvals"] == 1


# ============================================================
# Approval Creation from Human Task Workflow
# ============================================================


class TestHumanTaskApprovalCreation:
    def test_generate_instructions_creates_db_approval(self):
        db = _temp_db()
        state = _make_state(
            human_task_response={
                "needs_human": True,
                "instructions": "Click the button",
                "required_inputs": [],
                "provider": "AWS",
                "documentation_url": "",
                "estimated_time_minutes": 5,
                "reason": "Manual step needed",
                "verification_checks": [],
            },
        )
        result = generate_instructions_node(state, _db_manager=db)

        # Should have created an approval_db_id in state
        assert "approval_db_id" in result
        approval_id = result["approval_db_id"]

        # Verify the approval exists in DB
        approval = db.get_approval(approval_id)
        assert approval is not None
        assert approval["approval_type"] == "human_action"
        assert approval["status"] == "pending"
        assert "completed" in str(approval["form_fields"])
        assert "notes" in str(approval["form_fields"])

    def test_generate_instructions_includes_dashboard_url(self):
        state = _make_state(
            human_task_response={
                "needs_human": True,
                "instructions": "Do stuff",
                "required_inputs": [],
                "provider": "",
                "documentation_url": "",
                "estimated_time_minutes": 0,
                "reason": "",
                "verification_checks": [],
            },
        )
        result = generate_instructions_node(state, _db_manager=None)
        assert "localhost:8765/approvals" in result["human_summary"]

    def test_generate_instructions_fallback_no_db(self):
        """When DB is unavailable, should still generate instructions without error."""
        state = _make_state(
            human_task_response={
                "needs_human": True,
                "instructions": "Step 1, Step 2",
                "required_inputs": [],
                "provider": "",
                "documentation_url": "",
                "estimated_time_minutes": 0,
                "reason": "",
                "verification_checks": [],
            },
        )
        # Patch _get_db_manager to return None (simulating DB unavailable)
        with patch("src.workflows.approval_workflow._get_db_manager", return_value=None):
            result = generate_instructions_node(state, _db_manager=None)

        # Instructions should still be generated
        assert "Step 1, Step 2" in result["human_summary"]
        # No approval_db_id since DB was unavailable
        assert "approval_db_id" not in result or result.get("approval_db_id") is None


# ============================================================
# Approval Completion Updates Workflow State
# ============================================================


class TestApprovalCompletionUpdatesWorkflow:
    def test_pause_node_picks_up_db_response(self):
        """When a user responds via the dashboard, the pause node should detect it."""
        db = _temp_db()
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=10)
        state = _make_state()

        # Pre-create an approval in DB
        approval_id = db.create_approval(
            task_id="task-200",
            story_id="US-200",
            approval_type="plan_review",
            title="Test",
        )

        def mock_create_approval(state, approval_type="plan_review", form_fields=None, db_manager=None):
            return approval_id

        poll_count = [0]
        original_poll = _poll_db_approval

        def mock_poll(aid, db_manager=None):
            poll_count[0] += 1
            if poll_count[0] >= 2:
                # Simulate user responding via dashboard
                db.respond_to_approval(aid, "approved", {"comment": "LGTM"})
            return original_poll(aid, db_manager=db)

        with patch("src.workflows.approval_workflow._create_db_approval", mock_create_approval):
            with patch("src.workflows.approval_workflow._poll_db_approval", mock_poll):
                result = approval_pause_node(
                    state,
                    ntf,
                    cfg,
                    _sleep_fn=_noop_sleep,
                    _write_fn=_noop_write,
                    _read_fn=lambda p: None,  # Signal file never responds
                    _db_manager=db,
                )

        assert result["approval_status"] == "responded"
        assert result["pause_response"] == "LGTM"

    def test_pause_node_db_rejection_produces_rejected_response(self):
        """Rejection via dashboard produces REJECTED: prefix in pause_response."""
        db = _temp_db()
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=10)
        state = _make_state()

        approval_id = db.create_approval(
            task_id="task-200",
            story_id="US-200",
            approval_type="plan_review",
            title="Test",
        )

        def mock_create(*a, **kw):
            return approval_id

        poll_count = [0]
        original_poll = _poll_db_approval

        def mock_poll(aid, db_manager=None):
            poll_count[0] += 1
            if poll_count[0] >= 2:
                db.respond_to_approval(aid, "rejected", {"comment": "needs rework"})
            return original_poll(aid, db_manager=db)

        with patch("src.workflows.approval_workflow._create_db_approval", mock_create):
            with patch("src.workflows.approval_workflow._poll_db_approval", mock_poll):
                result = approval_pause_node(
                    state,
                    ntf,
                    cfg,
                    _sleep_fn=_noop_sleep,
                    _write_fn=_noop_write,
                    _read_fn=lambda p: None,
                    _db_manager=db,
                )

        assert result["approval_status"] == "responded"
        assert result["pause_response"].startswith("REJECTED:")
        assert "needs rework" in result["pause_response"]

    def test_pause_node_notification_includes_dashboard_url(self):
        """Notification should include dashboard URL."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=2)
        state = _make_state()

        approval_pause_node(
            state,
            ntf,
            cfg,
            _sleep_fn=_noop_sleep,
            _write_fn=_noop_write,
            _read_fn=lambda p: None,
            _db_manager=None,
        )

        call_kwargs = ntf.send_ntfy.call_args[1]
        assert "localhost:8765/approvals" in call_kwargs["message"]


# ============================================================
# Backward Compatibility: Signal File Fallback
# ============================================================


class TestSignalFileFallback:
    def test_pause_node_falls_back_to_signal_file(self):
        """When DB is unavailable, should still work via signal files."""
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=10)
        state = _make_state()

        call_count = [0]

        def read_fn(path):
            call_count[0] += 1
            if call_count[0] >= 3:
                return "Response\n\n---\n\napproved\n\n<Pending>"
            return None

        with patch("src.workflows.approval_workflow._create_db_approval", return_value=None):
            result = approval_pause_node(
                state,
                ntf,
                cfg,
                _sleep_fn=_noop_sleep,
                _write_fn=_noop_write,
                _read_fn=read_fn,
                _db_manager=None,
            )

        assert result["approval_status"] == "responded"
        assert result["pause_response"] == "approved"

    def test_pause_node_signal_file_still_written_with_db(self):
        """Even when DB is available, signal file is still written for backward compat."""
        db = _temp_db()
        ntf = _mock_notifier()
        cfg = ApprovalConfig(poll_interval=1, follow_up_after=2, signal_dir="/tmp/test-signals")
        state = _make_state()

        written_paths = []

        def write_fn(path, content):
            written_paths.append(path)

        with patch("src.workflows.approval_workflow._create_db_approval", return_value=None):
            approval_pause_node(
                state,
                ntf,
                cfg,
                _sleep_fn=_noop_sleep,
                _write_fn=write_fn,
                _read_fn=lambda p: None,
                _db_manager=db,
            )

        assert len(written_paths) == 1
        assert "US-200_approval.md" in written_paths[0]

    def test_create_db_approval_returns_none_on_failure(self):
        """_create_db_approval should return None if DB fails."""
        state = _make_state()
        result = _create_db_approval(state, db_manager=None)
        # With no DB manager and _get_db_manager patched to fail
        with patch("src.workflows.approval_workflow._get_db_manager", return_value=None):
            result = _create_db_approval(state, db_manager=None)
        assert result is None

    def test_poll_db_approval_returns_none_on_failure(self):
        """_poll_db_approval should return None if DB fails."""
        with patch("src.workflows.approval_workflow._get_db_manager", return_value=None):
            result = _poll_db_approval("nonexistent", db_manager=None)
        assert result is None


# ============================================================
# Helper Function Tests
# ============================================================


class TestApprovalHelpers:
    def test_create_db_approval_with_db(self):
        db = _temp_db()
        state = _make_state(human_summary="Do the thing step by step")
        approval_id = _create_db_approval(
            state,
            approval_type="human_action",
            form_fields=[{"name": "done", "type": "checkbox"}],
            db_manager=db,
        )
        assert approval_id is not None
        approval = db.get_approval(approval_id)
        assert approval["approval_type"] == "human_action"
        assert approval["instructions"] == "Do the thing step by step"
        assert approval["story_id"] == "US-200"

    def test_poll_db_approval_pending(self):
        db = _temp_db()
        aid = db.create_approval(task_id="t1", story_id="s1", title="A1")
        result = _poll_db_approval(aid, db_manager=db)
        assert result is None  # Still pending

    def test_poll_db_approval_responded(self):
        db = _temp_db()
        aid = db.create_approval(task_id="t1", story_id="s1", title="A1")
        db.respond_to_approval(aid, "approved", {"comment": "good"})
        result = _poll_db_approval(aid, db_manager=db)
        assert result is not None
        assert result["status"] == "approved"
        assert result["response_data"]["comment"] == "good"
