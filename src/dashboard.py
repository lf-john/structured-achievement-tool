"""SAT Web Dashboard — Real-time task monitoring via browser.

Provides:
- JSON API endpoints for task/story status, events, audit data
- Single-page HTML dashboard with auto-refresh
- System health overview

Run: python -m src.dashboard (default port 8765)
Or via systemd: sat-dashboard.service
"""

import argparse
import logging
import os

from flask import Flask, jsonify, render_template_string

from src.db.database_manager import DatabaseManager
from src.execution.audit_journal import AuditJournal
from src.visibility import TaskVisibility

logger = logging.getLogger(__name__)

app = Flask(__name__)

_db: DatabaseManager | None = None
_vis: TaskVisibility | None = None
_audit: AuditJournal | None = None


def _get_db() -> DatabaseManager:
    global _db
    if _db is None:
        _db = DatabaseManager()
    return _db


def _get_vis() -> TaskVisibility:
    global _vis
    if _vis is None:
        _vis = TaskVisibility(_get_db())
    return _vis


def _get_audit() -> AuditJournal:
    global _audit
    if _audit is None:
        _audit = AuditJournal(
            os.path.expanduser(
                "~/projects/structured-achievement-tool/.memory/audit_journal.jsonl"
            )
        )
    return _audit


DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAT Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #c9d1d9; line-height: 1.5; padding: 20px; }
  h1 { color: #58a6ff; margin-bottom: 20px; }
  h2 { color: #8b949e; margin: 20px 0 10px; font-size: 1.1em; text-transform: uppercase; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card .label { color: #8b949e; font-size: 0.85em; }
  .card .value { font-size: 1.8em; font-weight: 600; color: #58a6ff; }
  .card.success .value { color: #3fb950; }
  .card.warning .value { color: #d29922; }
  .card.danger .value { color: #f85149; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #21262d; }
  th { color: #8b949e; font-weight: 600; font-size: 0.85em; text-transform: uppercase; }
  td { font-size: 0.9em; }
  .status { padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: 600; }
  .status-complete { background: #1b4332; color: #3fb950; }
  .status-working { background: #1a2332; color: #58a6ff; }
  .status-failed { background: #3d1a1a; color: #f85149; }
  .status-pending { background: #2d2a1a; color: #d29922; }
  .status-blocked { background: #2d1a2d; color: #bc8cff; }
  .event { font-size: 0.85em; padding: 6px 0; border-bottom: 1px solid #21262d; }
  .event .ts { color: #484f58; margin-right: 8px; }
  .event .type { color: #58a6ff; font-weight: 600; margin-right: 8px; }
  .refresh { color: #484f58; font-size: 0.8em; float: right; }
  #error { color: #f85149; padding: 10px; display: none; }
</style>
</head>
<body>
<h1>SAT Dashboard <span class="refresh" id="refresh">Auto-refresh: 10s</span></h1>
<div id="error"></div>

<h2>System Status</h2>
<div class="grid" id="status-grid"></div>

<h2>Audit Summary</h2>
<div class="grid" id="audit-grid"></div>

<h2>Active Stories</h2>
<table id="stories-table">
<thead><tr><th>Story</th><th>Type</th><th>Status</th><th>Phase</th><th>Attempts</th></tr></thead>
<tbody></tbody>
</table>

<h2>Recent Events</h2>
<div id="events-list"></div>

<script>
async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

function statusClass(s) {
  return 'status-' + (s || 'pending');
}

async function refresh() {
  try {
    document.getElementById('error').style.display = 'none';

    // Status
    const status = await fetchJSON('/api/status');
    document.getElementById('status-grid').innerHTML = `
      <div class="card"><div class="label">Active Tasks</div><div class="value">${status.active_tasks || 0}</div></div>
      <div class="card"><div class="label">Working Stories</div><div class="value">${status.working_stories || 0}</div></div>
      <div class="card success"><div class="label">Complete Stories</div><div class="value">${status.complete_stories || 0}</div></div>
      <div class="card ${(status.failed_stories || 0) > 0 ? 'danger' : ''}"><div class="label">Failed Stories</div><div class="value">${status.failed_stories || 0}</div></div>
    `;

    // Audit
    const audit = await fetchJSON('/api/audit/summary');
    const rate = audit.success_rate ? audit.success_rate.toFixed(1) : '0.0';
    const avgDur = audit.average_duration_seconds ? audit.average_duration_seconds.toFixed(0) : '0';
    document.getElementById('audit-grid').innerHTML = `
      <div class="card"><div class="label">Total Executions</div><div class="value">${audit.total_count || 0}</div></div>
      <div class="card success"><div class="label">Success Rate</div><div class="value">${rate}%</div></div>
      <div class="card"><div class="label">Avg Duration</div><div class="value">${avgDur}s</div></div>
      <div class="card danger"><div class="label">Failures</div><div class="value">${audit.failed_count || 0}</div></div>
    `;

    // Active work
    const active = await fetchJSON('/api/active');
    const tbody = document.querySelector('#stories-table tbody');
    let rows = '';
    for (const item of (active.active_tasks || [])) {
      for (const s of (item.stories || [])) {
        rows += `<tr>
          <td>${s.title || s.id || '?'}</td>
          <td>${s.type || '?'}</td>
          <td><span class="status ${statusClass(s.status)}">${s.status || '?'}</span></td>
          <td>${s.phase || '-'}</td>
          <td>${s.attempt_count || 0}</td>
        </tr>`;
      }
    }
    tbody.innerHTML = rows || '<tr><td colspan="5" style="color:#484f58">No active stories</td></tr>';

    // Events
    const events = await fetchJSON('/api/events');
    const evList = document.getElementById('events-list');
    let evHTML = '';
    for (const e of (events || []).slice(0, 25)) {
      const ts = (e.timestamp || '').slice(11, 19);
      const detail = (e.detail || '').slice(0, 100);
      evHTML += `<div class="event"><span class="ts">${ts}</span><span class="type">${e.event_type || '?'}</span>${detail}</div>`;
    }
    evList.innerHTML = evHTML || '<div class="event" style="color:#484f58">No recent events</div>';

  } catch (err) {
    const el = document.getElementById('error');
    el.textContent = 'Error: ' + err.message;
    el.style.display = 'block';
  }
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""


@app.route("/api/status")
def api_status():
    return jsonify(_get_db().get_system_status())


@app.route("/api/active")
def api_active():
    return jsonify(_get_vis().get_active_work())


@app.route("/api/tasks")
def api_tasks():
    return jsonify(_get_db().get_active_tasks())


@app.route("/api/task/<task_id>")
def api_task(task_id):
    return jsonify(_get_vis().get_task_status(task_id))


@app.route("/api/task/<task_id>/stories")
def api_task_stories(task_id):
    return jsonify(_get_db().get_stories_for_task(task_id))


@app.route("/api/events")
def api_events():
    return jsonify(_get_db().get_recent_events())


@app.route("/api/events/<task_id>")
def api_task_events(task_id):
    return jsonify(_get_db().get_recent_events(task_id=task_id))


@app.route("/api/blocked")
def api_blocked():
    return jsonify(_get_vis().get_blocked_stories())


@app.route("/api/audit/summary")
def api_audit_summary():
    audit = _get_audit()
    return jsonify(audit.summary)


@app.route("/api/daily-summary")
def api_daily_summary():
    vis = _get_vis()
    return jsonify(summary=vis.generate_daily_summary())


@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


def main():
    parser = argparse.ArgumentParser(description="SAT Dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"SAT Dashboard starting on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
