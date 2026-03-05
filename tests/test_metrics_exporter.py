"""Tests for src.monitoring.metrics_exporter — Prometheus metrics."""

from unittest.mock import MagicMock

from src.execution.audit_journal import AuditRecord
from src.monitoring.metrics_exporter import (
    MetricsSnapshot,
    _classify_error,
    collect_metrics,
    format_prometheus,
)


def _make_record(success=True, error_summary="", duration=10.0, story_id="US-001", task_file="task.md"):
    return AuditRecord(
        timestamp="2026-02-26T10:00:00",
        task_file=task_file,
        story_id=story_id,
        success=success,
        duration_seconds=duration,
        exit_code=0 if success else 1,
        error_summary=error_summary,
    )


class TestCollectMetrics:
    def test_counts_success_and_failure(self):
        journal = MagicMock()
        journal.query.return_value = [
            _make_record(success=True),
            _make_record(success=True),
            _make_record(success=False, error_summary="test failed"),
        ]
        snapshot = collect_metrics(journal)
        assert snapshot.stories_succeeded == 2
        assert snapshot.stories_failed == 1
        assert snapshot.stories_total == 3

    def test_calculates_avg_duration(self):
        journal = MagicMock()
        journal.query.return_value = [
            _make_record(duration=10.0),
            _make_record(duration=20.0),
        ]
        snapshot = collect_metrics(journal)
        assert snapshot.avg_duration_seconds == 15.0

    def test_counts_failure_types(self):
        journal = MagicMock()
        journal.query.return_value = [
            _make_record(success=False, error_summary="timeout after 300s"),
            _make_record(success=False, error_summary="timeout on API call"),
            _make_record(success=False, error_summary="ImportError: foo"),
        ]
        snapshot = collect_metrics(journal)
        assert snapshot.failure_type_counts.get("timeout", 0) == 2
        assert snapshot.failure_type_counts.get("import_error", 0) == 1

    def test_empty_journal(self):
        journal = MagicMock()
        journal.query.return_value = []
        snapshot = collect_metrics(journal)
        assert snapshot.stories_total == 0
        assert snapshot.avg_duration_seconds == 0.0

    def test_queue_depth_counted(self, tmp_path):
        # Create a mock task directory with pending files
        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        pending_file = task_dir / "001_test.md"
        pending_file.write_text("Some task\n<Pending>\n")

        journal = MagicMock()
        journal.query.return_value = []
        snapshot = collect_metrics(journal, queue_dir=str(tmp_path))
        assert snapshot.queue_depth == 1


class TestFormatPrometheus:
    def test_includes_all_metrics(self):
        snapshot = MetricsSnapshot(
            stories_succeeded=5,
            stories_failed=2,
            avg_duration_seconds=15.5,
            tasks_completed=3,
            tasks_failed=1,
            queue_depth=2,
            system_healthy=True,
            uptime_seconds=3600.0,
        )
        output = format_prometheus(snapshot)
        assert 'sat_stories_total{status="succeeded"} 5' in output
        assert 'sat_stories_total{status="failed"} 2' in output
        assert "sat_stories_avg_duration_seconds 15.50" in output
        assert "sat_queue_depth 2" in output
        assert "sat_system_healthy 1" in output
        assert "sat_uptime_seconds 3600" in output

    def test_includes_failure_types(self):
        snapshot = MetricsSnapshot(
            failure_type_counts={"timeout": 3, "import_error": 1},
        )
        output = format_prometheus(snapshot)
        assert 'sat_failure_types{type="timeout"} 3' in output
        assert 'sat_failure_types{type="import_error"} 1' in output

    def test_prometheus_format_structure(self):
        snapshot = MetricsSnapshot()
        output = format_prometheus(snapshot)
        # Should have HELP and TYPE comments
        assert "# HELP" in output
        assert "# TYPE" in output


class TestClassifyError:
    def test_timeout(self):
        assert _classify_error("Connection timeout after 30s") == "timeout"

    def test_rate_limit(self):
        assert _classify_error("429 Too Many Requests") == "rate_limit"

    def test_import_error(self):
        assert _classify_error("ImportError: no module named foo") == "import_error"

    def test_test_failure(self):
        assert _classify_error("AssertionError: expected 5") == "test_failure"

    def test_unknown(self):
        assert _classify_error("Something weird happened") == "other"
