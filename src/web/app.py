#!/usr/bin/env python3
"""SAT Web Dashboard — FastAPI app served behind Cloudflare Tunnel + Access."""

import json
import os
import time
import glob
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Environment, BaseLoader

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_DIR = Path("/home/johnlane/projects/structured-achievement-tool")
AUDIT_JOURNAL = PROJECT_DIR / ".memory" / "audit_journal.jsonl"
SAT_TASKS_DIR = Path("/home/johnlane/GoogleDrive/DriveSyncFiles/sat-tasks")
CF_ACCESS_TEAM = "sat-info"  # Cloudflare Access team/app domain
GRAFANA_URL = "http://localhost:3000"  # placeholder — redirect target for /metrics

# JWT validation imports (optional — degrade gracefully if keys unavailable)
try:
    from jose import jwt as jose_jwt, JWTError
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False

START_TIME = time.time()

app = FastAPI(title="SAT Dashboard", docs_url=None, redoc_url=None)

# ---------------------------------------------------------------------------
# Cloudflare Access JWT middleware
# ---------------------------------------------------------------------------
# Cloudflare Access sends a JWT in the Cf-Access-Jwt-Assertion header.
# We validate it to ensure requests come through Access, not direct.
# If python-jose is not installed or keys can't be fetched, we log a warning
# but still allow requests (the tunnel itself is protected by Access).

CF_CERTS_URL = f"https://{CF_ACCESS_TEAM}.cloudflareaccess.com/cdn-cgi/access/certs"
_cf_public_keys: Optional[dict] = None


def _get_cf_public_keys():
    """Fetch Cloudflare Access public keys (cached in memory)."""
    global _cf_public_keys
    if _cf_public_keys is not None:
        return _cf_public_keys
    try:
        import urllib.request
        resp = urllib.request.urlopen(CF_CERTS_URL, timeout=5)
        _cf_public_keys = json.loads(resp.read())
        return _cf_public_keys
    except Exception:
        return None


def verify_cf_jwt(token: str) -> bool:
    """Verify a Cloudflare Access JWT. Returns True if valid."""
    if not JOSE_AVAILABLE:
        return True  # can't verify without jose
    keys = _get_cf_public_keys()
    if not keys:
        return True  # can't verify without keys — trust the tunnel
    try:
        jose_jwt.decode(
            token,
            keys,
            algorithms=["RS256"],
            audience=[f"https://{CF_ACCESS_TEAM}.cloudflareaccess.com"],
        )
        return True
    except (JWTError, Exception):
        return False


@app.middleware("http")
async def cf_access_middleware(request: Request, call_next):
    """Verify Cloudflare Access JWT on every request."""
    token = request.headers.get("Cf-Access-Jwt-Assertion")
    if token:
        if not verify_cf_jwt(token):
            return JSONResponse({"error": "Invalid Cloudflare Access token"}, status_code=403)
    # If no token present, we still serve — the tunnel + Access policy is the gate.
    # For local dev / health checks this is convenient.
    return await call_next(request)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_audit_journal(limit: int = 100) -> list[dict]:
    """Read the most recent entries from the audit journal."""
    entries = []
    if not AUDIT_JOURNAL.exists():
        return entries
    try:
        with open(AUDIT_JOURNAL, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass
    return entries[-limit:]


def get_task_files() -> list[dict]:
    """Scan sat-tasks directories for task files and their status."""
    tasks = []
    if not SAT_TASKS_DIR.exists():
        return tasks
    for md_file in sorted(SAT_TASKS_DIR.rglob("*.md")):
        if md_file.name == "CLAUDE.md":
            continue
        try:
            content = md_file.read_text(errors="replace")[:4000]
        except Exception:
            continue
        # Detect state tag
        state = "unknown"
        for tag in ["<Finished>", "<Working>", "<Pending>", "<Failed>", "<Cancel>"]:
            if tag in content:
                state = tag.strip("<>")
                break
        # Check for commented-out pending (safety hold)
        if state == "unknown" and "# <Pending>" in content:
            state = "held"
        # Check for approval markers
        has_approval = bool(re.search(r"<Approval\s", content, re.IGNORECASE))
        rel_path = md_file.relative_to(SAT_TASKS_DIR)
        tasks.append({
            "file": str(rel_path),
            "name": md_file.stem,
            "state": state,
            "has_approval": has_approval,
            "mtime": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(timespec="seconds"),
            "abs_path": str(md_file),
        })
    return tasks


def get_pending_approvals() -> list[dict]:
    """Find tasks with pending approval workflow items."""
    approvals = []
    if not SAT_TASKS_DIR.exists():
        return approvals
    for md_file in SAT_TASKS_DIR.rglob("*.md"):
        if md_file.name == "CLAUDE.md":
            continue
        try:
            content = md_file.read_text(errors="replace")
        except Exception:
            continue
        # Look for approval blocks: <Approval id="xxx" status="pending">
        for match in re.finditer(
            r'<Approval\s+id="([^"]+)"\s+status="pending"[^>]*>(.*?)</Approval>',
            content, re.DOTALL | re.IGNORECASE
        ):
            approval_id = match.group(1)
            body = match.group(2).strip()
            rel_path = md_file.relative_to(SAT_TASKS_DIR)
            approvals.append({
                "id": approval_id,
                "file": str(rel_path),
                "body": body[:500],
                "abs_path": str(md_file),
            })
    return approvals


def uptime_str() -> str:
    """Human-readable uptime."""
    secs = int(time.time() - START_TIME)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m {secs % 60}s"
    hours = secs // 3600
    mins = (secs % 3600) // 60
    return f"{hours}h {mins}m"


# ---------------------------------------------------------------------------
# Jinja2 inline templates
# ---------------------------------------------------------------------------

jinja_env = Environment(loader=BaseLoader(), autoescape=True)

DASHBOARD_TEMPLATE = jinja_env.from_string(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAT Dashboard</title>
<style>
  :root { --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3;
          --muted: #8b949e; --green: #3fb950; --red: #f85149; --yellow: #d29922;
          --blue: #58a6ff; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont,
         "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.5; padding: 1.5rem; }
  h1 { font-size: 1.4rem; margin-bottom: 1rem; }
  h2 { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; color: var(--blue); }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
          padding: 1rem; }
  .card .label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; }
  .card .value { font-size: 1.6rem; font-weight: 600; margin-top: 0.25rem; }
  .green { color: var(--green); } .red { color: var(--red); } .yellow { color: var(--yellow); }
  table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
  th, td { text-align: left; padding: 0.4rem 0.75rem; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
  th { color: var(--muted); font-weight: 500; }
  .tag { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.75rem;
         font-weight: 600; }
  .tag-Finished { background: #1a3a2a; color: var(--green); }
  .tag-Working  { background: #2a2a1a; color: var(--yellow); }
  .tag-Pending  { background: #1a2a3a; color: var(--blue); }
  .tag-Failed   { background: #3a1a1a; color: var(--red); }
  .tag-Cancel   { background: #2a2a2a; color: var(--muted); }
  .tag-held     { background: #2a2a2a; color: var(--muted); }
  .tag-unknown  { background: #1a1a2a; color: var(--muted); }
  nav { margin-bottom: 1.5rem; }
  nav a { color: var(--blue); text-decoration: none; margin-right: 1.5rem; font-size: 0.9rem; }
  nav a:hover { text-decoration: underline; }
  .footer { margin-top: 2rem; color: var(--muted); font-size: 0.75rem; }
</style>
</head>
<body>
<h1>SAT Dashboard</h1>
<nav>
  <a href="/">Dashboard</a>
  <a href="/tasks">Tasks</a>
  <a href="/approvals">Approvals</a>
  <a href="/status">Status (JSON)</a>
  <a href="/metrics">Metrics</a>
</nav>

<div class="cards">
  <div class="card">
    <div class="label">Uptime</div>
    <div class="value">{{ uptime }}</div>
  </div>
  <div class="card">
    <div class="label">Stories Succeeded</div>
    <div class="value green">{{ succeeded }}</div>
  </div>
  <div class="card">
    <div class="label">Stories Failed</div>
    <div class="value red">{{ failed }}</div>
  </div>
  <div class="card">
    <div class="label">Queue Depth</div>
    <div class="value yellow">{{ queue_depth }}</div>
  </div>
  <div class="card">
    <div class="label">Total Tasks</div>
    <div class="value">{{ total_tasks }}</div>
  </div>
  <div class="card">
    <div class="label">Pending Approvals</div>
    <div class="value">{{ approval_count }}</div>
  </div>
</div>

<h2>Recent Audit Entries</h2>
{% if journal_entries %}
<table>
  <tr><th>Time</th><th>Task</th><th>Story</th><th>Result</th><th>Duration</th></tr>
  {% for e in journal_entries %}
  <tr>
    <td>{{ e.timestamp }}</td>
    <td title="{{ e.task_file }}">{{ e.task_file | replace('/home/johnlane/GoogleDrive/DriveSyncFiles/sat-tasks/', '') }}</td>
    <td>{{ e.story_id }}</td>
    <td><span class="tag {{ 'tag-Finished' if e.success else 'tag-Failed' }}">{{ 'OK' if e.success else 'FAIL' }}</span></td>
    <td>{{ '%.1f' | format(e.duration_seconds) }}s</td>
  </tr>
  {% endfor %}
</table>
{% else %}
<p style="color:var(--muted); margin-top:0.5rem;">No audit entries yet.</p>
{% endif %}

<h2>Task Overview</h2>
{% if tasks %}
<table>
  <tr><th>File</th><th>State</th><th>Modified</th></tr>
  {% for t in tasks %}
  <tr>
    <td>{{ t.file }}</td>
    <td><span class="tag tag-{{ t.state }}">{{ t.state }}</span></td>
    <td>{{ t.mtime }}</td>
  </tr>
  {% endfor %}
</table>
{% else %}
<p style="color:var(--muted); margin-top:0.5rem;">No tasks found.</p>
{% endif %}

<div class="footer">SAT Web &mdash; served via Cloudflare Tunnel</div>
</body>
</html>""")

TASKS_TEMPLATE = jinja_env.from_string(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAT Tasks</title>
<style>
  :root { --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3;
          --muted: #8b949e; --green: #3fb950; --red: #f85149; --yellow: #d29922;
          --blue: #58a6ff; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont,
         "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.5; padding: 1.5rem; }
  h1 { font-size: 1.4rem; margin-bottom: 1rem; }
  nav { margin-bottom: 1.5rem; }
  nav a { color: var(--blue); text-decoration: none; margin-right: 1.5rem; font-size: 0.9rem; }
  nav a:hover { text-decoration: underline; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 0.4rem 0.75rem; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
  th { color: var(--muted); font-weight: 500; }
  .tag { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
  .tag-Finished { background: #1a3a2a; color: var(--green); }
  .tag-Working  { background: #2a2a1a; color: var(--yellow); }
  .tag-Pending  { background: #1a2a3a; color: var(--blue); }
  .tag-Failed   { background: #3a1a1a; color: var(--red); }
  .tag-Cancel   { background: #2a2a2a; color: var(--muted); }
  .tag-held     { background: #2a2a2a; color: var(--muted); }
  .tag-unknown  { background: #1a1a2a; color: var(--muted); }
</style>
</head>
<body>
<h1>SAT Tasks</h1>
<nav>
  <a href="/">Dashboard</a>
  <a href="/tasks">Tasks</a>
  <a href="/approvals">Approvals</a>
  <a href="/status">Status (JSON)</a>
  <a href="/metrics">Metrics</a>
</nav>
{% if tasks %}
<table>
  <tr><th>File</th><th>State</th><th>Approval</th><th>Modified</th></tr>
  {% for t in tasks %}
  <tr>
    <td>{{ t.file }}</td>
    <td><span class="tag tag-{{ t.state }}">{{ t.state }}</span></td>
    <td>{{ 'yes' if t.has_approval else '' }}</td>
    <td>{{ t.mtime }}</td>
  </tr>
  {% endfor %}
</table>
{% else %}
<p style="color:var(--muted);">No tasks found.</p>
{% endif %}
</body>
</html>""")

APPROVALS_TEMPLATE = jinja_env.from_string(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAT Approvals</title>
<style>
  :root { --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3;
          --muted: #8b949e; --green: #3fb950; --red: #f85149; --blue: #58a6ff; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont,
         "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.5; padding: 1.5rem; }
  h1 { font-size: 1.4rem; margin-bottom: 1rem; }
  nav { margin-bottom: 1.5rem; }
  nav a { color: var(--blue); text-decoration: none; margin-right: 1.5rem; font-size: 0.9rem; }
  nav a:hover { text-decoration: underline; }
  .approval { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
              padding: 1rem; margin-bottom: 1rem; }
  .approval h3 { font-size: 0.95rem; margin-bottom: 0.5rem; }
  .approval .meta { color: var(--muted); font-size: 0.8rem; margin-bottom: 0.5rem; }
  .approval pre { background: var(--bg); padding: 0.75rem; border-radius: 4px; font-size: 0.8rem;
                  white-space: pre-wrap; margin-bottom: 0.75rem; overflow-x: auto; }
  .btn { display: inline-block; padding: 0.35rem 1rem; border: none; border-radius: 4px;
         font-size: 0.85rem; cursor: pointer; margin-right: 0.5rem; font-weight: 600; }
  .btn-approve { background: var(--green); color: #000; }
  .btn-reject  { background: var(--red); color: #fff; }
</style>
<script>
async function respond(id, action) {
  const res = await fetch(`/approvals/${id}/respond`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: action})
  });
  if (res.ok) { location.reload(); }
  else { alert('Error: ' + (await res.text())); }
}
</script>
</head>
<body>
<h1>Pending Approvals</h1>
<nav>
  <a href="/">Dashboard</a>
  <a href="/tasks">Tasks</a>
  <a href="/approvals">Approvals</a>
  <a href="/status">Status (JSON)</a>
  <a href="/metrics">Metrics</a>
</nav>
{% if approvals %}
{% for a in approvals %}
<div class="approval">
  <h3>{{ a.id }}</h3>
  <div class="meta">File: {{ a.file }}</div>
  <pre>{{ a.body }}</pre>
  <button class="btn btn-approve" onclick="respond('{{ a.id }}', 'approve')">Approve</button>
  <button class="btn btn-reject" onclick="respond('{{ a.id }}', 'reject')">Reject</button>
</div>
{% endfor %}
{% else %}
<p style="color:var(--muted);">No pending approvals.</p>
{% endif %}
</body>
</html>""")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    journal = read_audit_journal(50)
    tasks = get_task_files()
    approvals = get_pending_approvals()
    succeeded = sum(1 for e in journal if e.get("success"))
    failed = sum(1 for e in journal if not e.get("success"))
    queue_depth = sum(1 for t in tasks if t["state"] in ("Pending", "Working"))
    return DASHBOARD_TEMPLATE.render(
        uptime=uptime_str(),
        succeeded=succeeded,
        failed=failed,
        queue_depth=queue_depth,
        total_tasks=len(tasks),
        approval_count=len(approvals),
        journal_entries=list(reversed(journal[-20:])),
        tasks=tasks,
    )


@app.get("/status")
async def status():
    journal = read_audit_journal()
    tasks = get_task_files()
    succeeded = sum(1 for e in journal if e.get("success"))
    failed = sum(1 for e in journal if not e.get("success"))
    queue_depth = sum(1 for t in tasks if t["state"] in ("Pending", "Working"))
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START_TIME),
        "uptime": uptime_str(),
        "stories_succeeded": succeeded,
        "stories_failed": failed,
        "queue_depth": queue_depth,
        "total_tasks": len(tasks),
        "pending_approvals": len(get_pending_approvals()),
    }


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page():
    tasks = get_task_files()
    return TASKS_TEMPLATE.render(tasks=tasks)


@app.get("/approvals", response_class=HTMLResponse)
async def approvals_page():
    approvals = get_pending_approvals()
    return APPROVALS_TEMPLATE.render(approvals=approvals)


@app.post("/approvals/{approval_id}/respond")
async def approval_respond(approval_id: str, request: Request):
    """Handle approval/rejection of a pending approval item."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    action = body.get("action", "").lower()
    if action not in ("approve", "reject"):
        raise HTTPException(400, "action must be 'approve' or 'reject'")

    # Find the approval in task files
    approvals = get_pending_approvals()
    target = None
    for a in approvals:
        if a["id"] == approval_id:
            target = a
            break
    if not target:
        raise HTTPException(404, f"Approval '{approval_id}' not found or already resolved")

    # Update the file: change status="pending" to status="approved" or status="rejected"
    file_path = Path(target["abs_path"])
    try:
        content = file_path.read_text()
        new_status = "approved" if action == "approve" else "rejected"
        updated = re.sub(
            rf'(<Approval\s+id="{re.escape(approval_id)}"\s+status=")pending(")',
            rf'\g<1>{new_status}\2',
            content,
        )
        if updated == content:
            raise HTTPException(500, "Failed to update approval status in file")
        file_path.write_text(updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"File update error: {e}")

    return {"ok": True, "approval_id": approval_id, "action": action}


@app.get("/metrics")
async def metrics():
    return RedirectResponse(GRAFANA_URL)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
