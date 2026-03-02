#!/usr/bin/env python3
"""SAT Daily Digest — Sends a summary of the last 24 hours via ntfy.

Scheduled via cron at 8am Mountain (14:00 UTC):
    0 14 * * * cd ~/projects/structured-achievement-tool && venv/bin/python scripts/daily_digest.py
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_DIR / ".memory"
SAT_DB = MEMORY_DIR / "sat.db"
LLM_COSTS_DB = MEMORY_DIR / "llm_costs.db"
AUDIT_JOURNAL = MEMORY_DIR / "audit_journal.jsonl"
ENV_FILE = Path.home() / ".config" / "sat" / "env"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env(env_path: Path) -> None:
    """Read a systemd-style env file (KEY=VALUE) and inject into os.environ."""
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def cutoff_iso() -> str:
    """Return the ISO-8601 timestamp for 24 hours ago (UTC, no tz suffix)."""
    return (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")


def query_sat_db(cutoff: str) -> dict:
    """Query sat.db for task/story/event activity in the last 24 hours."""
    result = {
        "tasks_created": 0,
        "tasks_completed": 0,
        "stories_total": 0,
        "stories_passed": 0,
        "stories_failed": 0,
        "events_total": 0,
    }
    if not SAT_DB.exists():
        return result
    try:
        conn = sqlite3.connect(str(SAT_DB))
        conn.row_factory = sqlite3.Row

        # Tasks created in window
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE created_at >= ?", (cutoff,)
        ).fetchone()
        result["tasks_created"] = row["n"] if row else 0

        # Tasks moved to a completed-like status in window
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE updated_at >= ? AND status IN ('completed','done','finished')",
            (cutoff,),
        ).fetchone()
        result["tasks_completed"] = row["n"] if row else 0

        # Stories updated in window
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM stories WHERE updated_at >= ?", (cutoff,)
        ).fetchone()
        result["stories_total"] = row["n"] if row else 0

        row = conn.execute(
            "SELECT COUNT(*) AS n FROM stories WHERE updated_at >= ? AND status IN ('passed','done','completed','green')",
            (cutoff,),
        ).fetchone()
        result["stories_passed"] = row["n"] if row else 0

        row = conn.execute(
            "SELECT COUNT(*) AS n FROM stories WHERE updated_at >= ? AND status IN ('failed','error','red')",
            (cutoff,),
        ).fetchone()
        result["stories_failed"] = row["n"] if row else 0

        # Events logged in window
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE timestamp >= ?", (cutoff,)
        ).fetchone()
        result["events_total"] = row["n"] if row else 0

        conn.close()
    except Exception as exc:
        print(f"[digest] sat.db query error: {exc}", file=sys.stderr)
    return result


def query_llm_costs(cutoff: str) -> dict:
    """Query llm_costs.db for token usage and cost in the last 24 hours."""
    result = {
        "total_cost": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "calls": 0,
        "models": [],
    }
    if not LLM_COSTS_DB.exists():
        return result
    try:
        conn = sqlite3.connect(str(LLM_COSTS_DB))
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(estimated_cost), 0) AS cost, "
            "COALESCE(SUM(prompt_tokens), 0) AS pt, "
            "COALESCE(SUM(completion_tokens), 0) AS ct "
            "FROM llm_costs WHERE timestamp >= ?",
            (cutoff,),
        ).fetchone()
        if row:
            result["calls"] = row["n"]
            result["total_cost"] = round(row["cost"], 4)
            result["prompt_tokens"] = row["pt"]
            result["completion_tokens"] = row["ct"]

        models = conn.execute(
            "SELECT DISTINCT model_name FROM llm_costs WHERE timestamp >= ?",
            (cutoff,),
        ).fetchall()
        result["models"] = [r["model_name"] for r in models]

        conn.close()
    except Exception as exc:
        print(f"[digest] llm_costs.db query error: {exc}", file=sys.stderr)
    return result


def read_audit_journal(cutoff: str) -> dict:
    """Read audit_journal.jsonl and count events in the last 24 hours."""
    result = {"total": 0, "success": 0, "failure": 0, "task_files": set()}
    if not AUDIT_JOURNAL.exists():
        return result
    try:
        for line in AUDIT_JOURNAL.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = entry.get("timestamp", "")
            if ts >= cutoff:
                result["total"] += 1
                if entry.get("success"):
                    result["success"] += 1
                else:
                    result["failure"] += 1
                tf = entry.get("task_file", "")
                if tf:
                    result["task_files"].add(Path(tf).name)
    except Exception as exc:
        print(f"[digest] audit_journal read error: {exc}", file=sys.stderr)
    return result


def format_digest(sat: dict, costs: dict, audit: dict) -> str:
    """Build a human-readable digest message."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_activity = sat["events_total"] + audit["total"] + costs["calls"]

    if total_activity == 0:
        return f"SAT Daily Digest ({now})\n\nNo activity in the last 24 hours."

    lines = [f"SAT Daily Digest ({now})", ""]

    # Tasks
    lines.append("Tasks")
    lines.append(f"  Created:   {sat['tasks_created']}")
    lines.append(f"  Completed: {sat['tasks_completed']}")
    lines.append("")

    # Stories
    lines.append("Stories")
    lines.append(f"  Active:  {sat['stories_total']}")
    lines.append(f"  Passed:  {sat['stories_passed']}")
    lines.append(f"  Failed:  {sat['stories_failed']}")
    lines.append("")

    # Audit journal
    lines.append("Audit Journal")
    lines.append(f"  Entries:   {audit['total']}")
    lines.append(f"  Success:   {audit['success']}")
    lines.append(f"  Failure:   {audit['failure']}")
    if audit["task_files"]:
        lines.append(f"  Files:     {', '.join(sorted(audit['task_files']))}")
    lines.append("")

    # LLM Costs
    lines.append("LLM Usage")
    lines.append(f"  Calls:       {costs['calls']}")
    lines.append(f"  Prompt tok:  {costs['prompt_tokens']:,}")
    lines.append(f"  Compl tok:   {costs['completion_tokens']:,}")
    lines.append(f"  Est. cost:   ${costs['total_cost']:.4f}")
    if costs["models"]:
        lines.append(f"  Models:      {', '.join(costs['models'])}")

    return "\n".join(lines)


def send_ntfy(title: str, message: str, priority: str = "default") -> None:
    """Send a notification via ntfy. Silently ignores errors."""
    topic = os.environ.get("NTFY_TOPIC", "")
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
    if not topic:
        print("[digest] NTFY_TOPIC not set — skipping notification", file=sys.stderr)
        return
    try:
        import requests

        url = f"{server.rstrip('/')}/{topic}"
        resp = requests.post(
            url,
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": "clipboard",
            },
            timeout=15,
        )
        resp.raise_for_status()
        print(f"[digest] Sent to {url} (HTTP {resp.status_code})")
    except Exception as exc:
        print(f"[digest] ntfy send error: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_env(ENV_FILE)

    cutoff = cutoff_iso()
    print(f"[digest] Cutoff: {cutoff} UTC")

    sat = query_sat_db(cutoff)
    costs = query_llm_costs(cutoff)
    audit = read_audit_journal(cutoff)

    message = format_digest(sat, costs, audit)
    print(message)

    send_ntfy("SAT Daily Digest", message, priority="default")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[digest] Fatal error: {exc}", file=sys.stderr)
    sys.exit(0)
