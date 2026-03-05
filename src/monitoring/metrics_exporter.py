"""
Metrics Exporter — Export SAT metrics in Prometheus format for Grafana.

Reads from the audit journal and system state to produce metrics that
Prometheus can scrape. Exposes an HTTP endpoint on a configurable port.

Metrics exported:
- sat_stories_total (counter, labels: status)
- sat_stories_duration_seconds (histogram)
- sat_tasks_total (counter, labels: status)
- sat_failure_types (counter, labels: failure_type)
- sat_system_healthy (gauge)
- sat_queue_depth (gauge)
"""

import logging
import os
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from src.execution.audit_journal import AuditJournal

logger = logging.getLogger(__name__)


@dataclass
class MetricsSnapshot:
    """A point-in-time snapshot of all SAT metrics."""
    stories_succeeded: int = 0
    stories_failed: int = 0
    stories_total: int = 0
    avg_duration_seconds: float = 0.0
    failure_type_counts: dict[str, int] = field(default_factory=dict)
    tasks_completed: int = 0
    tasks_failed: int = 0
    queue_depth: int = 0
    system_healthy: bool = True
    uptime_seconds: float = 0.0


def collect_metrics(
    audit_journal: AuditJournal,
    queue_dir: str | None = None,
    start_time: float | None = None,
) -> MetricsSnapshot:
    """Collect current metrics from audit journal and system state.

    Args:
        audit_journal: The audit journal to read from.
        queue_dir: Optional directory to count pending tasks.
        start_time: Process start time for uptime calculation.

    Returns:
        MetricsSnapshot with current values.
    """
    records = audit_journal.query()
    snapshot = MetricsSnapshot()

    if records:
        snapshot.stories_total = len(records)
        snapshot.stories_succeeded = sum(1 for r in records if r.success)
        snapshot.stories_failed = sum(1 for r in records if not r.success)

        durations = [r.duration_seconds for r in records if r.duration_seconds > 0]
        if durations:
            snapshot.avg_duration_seconds = sum(durations) / len(durations)

        # Count failure types from error summaries
        for r in records:
            if not r.success and r.error_summary:
                # Simple classification by first word of error
                error_type = _classify_error(r.error_summary)
                snapshot.failure_type_counts[error_type] = (
                    snapshot.failure_type_counts.get(error_type, 0) + 1
                )

        # Count unique tasks
        task_files = set()
        for r in records:
            task_files.add(r.task_file)
        for tf in task_files:
            task_records = [r for r in records if r.task_file == tf]
            if all(r.success for r in task_records):
                snapshot.tasks_completed += 1
            elif any(not r.success for r in task_records):
                snapshot.tasks_failed += 1

    # Count pending tasks in queue
    if queue_dir and os.path.exists(queue_dir):
        try:
            for item in os.listdir(queue_dir):
                item_path = os.path.join(queue_dir, item)
                if os.path.isdir(item_path) and not item.startswith('_'):
                    for f in os.listdir(item_path):
                        if f.endswith('.md') and not f.startswith('_'):
                            filepath = os.path.join(item_path, f)
                            try:
                                with open(filepath) as fh:
                                    content = fh.read(500)
                                if '<Pending>' in content and '# <Pending>' not in content:
                                    snapshot.queue_depth += 1
                            except (OSError, UnicodeDecodeError):
                                pass
        except OSError:
            pass

    if start_time:
        snapshot.uptime_seconds = time.time() - start_time

    return snapshot


def _classify_error(error_summary: str) -> str:
    """Classify an error summary into a type for metrics."""
    lower = error_summary.lower()
    if "timeout" in lower:
        return "timeout"
    if "rate" in lower or "429" in lower:
        return "rate_limit"
    if "import" in lower or "module" in lower:
        return "import_error"
    if "assert" in lower or "test" in lower:
        return "test_failure"
    if "permission" in lower:
        return "permission_error"
    if "syntax" in lower:
        return "syntax_error"
    return "other"


def format_prometheus(snapshot: MetricsSnapshot) -> str:
    """Format a MetricsSnapshot as Prometheus exposition text.

    Returns a string suitable for serving via HTTP.
    """
    lines = []

    # Stories counter
    lines.append("# HELP sat_stories_total Total number of stories processed")
    lines.append("# TYPE sat_stories_total counter")
    lines.append(f'sat_stories_total{{status="succeeded"}} {snapshot.stories_succeeded}')
    lines.append(f'sat_stories_total{{status="failed"}} {snapshot.stories_failed}')

    # Duration
    lines.append("# HELP sat_stories_avg_duration_seconds Average story execution duration")
    lines.append("# TYPE sat_stories_avg_duration_seconds gauge")
    lines.append(f"sat_stories_avg_duration_seconds {snapshot.avg_duration_seconds:.2f}")

    # Tasks
    lines.append("# HELP sat_tasks_total Total tasks processed")
    lines.append("# TYPE sat_tasks_total counter")
    lines.append(f'sat_tasks_total{{status="completed"}} {snapshot.tasks_completed}')
    lines.append(f'sat_tasks_total{{status="failed"}} {snapshot.tasks_failed}')

    # Failure types
    lines.append("# HELP sat_failure_types Failure counts by type")
    lines.append("# TYPE sat_failure_types counter")
    for ftype, count in sorted(snapshot.failure_type_counts.items()):
        lines.append(f'sat_failure_types{{type="{ftype}"}} {count}')

    # Queue
    lines.append("# HELP sat_queue_depth Number of pending tasks in queue")
    lines.append("# TYPE sat_queue_depth gauge")
    lines.append(f"sat_queue_depth {snapshot.queue_depth}")

    # System health
    lines.append("# HELP sat_system_healthy Whether the system is healthy (1=yes, 0=no)")
    lines.append("# TYPE sat_system_healthy gauge")
    lines.append(f"sat_system_healthy {1 if snapshot.system_healthy else 0}")

    # Uptime
    lines.append("# HELP sat_uptime_seconds Process uptime in seconds")
    lines.append("# TYPE sat_uptime_seconds gauge")
    lines.append(f"sat_uptime_seconds {snapshot.uptime_seconds:.0f}")

    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves Prometheus metrics."""

    audit_journal = None
    queue_dir = None
    start_time = None

    def do_GET(self):
        if self.path == "/metrics":
            try:
                snapshot = collect_metrics(
                    self.audit_journal,
                    self.queue_dir,
                    self.start_time,
                )
                body = format_prometheus(snapshot)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.end_headers()
                self.wfile.write(body.encode())
            except BrokenPipeError:
                # Client disconnected; this is normal
                pass
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def start_metrics_server(
    audit_journal: AuditJournal,
    port: int = 9101,
    queue_dir: str | None = None,
) -> HTTPServer:
    """Start the metrics HTTP server in a background thread.

    Args:
        audit_journal: Audit journal to read metrics from.
        port: HTTP port to serve on.
        queue_dir: Directory to scan for pending tasks.

    Returns:
        The HTTPServer instance (for later shutdown).
    """
    MetricsHandler.audit_journal = audit_journal
    MetricsHandler.queue_dir = queue_dir
    MetricsHandler.start_time = time.time()

    server = HTTPServer(("", port), MetricsHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Metrics server started on port {port}")
    return server
