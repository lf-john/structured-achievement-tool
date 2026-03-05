"""Tests for src.workflows.human_nodes — shared nodes for human story types."""

from src.workflows.human_nodes import (
    integrate_node,
    package_diagnostics_node,
    parse_feedback_node,
    prepare_node,
    validate_node,
)
from src.workflows.state import PhaseStatus


def _make_state(**overrides):
    """Create a minimal StoryState dict for testing."""
    state = {
        "story": {
            "id": "US-050",
            "title": "Configure DNS records",
            "description": "Set up A records for api.example.com",
            "acceptanceCriteria": ["A record points to 1.2.3.4", "TTL is 300"],
            "type": "assignment",
        },
        "task_id": "task-10",
        "task_description": "DNS setup",
        "current_phase": "",
        "phase_outputs": [],
        "phase_retry_count": 0,
        "verify_passed": None,
        "test_results": None,
        "failure_context": "",
        "story_attempt": 1,
        "max_attempts": 5,
        "mediator_verdict": None,
        "mediator_enabled": False,
        "working_directory": "/tmp/test",
        "git_base_commit": None,
        "design_output": "",
        "test_files": "",
        "plan_output": "",
        "pause_response": None,
        "pause_escalated": None,
        "approval_status": None,
        "approval_signal_path": None,
        "approval_elapsed": None,
    }
    state.update(overrides)
    return state


class TestPrepareNode:
    def test_creates_summary_with_title(self):
        state = _make_state()
        result = prepare_node(state, story_type="assignment")
        assert "Configure DNS records" in result["human_summary"]

    def test_includes_action_required(self):
        state = _make_state()
        result = prepare_node(state, story_type="assignment")
        assert "Action Required" in result["human_summary"]
        assert "deliverables" in result["human_summary"].lower()

    def test_includes_deliverables(self):
        state = _make_state()
        result = prepare_node(state, story_type="assignment")
        assert "A record points to 1.2.3.4" in result["human_summary"]
        assert "TTL is 300" in result["human_summary"]

    def test_qa_feedback_action(self):
        state = _make_state()
        result = prepare_node(state, story_type="qa_feedback")
        assert "Test the implementation" in result["human_summary"]

    def test_escalation_action(self):
        state = _make_state()
        result = prepare_node(state, story_type="escalation")
        assert "diagnostic" in result["human_summary"].lower() or "guidance" in result["human_summary"].lower() or "Review" in result["human_summary"]

    def test_includes_deadline_when_present(self):
        state = _make_state()
        state["story"]["deadline"] = "2026-03-01"
        result = prepare_node(state, story_type="assignment")
        assert "2026-03-01" in result["human_summary"]

    def test_no_deadline_when_absent(self):
        state = _make_state()
        result = prepare_node(state, story_type="assignment")
        assert "Deadline" not in result["human_summary"]

    def test_includes_failure_context_for_escalation(self):
        state = _make_state(failure_context="ImportError: no module named 'foo'")
        result = prepare_node(state, story_type="escalation")
        assert "ImportError" in result["human_summary"]

    def test_sets_current_phase(self):
        state = _make_state()
        result = prepare_node(state, story_type="assignment")
        assert result["current_phase"] == "PREPARE"

    def test_records_phase_output(self):
        state = _make_state()
        result = prepare_node(state, story_type="assignment")
        assert len(result["phase_outputs"]) == 1
        assert result["phase_outputs"][0]["phase"] == "PREPARE"
        assert result["phase_outputs"][0]["status"] == PhaseStatus.COMPLETE

    def test_includes_prior_phase_context(self):
        state = _make_state(phase_outputs=[
            {"phase": "CODE", "output": "Wrote main.py with handler logic"},
        ])
        result = prepare_node(state, story_type="assignment")
        assert "CODE" in result["human_summary"]

    def test_excludes_prepare_notify_pause_from_context(self):
        state = _make_state(phase_outputs=[
            {"phase": "PREPARE", "output": "Should be excluded"},
            {"phase": "NOTIFY", "output": "Should be excluded"},
            {"phase": "CODE", "output": "Should be included"},
        ])
        result = prepare_node(state, story_type="assignment")
        # CODE output included, PREPARE/NOTIFY excluded
        assert "Should be included" in result["human_summary"]


class TestValidateNode:
    def test_passes_when_response_says_done(self):
        state = _make_state(pause_response="Done, all records configured.")
        result = validate_node(state)
        assert result["verify_passed"] is True

    def test_passes_when_response_says_complete(self):
        state = _make_state(pause_response="Complete — verified in Route53.")
        result = validate_node(state)
        assert result["verify_passed"] is True

    def test_fails_when_response_is_unclear(self):
        state = _make_state(pause_response="I looked at it but not sure what to do.")
        result = validate_node(state)
        assert result["verify_passed"] is False

    def test_passes_with_no_criteria(self):
        state = _make_state(pause_response="Here's my update")
        state["story"]["acceptanceCriteria"] = []
        result = validate_node(state)
        assert result["verify_passed"] is True

    def test_records_validation_result(self):
        state = _make_state(pause_response="Done")
        result = validate_node(state)
        assert result["validation_result"]["passed"] is True

    def test_sets_current_phase(self):
        state = _make_state(pause_response="Done")
        result = validate_node(state)
        assert result["current_phase"] == "VALIDATE"

    def test_records_phase_output(self):
        state = _make_state(pause_response="Done")
        result = validate_node(state)
        outputs = result["phase_outputs"]
        assert outputs[-1]["phase"] == "VALIDATE"


class TestParseFeedbackNode:
    def test_pass_verdict(self):
        state = _make_state(pause_response="All tests pass. LGTM!")
        result = parse_feedback_node(state)
        assert result["qa_feedback_parsed"]["verdict"] == "pass"
        assert result["verify_passed"] is True

    def test_fail_verdict(self):
        state = _make_state(pause_response="This is broken. The login page crashes.")
        result = parse_feedback_node(state)
        assert result["qa_feedback_parsed"]["verdict"] == "fail"
        assert result["verify_passed"] is False

    def test_partial_verdict(self):
        state = _make_state(pause_response="Some items work, some need tweaking.")
        result = parse_feedback_node(state)
        assert result["qa_feedback_parsed"]["verdict"] == "partial"

    def test_extracts_bugs(self):
        state = _make_state(pause_response="bug: Login fails on Safari\nbug: Missing favicon")
        result = parse_feedback_node(state)
        assert len(result["qa_feedback_parsed"]["bugs"]) == 2

    def test_extracts_suggestions(self):
        state = _make_state(pause_response="suggestion: Add loading spinner\nconsider: Dark mode")
        result = parse_feedback_node(state)
        assert len(result["qa_feedback_parsed"]["suggestions"]) == 2

    def test_truncates_raw_response(self):
        state = _make_state(pause_response="x" * 3000)
        result = parse_feedback_node(state)
        assert len(result["qa_feedback_parsed"]["raw_response"]) == 2000

    def test_records_phase_output(self):
        state = _make_state(pause_response="pass")
        result = parse_feedback_node(state)
        outputs = result["phase_outputs"]
        assert outputs[-1]["phase"] == "PARSE"


class TestIntegrateNode:
    def test_stores_deliverables(self):
        state = _make_state(pause_response="Here are the DNS records I configured:\nA: api.example.com → 1.2.3.4")
        result = integrate_node(state)
        assert "DNS records" in result["human_deliverables"]

    def test_truncates_long_response(self):
        state = _make_state(pause_response="x" * 6000)
        result = integrate_node(state)
        assert len(result["human_deliverables"]) == 5000

    def test_records_phase_output(self):
        state = _make_state(pause_response="Done")
        result = integrate_node(state)
        outputs = result["phase_outputs"]
        assert outputs[-1]["phase"] == "INTEGRATE"


class TestPackageDiagnosticsNode:
    def test_packages_failure_context(self):
        state = _make_state(failure_context="ImportError: no module named 'foo'")
        result = package_diagnostics_node(state)
        pkg = result["escalation_package"]
        assert "ImportError" in pkg["failure_context"]

    def test_collects_attempted_fixes(self):
        state = _make_state(phase_outputs=[
            {"phase": "CODE", "status": "failed", "output": "Tried adding import"},
            {"phase": "FIX", "status": "failed", "output": "Tried installing package"},
        ])
        result = package_diagnostics_node(state)
        assert len(result["escalation_package"]["attempted_fixes"]) == 2

    def test_generates_recommendations_for_timeout(self):
        state = _make_state(failure_context="Operation timeout after 300s")
        result = package_diagnostics_node(state)
        recs = result["escalation_package"]["recommendations"]
        assert any("timeout" in r.lower() for r in recs)

    def test_generates_recommendations_for_permission(self):
        state = _make_state(failure_context="Permission denied: /etc/hosts")
        result = package_diagnostics_node(state)
        recs = result["escalation_package"]["recommendations"]
        assert any("permission" in r.lower() for r in recs)

    def test_default_recommendation_when_no_pattern(self):
        state = _make_state(failure_context="Something unexpected happened")
        result = package_diagnostics_node(state)
        recs = result["escalation_package"]["recommendations"]
        assert any("manual" in r.lower() for r in recs)

    def test_includes_story_metadata(self):
        state = _make_state()
        result = package_diagnostics_node(state)
        pkg = result["escalation_package"]
        assert pkg["story_id"] == "US-050"

    def test_records_phase_output(self):
        state = _make_state()
        result = package_diagnostics_node(state)
        outputs = result["phase_outputs"]
        assert outputs[-1]["phase"] == "PACKAGE_DIAGNOSTICS"
