"""Tests for src.agents.rca_agent — Root Cause Analysis agent."""

from unittest.mock import MagicMock

from src.agents.rca_agent import (
    RCAReport,
    analyze_failure_patterns,
    generate_escalation_story,
    should_trigger_rca,
)
from src.execution.audit_journal import AuditRecord


def _make_record(story_id="US-001", success=False, error_summary="", exit_code=1, task_file="task.md"):
    return AuditRecord(
        timestamp="2026-02-26T10:00:00",
        task_file=task_file,
        story_id=story_id,
        success=success,
        duration_seconds=10.0,
        exit_code=exit_code,
        error_summary=error_summary,
    )


class TestAnalyzeFailurePatterns:
    def test_empty_records(self):
        records = [_make_record(success=True)]
        report = analyze_failure_patterns(records, "US-001")
        assert report.failure_count == 0

    def test_single_failure(self):
        records = [_make_record(error_summary="ImportError: no module named foo")]
        report = analyze_failure_patterns(records, "US-001")
        assert report.failure_count == 1
        assert report.root_cause_category == "dependency"

    def test_multiple_failures_same_type(self):
        records = [
            _make_record(error_summary="ImportError: no module named foo"),
            _make_record(error_summary="ModuleNotFoundError: bar"),
            _make_record(error_summary="ImportError: baz not found"),
        ]
        report = analyze_failure_patterns(records, "US-001")
        assert report.failure_count == 3
        assert report.root_cause_category == "dependency"
        assert any("import_error" in p for p in report.common_patterns)

    def test_environment_failure(self):
        records = [
            _make_record(error_summary="Permission denied: /etc/config"),
            _make_record(error_summary="Permission error accessing path"),
        ]
        report = analyze_failure_patterns(records, "US-001")
        assert report.root_cause_category == "environment"

    def test_code_bug_failure(self):
        records = [
            _make_record(error_summary="AssertionError: expected 5, got 3"),
            _make_record(error_summary="TypeError: cannot add str and int"),
        ]
        report = analyze_failure_patterns(records, "US-001")
        assert report.root_cause_category == "code_bug"

    def test_resource_failure(self):
        records = [
            _make_record(error_summary="Out of memory, cannot allocate"),
        ]
        report = analyze_failure_patterns(records, "US-001")
        assert report.root_cause_category == "resource"

    def test_unknown_failure(self):
        records = [
            _make_record(error_summary="Something completely unexpected"),
        ]
        report = analyze_failure_patterns(records, "US-001")
        assert report.root_cause_category == "unknown"
        assert any("manual" in r.lower() for r in report.recommendations)

    def test_escalation_required_for_persistent(self):
        records = [
            _make_record(error_summary="AssertionError: test failed"),
            _make_record(error_summary="AssertionError: test failed"),
            _make_record(error_summary="AssertionError: test failed"),
        ]
        report = analyze_failure_patterns(records, "US-001")
        assert report.escalation_required is True

    def test_no_escalation_for_dependency(self):
        records = [
            _make_record(error_summary="ImportError: foo"),
            _make_record(error_summary="ImportError: foo"),
            _make_record(error_summary="ImportError: foo"),
        ]
        report = analyze_failure_patterns(records, "US-001")
        # dependency issues are usually self-fixable
        assert report.escalation_required is False

    def test_timeline_includes_timestamps(self):
        records = [_make_record(error_summary="Error")]
        report = analyze_failure_patterns(records, "US-001")
        assert len(report.failure_timeline) == 1
        assert "timestamp" in report.failure_timeline[0]

    def test_recommendations_present(self):
        records = [_make_record(error_summary="timeout after 300s")]
        report = analyze_failure_patterns(records, "US-001")
        assert len(report.recommendations) > 0

    def test_filters_by_story_id(self):
        records = [
            _make_record(story_id="US-001", error_summary="Error 1"),
            _make_record(story_id="US-002", error_summary="Error 2"),
        ]
        report = analyze_failure_patterns(records, "US-001")
        assert report.failure_count == 1


class TestShouldTriggerRCA:
    def test_triggers_after_threshold(self):
        journal = MagicMock()
        journal.query.return_value = [
            _make_record(success=False),
            _make_record(success=False),
            _make_record(success=False),
        ]
        assert should_trigger_rca(journal, "US-001", threshold=3) is True

    def test_does_not_trigger_below_threshold(self):
        journal = MagicMock()
        journal.query.return_value = [
            _make_record(success=False),
            _make_record(success=False),
        ]
        assert should_trigger_rca(journal, "US-001", threshold=3) is False

    def test_resets_on_success(self):
        journal = MagicMock()
        journal.query.return_value = [
            _make_record(success=True),   # Oldest
            _make_record(success=False),
            _make_record(success=False),
        ]
        # Most recent 2 are failures, but threshold is 3
        assert should_trigger_rca(journal, "US-001", threshold=3) is False

    def test_custom_threshold(self):
        journal = MagicMock()
        journal.query.return_value = [
            _make_record(success=False),
            _make_record(success=False),
            _make_record(success=False),
            _make_record(success=False),
            _make_record(success=False),
        ]
        assert should_trigger_rca(journal, "US-001", threshold=5) is True


class TestGenerateEscalationStory:
    def test_creates_valid_story(self):
        report = RCAReport(
            story_id="US-001",
            task_file="task.md",
            failure_count=3,
            root_cause_category="code_bug",
            root_cause_summary="3 consecutive test failures",
            common_patterns=["test_failure: 3/3"],
            recommendations=["Review test output"],
            escalation_required=True,
        )
        story = generate_escalation_story(report, "test-task")
        assert story["id"] == "US-001-rca"
        assert story["type"] == "escalation"
        assert "code_bug" in story["title"]
        assert len(story["acceptanceCriteria"]) == 3

    def test_debug_story_type(self):
        report = RCAReport(
            story_id="US-001",
            task_file="task.md",
            failure_count=3,
            root_cause_category="dependency",
            root_cause_summary="Import errors",
            escalation_required=False,
            suggested_story_type="debug",
        )
        story = generate_escalation_story(report, "test-task")
        assert story["type"] == "debug"
