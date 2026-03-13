"""SAT Web Dashboard — Real-time task monitoring via browser.

Provides:
- JSON API endpoints for task/story status, events, audit data
- Approval web forms for human tasks (replaces signal files)
- Single-page HTML dashboard with auto-refresh
- System health overview

Run: python -m src.dashboard (default port 8765)
Or via systemd: sat-dashboard.service
"""

import argparse
import logging
import os

from flask import Flask, jsonify, render_template_string, request

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
        _audit = AuditJournal(os.path.expanduser("~/projects/structured-achievement-tool/.memory/audit_journal.jsonl"))
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
  .nav { margin-bottom: 20px; }
  .nav a { color: #58a6ff; margin-right: 20px; text-decoration: none; }
  .nav a:hover { text-decoration: underline; }
</style>
</head>
<body>
<h1>SAT Dashboard <span class="refresh" id="refresh">Auto-refresh: 10s</span></h1>
<div class="nav"><a href="/">Dashboard</a><a href="/approvals">Pending Approvals</a></div>
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

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
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
      <div class="card ${(status.pending_approvals || 0) > 0 ? 'warning' : ''}"><div class="label">Pending Approvals</div><div class="value">${status.pending_approvals || 0}</div></div>
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
          <td>${escapeHtml(s.title || s.id || '?')}</td>
          <td>${escapeHtml(s.type || '?')}</td>
          <td><span class="status ${statusClass(s.status)}">${escapeHtml(s.status || '?')}</span></td>
          <td>${escapeHtml(s.phase || '-')}</td>
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
      evHTML += `<div class="event"><span class="ts">${escapeHtml(ts)}</span><span class="type">${escapeHtml(e.event_type || '?')}</span>${escapeHtml(detail)}</div>`;
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


APPROVALS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAT Approvals</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #c9d1d9; line-height: 1.5; padding: 20px; }
  h1 { color: #58a6ff; margin-bottom: 20px; }
  h2 { color: #8b949e; margin: 20px 0 10px; font-size: 1.1em; text-transform: uppercase; }
  .nav { margin-bottom: 20px; }
  .nav a { color: #58a6ff; margin-right: 20px; text-decoration: none; }
  .nav a:hover { text-decoration: underline; }
  .approval-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                   padding: 20px; margin-bottom: 20px; }
  .approval-card h3 { color: #58a6ff; margin-bottom: 8px; }
  .approval-card .meta { color: #8b949e; font-size: 0.85em; margin-bottom: 12px; }
  .approval-card .instructions { background: #0d1117; border: 1px solid #21262d;
                                  border-radius: 6px; padding: 16px; margin: 12px 0;
                                  white-space: pre-wrap; font-size: 0.9em; max-height: 400px;
                                  overflow-y: auto; }
  .form-group { margin: 12px 0; }
  .form-group label { display: block; color: #8b949e; font-size: 0.85em;
                      margin-bottom: 4px; font-weight: 600; }
  .form-group input, .form-group textarea, .form-group select {
    width: 100%; padding: 8px 12px; background: #0d1117; border: 1px solid #30363d;
    border-radius: 6px; color: #c9d1d9; font-family: inherit; font-size: 0.9em; }
  .form-group textarea { min-height: 80px; resize: vertical; }
  .form-group input[type="checkbox"] { width: auto; margin-right: 8px; }
  .btn-group { display: flex; gap: 10px; margin-top: 16px; }
  .btn { padding: 8px 20px; border: none; border-radius: 6px; cursor: pointer;
         font-size: 0.9em; font-weight: 600; }
  .btn-approve { background: #238636; color: #fff; }
  .btn-approve:hover { background: #2ea043; }
  .btn-reject { background: #da3633; color: #fff; }
  .btn-reject:hover { background: #f85149; }
  .btn-complete { background: #1f6feb; color: #fff; }
  .btn-complete:hover { background: #388bfd; }
  .btn-accept { background: #238636; color: #fff; }
  .btn-accept:hover { background: #2ea043; }
  .btn-decline { background: #da3633; color: #fff; }
  .btn-decline:hover { background: #f85149; }
  .empty { color: #484f58; padding: 40px; text-align: center; font-size: 1.1em; }
  .success-msg { color: #3fb950; padding: 12px; background: #1b4332;
                 border-radius: 6px; margin: 12px 0; display: none; }
  .error-msg { color: #f85149; padding: 12px; background: #3d1a1a;
               border-radius: 6px; margin: 12px 0; display: none; }
  .refresh-info { color: #484f58; font-size: 0.8em; float: right; }
</style>
</head>
<body>
<h1>SAT Approvals <span class="refresh-info">Auto-refresh: 15s</span></h1>
<div class="nav"><a href="/">Dashboard</a><a href="/approvals">Pending Approvals</a></div>

<div id="approvals-container"></div>

<script>
async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function renderFormField(field) {
  const name = field.name || '';
  const label = field.label || name;
  const type = field.type || 'text';
  const required = field.required ? 'required' : '';
  const options = field.options || [];

  if (type === 'checkbox') {
    return `<div class="form-group">
      <label><input type="checkbox" name="${escapeHtml(name)}" ${required}> ${escapeHtml(label)}</label>
    </div>`;
  }
  if (type === 'textarea') {
    return `<div class="form-group">
      <label>${escapeHtml(label)}</label>
      <textarea name="${escapeHtml(name)}" ${required}></textarea>
    </div>`;
  }
  if (type === 'select') {
    const opts = options.map(o => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join('');
    return `<div class="form-group">
      <label>${escapeHtml(label)}</label>
      <select name="${escapeHtml(name)}" ${required}>${opts}</select>
    </div>`;
  }
  return `<div class="form-group">
    <label>${escapeHtml(label)}</label>
    <input type="${escapeHtml(type)}" name="${escapeHtml(name)}" ${required}>
  </div>`;
}

function renderButtons(approvalType, approvalId) {
  const safeId = escapeHtml(approvalId);
  if (approvalType === 'human_action') {
    return `<div class="btn-group">
      <button class="btn btn-complete" onclick="submitApproval('${safeId}', 'completed')">Mark Complete</button>
    </div>`;
  }
  if (approvalType === 'plan_review') {
    return `<div class="btn-group">
      <button class="btn btn-approve" onclick="submitApproval('${safeId}', 'approved')">Approve</button>
      <button class="btn btn-reject" onclick="submitApproval('${safeId}', 'rejected')">Reject</button>
    </div>`;
  }
  if (approvalType === 'assignment') {
    return `<div class="btn-group">
      <button class="btn btn-accept" onclick="submitApproval('${safeId}', 'approved')">Accept</button>
      <button class="btn btn-decline" onclick="submitApproval('${safeId}', 'rejected')">Decline</button>
    </div>`;
  }
  return `<div class="btn-group">
    <button class="btn btn-approve" onclick="submitApproval('${safeId}', 'approved')">Approve</button>
    <button class="btn btn-reject" onclick="submitApproval('${safeId}', 'rejected')">Reject</button>
  </div>`;
}

function renderApproval(a) {
  const fields = (a.form_fields || []).map(renderFormField).join('');
  const typeLabel = (a.approval_type || 'unknown').replace('_', ' ');
  const created = (a.created_at || '').replace('T', ' ').slice(0, 19);

  return `<div class="approval-card" id="card-${a.id}">
    <h3>${escapeHtml(a.title || 'Untitled Approval')}</h3>
    <div class="meta">
      Type: ${escapeHtml(typeLabel)} |
      Story: ${escapeHtml(a.story_id || '?')} |
      Task: ${escapeHtml(a.task_id || '?')} |
      Created: ${created}
    </div>
    ${a.instructions ? `<div class="instructions">${escapeHtml(a.instructions)}</div>` : ''}
    <form id="form-${a.id}" onsubmit="return false;">
      ${fields}
    </form>
    <div class="success-msg" id="success-${a.id}"></div>
    <div class="error-msg" id="error-${a.id}"></div>
    ${renderButtons(a.approval_type, a.id)}
  </div>`;
}

async function submitApproval(approvalId, status) {
  const form = document.getElementById('form-' + approvalId);
  const formData = {};

  if (form) {
    const inputs = form.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
      if (input.type === 'checkbox') {
        formData[input.name] = input.checked;
      } else {
        formData[input.name] = input.value;
      }
    });
  }

  const successEl = document.getElementById('success-' + approvalId);
  const errorEl = document.getElementById('error-' + approvalId);
  successEl.style.display = 'none';
  errorEl.style.display = 'none';

  try {
    const res = await fetch('/api/approvals/' + approvalId + '/respond', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: status, response_data: formData})
    });
    const result = await res.json();

    if (res.ok) {
      successEl.textContent = 'Response submitted: ' + status;
      successEl.style.display = 'block';
      // Remove card after brief delay
      setTimeout(() => {
        const card = document.getElementById('card-' + approvalId);
        if (card) card.style.opacity = '0.5';
      }, 1000);
      // Refresh after a moment
      setTimeout(loadApprovals, 2000);
    } else {
      errorEl.textContent = 'Error: ' + (result.error || 'Unknown error');
      errorEl.style.display = 'block';
    }
  } catch (err) {
    errorEl.textContent = 'Request failed: ' + err.message;
    errorEl.style.display = 'block';
  }
}

async function loadApprovals() {
  const container = document.getElementById('approvals-container');
  try {
    const approvals = await fetchJSON('/api/approvals');
    if (!approvals.length) {
      container.innerHTML = '<div class="empty">No pending approvals. All clear.</div>';
      return;
    }
    container.innerHTML = approvals.map(renderApproval).join('');
  } catch (err) {
    container.innerHTML = `<div class="error-msg" style="display:block">Failed to load approvals: ${escapeHtml(err.message)}</div>`;
  }
}

loadApprovals();
setInterval(loadApprovals, 15000);
</script>
</body>
</html>
"""


# --- Existing Dashboard Routes ---


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


# --- Approval API Routes ---


@app.route("/api/approvals")
def api_approvals():
    """List all pending approvals."""
    return jsonify(_get_db().get_pending_approvals())


@app.route("/api/approvals/<approval_id>")
def api_approval_detail(approval_id):
    """Get details for a single approval including form fields."""
    approval = _get_db().get_approval(approval_id)
    if approval is None:
        return jsonify({"error": "Approval not found"}), 404
    return jsonify(approval)


@app.route("/api/approvals/<approval_id>/respond", methods=["POST"])
def api_approval_respond(approval_id):
    """Submit a response (approve/reject/complete) for an approval.

    Expects JSON body: {"status": "approved|rejected|completed", "response_data": {...}}
    """
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    response_data = data.get("response_data", {})

    if not new_status:
        return jsonify({"error": "Missing 'status' field"}), 400

    valid_statuses = ("approved", "rejected", "completed")
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status '{new_status}'. Must be one of: {', '.join(valid_statuses)}"}), 400

    db = _get_db()
    success = db.respond_to_approval(approval_id, new_status, response_data)
    if not success:
        return jsonify({"error": "Approval not found or already resolved"}), 404

    logger.info(f"Approval {approval_id} responded: {new_status}")
    return jsonify({"ok": True, "approval_id": approval_id, "status": new_status})


# --- HTML Routes ---


@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/approvals")
def approvals_page():
    """HTML page listing pending approvals with interactive forms."""
    return render_template_string(APPROVALS_HTML)


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
