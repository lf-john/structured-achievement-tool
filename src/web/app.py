#!/usr/bin/env python3
"""SAT Web Dashboard — FastAPI app served behind Cloudflare Tunnel + Access."""

import json
import os
import time
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from html import escape as html_escape

import httpx
import markdown

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Environment, BaseLoader
from markupsafe import Markup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
from src.core.paths import SAT_PROJECT_DIR, SAT_TASKS_DIR as _SAT_TASKS_DIR, AUDIT_JOURNAL as _AUDIT_JOURNAL
PROJECT_DIR = SAT_PROJECT_DIR
AUDIT_JOURNAL = _AUDIT_JOURNAL
SAT_TASKS_DIR = _SAT_TASKS_DIR
CF_ACCESS_TEAM = "sat-info"  # Cloudflare Access team/app domain
GRAFANA_URL = "http://crm3.logicalfront.com:3001/d/sat-overview/sat-overview"
PROMETHEUS_URL = "http://localhost:9101/metrics"

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
        return True
    keys = _get_cf_public_keys()
    if not keys:
        return True
    try:
        jose_jwt.decode(
            token,
            keys,
            algorithms=["RS256"],
            audience=[f"https://{CF_ACCESS_TEAM}.cloudflareaccess.com"],
        )
        return True
    except Exception:
        return False


@app.middleware("http")
async def cf_access_middleware(request: Request, call_next):
    """Verify Cloudflare Access JWT on every request."""
    token = request.headers.get("Cf-Access-Jwt-Assertion")
    if token:
        if not verify_cf_jwt(token):
            return JSONResponse({"error": "Invalid Cloudflare Access token"}, status_code=403)
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
            stat = md_file.stat()
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
        # Extract directory (category)
        parts = rel_path.parts
        category = parts[0] if len(parts) > 1 else "root"
        tasks.append({
            "file": str(rel_path),
            "name": md_file.stem,
            "state": state,
            "has_approval": has_approval,
            "category": category,
            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "mtime_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "size": stat.st_size,
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


def parse_prometheus_metrics(text: str) -> dict:
    """Parse Prometheus text format into a dict of metric_name -> value."""
    metrics = {}
    for line in text.strip().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        # e.g.: sat_stories_total{status="succeeded"} 7
        # or: sat_system_healthy 1
        match = re.match(r'^(\S+?)(?:\{([^}]*)\})?\s+(.+)$', line)
        if match:
            name = match.group(1)
            labels = match.group(2) or ""
            value = match.group(3)
            key = f"{name}{{{labels}}}" if labels else name
            try:
                metrics[key] = float(value)
            except ValueError:
                metrics[key] = value
    return metrics


async def fetch_prometheus_metrics() -> dict:
    """Fetch and parse Prometheus metrics from the SAT exporter."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(PROMETHEUS_URL)
            if resp.status_code == 200:
                return parse_prometheus_metrics(resp.text)
    except Exception:
        pass
    return {}


def get_service_status(service_name: str) -> dict:
    """Get systemd user service status."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service_name],
            capture_output=True, text=True, timeout=5
        )
        is_active = result.stdout.strip()
    except Exception:
        is_active = "unknown"

    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", service_name,
             "--property=ActiveEnterTimestamp,MainPID,MemoryCurrent"],
            capture_output=True, text=True, timeout=5
        )
        props = {}
        for line in result.stdout.strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v
    except Exception:
        props = {}

    return {
        "name": service_name,
        "active": is_active,
        "pid": props.get("MainPID", "?"),
        "since": props.get("ActiveEnterTimestamp", "?"),
        "memory": _format_bytes(props.get("MemoryCurrent", "")),
    }


def _format_bytes(val: str) -> str:
    """Format byte count to human-readable."""
    try:
        n = int(val)
        if n >= 1024 * 1024 * 1024:
            return f"{n / (1024**3):.1f} GB"
        if n >= 1024 * 1024:
            return f"{n / (1024**2):.1f} MB"
        if n >= 1024:
            return f"{n / 1024:.1f} KB"
        return f"{n} B"
    except (ValueError, TypeError):
        return "?"


def uptime_str() -> str:
    """Human-readable uptime."""
    secs = int(time.time() - START_TIME)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m {secs % 60}s"
    hours = secs // 3600
    mins = (secs % 3600) // 60
    if hours >= 24:
        days = hours // 24
        hours = hours % 24
        return f"{days}d {hours}h {mins}m"
    return f"{hours}h {mins}m"


def _format_duration(secs: float) -> str:
    """Format seconds to human-readable duration."""
    if secs == 0:
        return "< 1s"
    if secs < 60:
        return f"{secs:.1f}s"
    mins = int(secs) // 60
    s = int(secs) % 60
    return f"{mins}m {s}s"


# ---------------------------------------------------------------------------
# Shared CSS
# ---------------------------------------------------------------------------

COMMON_CSS = """
  :root {
    --bg: #0d1117; --surface: #161b22; --surface2: #1c2128; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --green: #3fb950; --red: #f85149;
    --yellow: #d29922; --blue: #58a6ff; --purple: #bc8cff; --orange: #f0883e;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    line-height: 1.6; padding: 0;
  }
  .container { max-width: 1200px; margin: 0 auto; padding: 1.5rem 2rem; }
  a { color: var(--blue); text-decoration: none; }
  a:hover { text-decoration: underline; }

  /* Header */
  .header {
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 0.75rem 2rem; display: flex; align-items: center; gap: 2rem;
  }
  .header .logo { font-size: 1.1rem; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
  .header .logo span { color: var(--blue); }
  .header nav { display: flex; gap: 1.5rem; }
  .header nav a {
    color: var(--muted); font-size: 0.85rem; font-weight: 500;
    padding: 0.25rem 0; border-bottom: 2px solid transparent; transition: all 0.15s;
  }
  .header nav a:hover, .header nav a.active {
    color: var(--text); text-decoration: none; border-bottom-color: var(--blue);
  }

  /* Page title */
  h1 { font-size: 1.3rem; margin-bottom: 1.25rem; font-weight: 600; }
  h2 { font-size: 1.05rem; margin: 1.75rem 0 0.75rem; color: var(--blue); font-weight: 600; }

  /* Cards grid */
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 0.75rem; }
  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 1rem 1.25rem;
  }
  .card .label { color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 1.5rem; font-weight: 700; margin-top: 0.2rem; font-variant-numeric: tabular-nums; }
  .card .sub { color: var(--muted); font-size: 0.72rem; margin-top: 0.15rem; }

  /* Tables */
  table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
  th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); font-size: 0.82rem; }
  th { color: var(--muted); font-weight: 500; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; }
  tr:hover { background: var(--surface2); }

  /* Status tags */
  .tag {
    display: inline-block; padding: 0.12rem 0.55rem; border-radius: 12px;
    font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;
  }
  .tag-Finished { background: #1a3a2a; color: var(--green); }
  .tag-Working  { background: #2a2a1a; color: var(--yellow); }
  .tag-Pending  { background: #1a2a3a; color: var(--blue); }
  .tag-Failed   { background: #3a1a1a; color: var(--red); }
  .tag-Cancel   { background: #2a2a2a; color: var(--muted); }
  .tag-held     { background: #2a2a2a; color: var(--muted); }
  .tag-unknown  { background: #1a1a2a; color: var(--muted); }

  /* Service indicators */
  .svc-row { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0; }
  .svc-dot {
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  }
  .svc-dot.active { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .svc-dot.inactive { background: var(--red); box-shadow: 0 0 6px var(--red); }
  .svc-dot.unknown { background: var(--muted); }
  .svc-name { font-weight: 600; font-size: 0.85rem; min-width: 160px; }
  .svc-meta { color: var(--muted); font-size: 0.75rem; }

  /* Two-column layout */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  @media (max-width: 768px) { .grid-2 { grid-template-columns: 1fr; } }

  /* Section panels */
  .panel {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  .panel h3 { font-size: 0.85rem; color: var(--muted); margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }

  /* Category headers in task list */
  .cat-header {
    font-size: 0.9rem; font-weight: 600; color: var(--purple);
    margin: 1.25rem 0 0.5rem; padding-bottom: 0.25rem;
    border-bottom: 1px solid var(--border);
  }

  /* Footer */
  .footer { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.72rem; }

  /* Approval cards */
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

  /* Task content view */
  .task-content {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 1.5rem 2rem; line-height: 1.7;
  }
  .task-content h1, .task-content h2, .task-content h3, .task-content h4 {
    color: var(--text); margin: 1rem 0 0.5rem; }
  .task-content h1 { font-size: 1.3rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
  .task-content h2 { font-size: 1.1rem; color: var(--blue); }
  .task-content h3 { font-size: 0.95rem; color: var(--purple); }
  .task-content code { background: var(--bg); padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.85em; }
  .task-content pre { background: var(--bg); padding: 1rem; border-radius: 6px; overflow-x: auto; margin: 0.75rem 0; }
  .task-content pre code { background: none; padding: 0; }
  .task-content ul, .task-content ol { padding-left: 1.5rem; margin: 0.5rem 0; }
  .task-content blockquote { border-left: 3px solid var(--border); padding-left: 1rem; color: var(--muted); margin: 0.75rem 0; }
  .task-content table { margin: 0.75rem 0; }
  .task-content table th { background: var(--surface2); }
  .breadcrumb { font-size: 0.82rem; color: var(--muted); margin-bottom: 1rem; }
  .breadcrumb a { color: var(--blue); }
  .file-meta { font-size: 0.78rem; color: var(--muted); margin-bottom: 1.25rem; display: flex; gap: 1.5rem; }
"""


# ---------------------------------------------------------------------------
# Jinja2 templates
# ---------------------------------------------------------------------------

jinja_env = Environment(loader=BaseLoader(), autoescape=True)

def _nav(active: str) -> str:
    """Generate nav HTML with active highlighting."""
    links = [
        ("/", "Dashboard"),
        ("/tasks", "Tasks"),
        ("/approvals", "Approvals"),
        ("/status", "Status API"),
    ]
    parts = []
    for href, label in links:
        cls = ' class="active"' if href == active else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    parts.append(f'<a href="{GRAFANA_URL}" target="_blank">Grafana</a>')
    return "\n    ".join(parts)


DASHBOARD_TEMPLATE = jinja_env.from_string(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAT Dashboard</title>
<style>""" + COMMON_CSS + r"""</style>
</head>
<body>
<div class="header">
  <div class="logo"><span>SAT</span> Dashboard</div>
  <nav>""" + _nav("/") + r"""</nav>
</div>
<div class="container">

<div class="cards">
  <div class="card">
    <div class="label">System</div>
    <div class="value {{ 'green' if system_healthy else 'red' }}">{{ 'Healthy' if system_healthy else 'Degraded' }}</div>
    <div class="sub">Uptime: {{ uptime }}</div>
  </div>
  <div class="card">
    <div class="label">Stories OK</div>
    <div class="value green">{{ stories_succeeded }}</div>
  </div>
  <div class="card">
    <div class="label">Stories Failed</div>
    <div class="value {{ 'red' if stories_failed > 0 else 'muted' }}">{{ stories_failed }}</div>
  </div>
  <div class="card">
    <div class="label">Tasks Done</div>
    <div class="value green">{{ tasks_completed }}</div>
  </div>
  <div class="card">
    <div class="label">Tasks Failed</div>
    <div class="value {{ 'red' if tasks_failed > 0 else 'muted' }}">{{ tasks_failed }}</div>
  </div>
  <div class="card">
    <div class="label">Queue Depth</div>
    <div class="value {{ 'yellow' if queue_depth > 0 else 'muted' }}">{{ queue_depth }}</div>
  </div>
  <div class="card">
    <div class="label">Avg Duration</div>
    <div class="value">{{ avg_duration }}</div>
  </div>
  <div class="card">
    <div class="label">Approvals</div>
    <div class="value {{ 'orange' if approval_count > 0 else 'muted' }}">{{ approval_count }}</div>
  </div>
</div>

<div class="grid-2">
  <div>
    <h2>Services</h2>
    <div class="panel">
      {% for svc in services %}
      <div class="svc-row">
        <div class="svc-dot {{ 'active' if svc.active == 'active' else ('inactive' if svc.active in ('inactive', 'failed') else 'unknown') }}"></div>
        <div class="svc-name">{{ svc.name }}</div>
        <div class="svc-meta">PID {{ svc.pid }} &middot; {{ svc.memory }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  <div>
    <h2>Task Summary</h2>
    <div class="panel">
      <table>
        <tr><th>Status</th><th>Count</th></tr>
        {% for state, count in task_summary %}
        <tr>
          <td><span class="tag tag-{{ state }}">{{ state }}</span></td>
          <td>{{ count }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </div>
</div>

<h2>Recent Audit Journal</h2>
{% if journal_entries %}
<div class="panel" style="padding: 0; overflow-x: auto;">
<table>
  <tr><th>Time</th><th>Task</th><th>Story</th><th>Result</th><th>Duration</th><th>Error</th></tr>
  {% for e in journal_entries %}
  <tr>
    <td style="white-space:nowrap;">{{ e.get('timestamp', '?')[:19] }}</td>
    <td>{{ e.get('task_file', '?').replace(sat_tasks_prefix, '') }}</td>
    <td>{{ e.get('story_id', '?') }}</td>
    <td><span class="tag {{ 'tag-Finished' if e.get('success') else 'tag-Failed' }}">{{ 'OK' if e.get('success') else 'FAIL' }}</span></td>
    <td>{{ format_dur(e.get('duration_seconds', 0)) }}</td>
    <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis;">{{ e.get('error_summary', '') or '' }}</td>
  </tr>
  {% endfor %}
</table>
</div>
{% else %}
<div class="panel"><p style="color:var(--muted);">No audit entries yet.</p></div>
{% endif %}

<h2>Tasks at a Glance</h2>
{% if tasks %}
<div class="panel" style="padding: 0; overflow-x: auto;">
<table>
  <tr><th>File</th><th>State</th><th>Modified</th><th>Size</th></tr>
  {% for t in tasks %}
  <tr>
    <td><a href="/task/{{ t.file }}">{{ t.file }}</a></td>
    <td><span class="tag tag-{{ t.state }}">{{ t.state }}</span></td>
    <td style="white-space:nowrap;">{{ t.mtime }}</td>
    <td>{{ format_size(t.size) }}</td>
  </tr>
  {% endfor %}
</table>
</div>
{% else %}
<div class="panel"><p style="color:var(--muted);">No tasks found.</p></div>
{% endif %}

<div class="footer">SAT Web Dashboard &mdash; served via Cloudflare Tunnel &mdash; auto-refreshes data on each page load</div>
</div>
</body>
</html>""")


TASKS_TEMPLATE = jinja_env.from_string(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAT Tasks</title>
<style>""" + COMMON_CSS + r"""</style>
</head>
<body>
<div class="header">
  <div class="logo"><span>SAT</span> Dashboard</div>
  <nav>""" + _nav("/tasks") + r"""</nav>
</div>
<div class="container">
<h1>All Tasks</h1>
<div class="cards" style="margin-bottom: 1.5rem;">
  <div class="card">
    <div class="label">Total Files</div>
    <div class="value">{{ tasks | length }}</div>
  </div>
  <div class="card">
    <div class="label">Finished</div>
    <div class="value green">{{ tasks | selectattr('state', 'eq', 'Finished') | list | length }}</div>
  </div>
  <div class="card">
    <div class="label">Working</div>
    <div class="value yellow">{{ tasks | selectattr('state', 'eq', 'Working') | list | length }}</div>
  </div>
  <div class="card">
    <div class="label">Pending</div>
    <div class="value blue">{{ tasks | selectattr('state', 'eq', 'Pending') | list | length }}</div>
  </div>
  <div class="card">
    <div class="label">Failed</div>
    <div class="value red">{{ tasks | selectattr('state', 'eq', 'Failed') | list | length }}</div>
  </div>
</div>

{% for cat, cat_tasks in categories.items() %}
<div class="cat-header">{{ cat }}</div>
<div class="panel" style="padding: 0; overflow-x: auto;">
<table>
  <tr><th>File</th><th>State</th><th>Approval</th><th>Modified</th><th>Size</th></tr>
  {% for t in cat_tasks %}
  <tr>
    <td><a href="/task/{{ t.file }}">{{ t.name }}.md</a></td>
    <td><span class="tag tag-{{ t.state }}">{{ t.state }}</span></td>
    <td>{{ 'yes' if t.has_approval else '' }}</td>
    <td style="white-space:nowrap;">{{ t.mtime }}</td>
    <td>{{ format_size(t.size) }}</td>
  </tr>
  {% endfor %}
</table>
</div>
{% endfor %}

{% if not categories %}
<div class="panel"><p style="color:var(--muted);">No tasks found.</p></div>
{% endif %}

<div class="footer">SAT Web Dashboard</div>
</div>
</body>
</html>""")


TASK_VIEW_TEMPLATE = jinja_env.from_string(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ file_path }} - SAT</title>
<style>""" + COMMON_CSS + r"""</style>
</head>
<body>
<div class="header">
  <div class="logo"><span>SAT</span> Dashboard</div>
  <nav>""" + _nav("") + r"""</nav>
</div>
<div class="container">
<div class="breadcrumb"><a href="/">Dashboard</a> / <a href="/tasks">Tasks</a> / {{ file_path }}</div>
<h1>{{ file_name }}</h1>
<div class="file-meta">
  <span>Status: <span class="tag tag-{{ state }}">{{ state }}</span></span>
  <span>Modified: {{ mtime }}</span>
  <span>Size: {{ size }}</span>
</div>
<div class="task-content">{{ rendered_html }}</div>
<div class="footer">SAT Web Dashboard</div>
</div>
</body>
</html>""")


APPROVALS_TEMPLATE = jinja_env.from_string(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAT Approvals</title>
<style>""" + COMMON_CSS + r"""</style>
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
<div class="header">
  <div class="logo"><span>SAT</span> Dashboard</div>
  <nav>""" + _nav("/approvals") + r"""</nav>
</div>
<div class="container">
<h1>Pending Approvals</h1>
{% if approvals %}
{% for a in approvals %}
<div class="approval">
  <h3>{{ a.id }}</h3>
  <div class="meta">File: <a href="/task/{{ a.file }}">{{ a.file }}</a></div>
  <pre>{{ a.body }}</pre>
  <button class="btn btn-approve" onclick="respond('{{ a.id }}', 'approve')">Approve</button>
  <button class="btn btn-reject" onclick="respond('{{ a.id }}', 'reject')">Reject</button>
</div>
{% endfor %}
{% else %}
<div class="panel"><p style="color:var(--muted);">No pending approvals.</p></div>
{% endif %}
<div class="footer">SAT Web Dashboard</div>
</div>
</body>
</html>""")


# ---------------------------------------------------------------------------
# Template helpers (registered as globals)
# ---------------------------------------------------------------------------

def _format_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024**2):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"

jinja_env.globals['format_dur'] = _format_duration
jinja_env.globals['format_size'] = _format_size


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    journal = read_audit_journal(50)
    tasks = get_task_files()
    approvals = get_pending_approvals()
    prom = await fetch_prometheus_metrics()

    # Pull Prometheus metrics for supplementary data (avg duration, system health)
    system_healthy = bool(prom.get('sat_system_healthy', 1))
    avg_dur_secs = prom.get('sat_stories_avg_duration_seconds', 0)

    # Headline cards: use task file scan (accurate) instead of audit journal counters
    task_state_counts = {}
    for t in tasks:
        task_state_counts[t["state"]] = task_state_counts.get(t["state"], 0) + 1
    tasks_completed = task_state_counts.get("Finished", 0)
    tasks_failed_count = task_state_counts.get("Failed", 0)
    tasks_working = task_state_counts.get("Working", 0)
    tasks_pending = task_state_counts.get("Pending", 0)
    queue_depth = tasks_pending + tasks_working

    # Stories from Prometheus (still useful), with journal fallback
    stories_succeeded = int(prom.get('sat_stories_total{status="succeeded"}', 0))
    stories_failed = int(prom.get('sat_stories_total{status="failed"}', 0))
    if not prom:
        stories_succeeded = sum(1 for e in journal if e.get("success"))
        stories_failed = sum(1 for e in journal if not e.get("success"))

    # Service statuses
    services = [
        get_service_status("sat.service"),
        get_service_status("sat-monitor.service"),
        get_service_status("sat-web.service"),
    ]

    # Task summary by state
    state_counts = {}
    for t in tasks:
        state_counts[t["state"]] = state_counts.get(t["state"], 0) + 1
    # Order: Finished, Working, Pending, Failed, held, unknown, Cancel
    order = ["Finished", "Working", "Pending", "Failed", "held", "unknown", "Cancel"]
    task_summary = [(s, state_counts[s]) for s in order if s in state_counts]

    return DASHBOARD_TEMPLATE.render(
        uptime=uptime_str(),
        system_healthy=system_healthy,
        stories_succeeded=stories_succeeded,
        stories_failed=stories_failed,
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed_count,
        queue_depth=queue_depth,
        avg_duration=_format_duration(avg_dur_secs),
        approval_count=len(approvals),
        services=services,
        task_summary=task_summary,
        journal_entries=list(reversed(journal[-20:])),
        tasks=tasks,
        sat_tasks_prefix=str(SAT_TASKS_DIR) + "/",
    )


@app.get("/status")
async def status():
    journal = read_audit_journal()
    tasks = get_task_files()
    prom = await fetch_prometheus_metrics()
    approvals = get_pending_approvals()

    services = [
        get_service_status("sat.service"),
        get_service_status("sat-monitor.service"),
        get_service_status("sat-web.service"),
    ]

    # Task file scan counts (accurate, ground-truth)
    task_state_counts = {}
    for t in tasks:
        task_state_counts[t["state"]] = task_state_counts.get(t["state"], 0) + 1

    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START_TIME),
        "uptime": uptime_str(),
        "stories_succeeded": int(prom.get('sat_stories_total{status="succeeded"}', 0)),
        "stories_failed": int(prom.get('sat_stories_total{status="failed"}', 0)),
        "tasks_completed": task_state_counts.get("Finished", 0),
        "tasks_failed": task_state_counts.get("Failed", 0),
        "tasks_working": task_state_counts.get("Working", 0),
        "tasks_pending": task_state_counts.get("Pending", 0),
        "queue_depth": task_state_counts.get("Pending", 0) + task_state_counts.get("Working", 0),
        "system_healthy": bool(prom.get('sat_system_healthy', 1)),
        "total_task_files": len(tasks),
        "task_state_counts": task_state_counts,
        "pending_approvals": len(approvals),
        "services": {s["name"]: s["active"] for s in services},
        "prometheus_metrics": prom if prom else "unavailable",
    }


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page():
    tasks = get_task_files()
    # Group by category
    categories = {}
    for t in tasks:
        cat = t["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(t)
    return TASKS_TEMPLATE.render(tasks=tasks, categories=categories)


@app.get("/task/{file_path:path}", response_class=HTMLResponse)
async def task_view(file_path: str):
    """View an individual task file rendered as HTML."""
    # Sanitize: only allow paths within SAT_TASKS_DIR
    full_path = SAT_TASKS_DIR / file_path
    try:
        full_path = full_path.resolve()
        # Security: ensure it's within SAT_TASKS_DIR
        if not str(full_path).startswith(str(SAT_TASKS_DIR.resolve())):
            raise HTTPException(403, "Access denied")
    except Exception:
        raise HTTPException(403, "Invalid path")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(404, f"Task file not found: {file_path}")

    try:
        raw_content = full_path.read_text(errors="replace")
    except Exception as e:
        raise HTTPException(500, f"Cannot read file: {e}")

    # Parse state
    state = "unknown"
    for tag in ["<Finished>", "<Working>", "<Pending>", "<Failed>", "<Cancel>"]:
        if tag in raw_content:
            state = tag.strip("<>")
            break
    if state == "unknown" and "# <Pending>" in raw_content:
        state = "held"

    stat = full_path.stat()

    # Render markdown to HTML
    rendered = markdown.markdown(
        raw_content,
        extensions=["tables", "fenced_code", "codehilite", "toc", "nl2br"],
    )

    return TASK_VIEW_TEMPLATE.render(
        file_path=file_path,
        file_name=full_path.name,
        state=state,
        mtime=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        size=_format_size(stat.st_size),
        rendered_html=Markup(rendered),
    )


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

    approvals = get_pending_approvals()
    target = None
    for a in approvals:
        if a["id"] == approval_id:
            target = a
            break
    if not target:
        raise HTTPException(404, f"Approval '{approval_id}' not found or already resolved")

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
