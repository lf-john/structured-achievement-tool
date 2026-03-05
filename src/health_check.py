#!/usr/bin/env python3
"""SAT Health Check Script - Run via cron to monitor system health.

Checks:
1. SAT daemon is running
2. SAT monitor is running
3. Ollama is healthy
4. No tasks stuck in <Working> or <Failed>
5. Google Drive mount is accessible
6. Dashboard is responding

Outputs a status report and takes corrective action where possible.
Sends ntfy notification on failures.
"""

import json
import os
import subprocess
import sys
import time

import requests

# Ensure the project root is in sys.path so 'from src.*' imports work when
# invoked from cron (which does not set PYTHONPATH).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Cron doesn't have the user D-Bus session. Set the env vars so systemctl --user works.
UID = os.getuid()
os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{UID}")
os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{UID}/bus")

try:
    from src.core.paths import FUSE_SENTINEL, PROACTIVE_STATE, SAT_DB, SAT_PROJECT_DIR, SAT_TASKS_DIR
except ImportError:
    from pathlib import Path
    SAT_PROJECT_DIR = Path(_PROJECT_ROOT)
    SAT_TASKS_DIR = Path(os.path.expanduser("~/GoogleDrive/DriveSyncFiles/sat-tasks"))
    FUSE_SENTINEL = SAT_TASKS_DIR / "CLAUDE.md"
    PROACTIVE_STATE = SAT_PROJECT_DIR / ".memory" / "proactive_state.json"
    SAT_DB = SAT_PROJECT_DIR / ".memory" / "sat.db"

WATCH_DIRS = [str(SAT_TASKS_DIR)]
# Read from env (set in ~/.config/sat/env, loaded by systemd)
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
NTFY_MIN_PRIORITY = os.environ.get("SAT_NTFY_MIN_PRIORITY", "default")
PRIORITY_LEVELS = {"min": 0, "low": 1, "default": 2, "high": 3, "urgent": 4}
PROJECT_PATH = str(SAT_PROJECT_DIR)

def notify(title, message, priority="default", tags=""):
    if not NTFY_TOPIC:
        return
    # Respect minimum priority filter
    msg_level = PRIORITY_LEVELS.get(priority, 2)
    min_level = PRIORITY_LEVELS.get(NTFY_MIN_PRIORITY, 2)
    if msg_level < min_level:
        return
    try:
        headers = {"Title": title}
        if priority != "default":
            headers["Priority"] = priority
        if tags:
            headers["Tags"] = tags
        requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=5
        )
    except:
        pass

def check_service(name):
    """Check if a systemd user service is active."""
    try:
        res = subprocess.run(
            ["systemctl", "--user", "is-active", name],
            capture_output=True, text=True
        )
        return res.stdout.strip() == "active"
    except:
        return False

def restart_service(name):
    """Restart a systemd user service."""
    try:
        subprocess.run(["systemctl", "--user", "restart", name], check=True)
        time.sleep(3)
        return check_service(name)
    except:
        return False

def check_ollama():
    """Check if Ollama is responding."""
    try:
        res = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10
        )
        return res.returncode == 0
    except:
        return False

def check_gdrive():
    """Check if Google Drive mount is accessible.

    Verifies a known file exists (not just the directory) to detect stale
    FUSE mounts where the mountpoint directory exists but reads hang or
    return empty results.
    """
    sentinel = str(FUSE_SENTINEL)
    try:
        return os.path.isfile(sentinel) and os.path.getsize(sentinel) > 0
    except OSError:
        return False

def check_dashboard():
    """Check if the SAT dashboard is responding."""
    try:
        res = requests.get("http://localhost:8765/status", timeout=5)
        return res.status_code == 200
    except:
        return False


def maintain_checkpoint_db():
    """Expire old checkpoint entries (>24h) and VACUUM the DB (Failure State 8).

    The checkpoint DB stores LangGraph workflow state for resume capability.
    Old entries serve no purpose and grow the DB file over time.
    """
    import sqlite3

    db_path = os.path.join(PROJECT_PATH, ".memory", "checkpoints.db")
    if not os.path.isfile(db_path):
        return

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()

        # List tables so we can handle any schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        # Delete rows older than 24 hours from any table with a timestamp column.
        # Only prune completed/failed entries — preserve in_progress and waiting_for_human.
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            has_status = "status" in columns
            for ts_col in ("created_at", "timestamp", "updated_at"):
                if ts_col in columns:
                    try:
                        if has_status:
                            cursor.execute(
                                f"DELETE FROM {table} WHERE {ts_col} < datetime('now', '-24 hours') "
                                f"AND status IN ('completed', 'failed')"
                            )
                        else:
                            cursor.execute(
                                f"DELETE FROM {table} WHERE {ts_col} < datetime('now', '-24 hours')"
                            )
                        deleted = cursor.rowcount
                        if deleted:
                            print(f"  Checkpoint DB: pruned {deleted} rows from {table}")
                    except sqlite3.OperationalError:
                        pass
                    break

        conn.commit()

        # VACUUM to reclaim disk space (only if DB > 1MB to avoid unnecessary I/O)
        db_size = os.path.getsize(db_path)
        if db_size > 1024 * 1024:
            cursor.execute("VACUUM")
            new_size = os.path.getsize(db_path)
            print(f"  Checkpoint DB: VACUUM {db_size // 1024}KB -> {new_size // 1024}KB")

        conn.close()
    except Exception as e:
        print(f"  Checkpoint DB maintenance failed: {e}")

def cleanup_orphan_worktrees():
    """Remove git worktrees that are older than 24 hours (Failure State 12).

    SAT creates worktrees under PROJECT_PATH/worktrees/ for isolated task
    execution.  If a task crashes without cleanup, the worktree is left behind.
    This function prunes worktrees whose last modification was >24h ago.
    """
    worktree_dir = os.path.join(PROJECT_PATH, "worktrees")
    if not os.path.isdir(worktree_dir):
        return

    cutoff = time.time() - 86400  # 24 hours

    try:
        for name in os.listdir(worktree_dir):
            wt_path = os.path.join(worktree_dir, name)
            if not os.path.isdir(wt_path):
                continue
            mtime = os.path.getmtime(wt_path)
            if mtime < cutoff:
                try:
                    result = subprocess.run(
                        ["git", "worktree", "remove", wt_path, "--force"],
                        cwd=PROJECT_PATH,
                        capture_output=True, text=True, timeout=15,
                    )
                    if result.returncode == 0:
                        print(f"  Cleaned orphan worktree: {name}")
                    else:
                        # Fallback: remove directory manually
                        import shutil
                        shutil.rmtree(wt_path, ignore_errors=True)
                        print(f"  Removed orphan worktree dir: {name}")
                except Exception as e:
                    print(f"  Failed to clean worktree {name}: {e}")
    except Exception as e:
        print(f"  Worktree cleanup error: {e}")


def scan_tasks():
    """Scan task directories for status.

    Handles the sat-tasks subdirectory structure:
    sat-tasks/
      dynamond/
        001.md
      another-task/
        001.md
    """
    status = {"finished": 0, "working": 0, "failed": 0, "queued": 0, "waiting": 0}
    issues = []

    for watch_dir in WATCH_DIRS:
        if not os.path.exists(watch_dir):
            continue
        for task_dir_name in sorted(os.listdir(watch_dir)):
            task_dir = os.path.join(watch_dir, task_dir_name)
            if not os.path.isdir(task_dir) or task_dir_name.startswith('_') or task_dir_name.startswith('tmp'):
                continue
            for f in sorted(os.listdir(task_dir)):
                if not f.endswith('.md') or f.startswith('_') or '_response' in f:
                    continue
                path = os.path.join(task_dir, f)
                try:
                    with open(path) as file:
                        content = file.read()
                    if '<!-- CLAUDE-RESPONSE -->' in content[:200]:
                        continue
                    if "<Finished>" in content:
                        status["finished"] += 1
                    elif "<Working>" in content:
                        status["working"] += 1
                        # Only flag as issue if stuck (not modified in 30+ min)
                        mtime = os.path.getmtime(path)
                        age_min = (time.time() - mtime) / 60
                        if age_min > 30:
                            issues.append(f"STUCK: {task_dir_name}/{f} ({int(age_min)}m)")
                    elif "<Failed>" in content:
                        status["failed"] += 1
                        issues.append(f"FAILED: {task_dir_name}/{f}")
                    elif "<Pending>" in content and "# <Pending>" not in content:
                        status["queued"] += 1
                    elif "# <Pending>" in content:
                        status["waiting"] += 1
                except:
                    pass

    return status, issues

def main():
    problems = []
    actions = []

    # 1. Check SAT daemon
    if not check_service("sat.service"):
        problems.append("SAT daemon is down")
        if restart_service("sat.service"):
            actions.append("Restarted SAT daemon successfully")
        else:
            actions.append("FAILED to restart SAT daemon")

    # 2. Check SAT monitor
    if not check_service("sat-monitor.service"):
        problems.append("SAT monitor is down")
        if restart_service("sat-monitor.service"):
            actions.append("Restarted SAT monitor successfully")
        else:
            actions.append("FAILED to restart SAT monitor")

    # 3. Check Ollama
    if not check_ollama():
        problems.append("Ollama is not responding")
        try:
            subprocess.run(["sudo", "systemctl", "restart", "ollama"], check=True, timeout=15)
            time.sleep(5)
            if check_ollama():
                actions.append("Restarted Ollama successfully")
            else:
                actions.append("FAILED to restart Ollama")
        except:
            actions.append("Could not restart Ollama")

    # 4. Check Google Drive
    if not check_gdrive():
        problems.append("Google Drive mount not accessible")
        try:
            subprocess.run(["systemctl", "--user", "restart", "rclone-gdrive.service"], check=True, timeout=15)
            time.sleep(5)
            if check_gdrive():
                actions.append("Restarted rclone-gdrive successfully")
            else:
                actions.append("FAILED to remount Google Drive")
        except:
            actions.append("Could not restart rclone-gdrive")

    # 5. Check Dashboard
    if not check_dashboard():
        problems.append("SAT Dashboard not responding")

    # 5b. Checkpoint DB maintenance (Failure State 8)
    maintain_checkpoint_db()

    # 5c. Git worktree cleanup (Failure State 12)
    cleanup_orphan_worktrees()

    # 6. Scan tasks
    task_status, task_issues = scan_tasks()

    # Build report
    report = "SAT Health Check Report\n"
    report += f"{'='*40}\n"
    report += f"Services: sat={'OK' if check_service('sat.service') else 'DOWN'}, "
    report += f"monitor={'OK' if check_service('sat-monitor.service') else 'DOWN'}, "
    report += f"ollama={'OK' if check_ollama() else 'DOWN'}\n"
    report += f"GDrive: {'OK' if check_gdrive() else 'DOWN'}\n"
    report += f"Tasks: {task_status['finished']} done, {task_status['working']} active, "
    report += f"{task_status['failed']} failed, {task_status['queued']} queued, {task_status['waiting']} waiting\n"

    if problems:
        report += "\nProblems:\n"
        for p in problems:
            report += f"  - {p}\n"

    if actions:
        report += "\nActions taken:\n"
        for a in actions:
            report += f"  - {a}\n"

    if task_issues:
        report += "\nTask issues:\n"
        for i in task_issues:
            report += f"  - {i}\n"

    print(report)

    # Send notification if there are problems
    if problems or task_issues:
        notify(
            "SAT Health Alert",
            report,
            priority="high",
            tags="warning,robot"
        )
    else:
        # Periodic success notification (only if run with --verbose)
        if "--verbose" in sys.argv:
            notify(
                "SAT Health OK",
                report,
                tags="white_check_mark"
            )

    # Create debug stories for persistent problems that couldn't be auto-fixed
    unfixed = [a for a in actions if "FAILED" in a]
    if unfixed:
        for action in unfixed:
            _create_debug_story_with_deps(
                f"Debug: {action}",
                (
                    f"The health check detected a problem and attempted auto-recovery "
                    f"but **failed**.\n\n"
                    f"**Problem:** {action}\n\n"
                    f"**Full report:**\n```\n{report}\n```\n\n"
                    f"Investigate the root cause and implement a permanent fix."
                ),
            )
        notify(
            "SAT: Debug Task Created",
            f"Created {len(unfixed)} debug tasks for unresolvable issues.",
            priority="high",
            tags="warning,wrench",
        )

    return 0 if not problems else 1

## --- Proactive Agency ---

PROACTIVE_STATE_FILE = str(PROACTIVE_STATE)

def _load_proactive_state():
    """Load last-run timestamps for proactive checks."""
    if os.path.exists(PROACTIVE_STATE_FILE):
        try:
            with open(PROACTIVE_STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def _save_proactive_state(state):
    os.makedirs(os.path.dirname(PROACTIVE_STATE_FILE), exist_ok=True)
    with open(PROACTIVE_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def _hours_since(timestamp_str):
    """Return hours since a timestamp string, or float('inf') if missing."""
    if not timestamp_str:
        return float("inf")
    try:
        import datetime
        last = datetime.datetime.fromisoformat(timestamp_str)
        now = datetime.datetime.now()
        return (now - last).total_seconds() / 3600
    except (ValueError, TypeError):
        return float("inf")

def _get_project_stories(project=None, db_path=None):
    """Query task_states for stories belonging to a specific project.

    Args:
        project: Project name to filter by. If None, uses 'structured-achievement-tool'.
        db_path: Path to sat.db.

    Returns:
        (in_progress_ids, queued_ids) — lists of task_path strings.
        in_progress_ids: tasks currently in 'working' state.
        queued_ids: tasks in 'pending' state (waiting to run).
    """
    import sqlite3

    if project is None:
        project = "structured-achievement-tool"
    if db_path is None:
        db_path = str(SAT_DB)
    if not os.path.isfile(db_path):
        return [], []

    in_progress = []
    queued = []
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute(
            "SELECT task_path, status FROM task_states "
            "WHERE project=? AND status IN ('working', 'pending')",
            (project,),
        ).fetchall()
        for row in rows:
            if row["status"] == "working":
                in_progress.append(row["task_path"])
            else:
                queued.append(row["task_path"])
        conn.close()
    except Exception as e:
        print(f"  Could not query project stories for {project}: {e}")
    return in_progress, queued


def _get_sat_editing_stories(db_path=None):
    """Query task_states for SAT-editing stories.

    Backwards-compatible wrapper around _get_project_stories.
    """
    return _get_project_stories(project="structured-achievement-tool", db_path=db_path)


def _create_maintenance_story(title, description, story_type="maintenance",
                              output_dir=None, priority="normal", depends_on=None):
    """Create a story file for proactive maintenance.

    Args:
        title: Story title.
        description: Story body (markdown).
        story_type: Type tag (maintenance, debug, etc.).
        output_dir: Directory to write the story file.
        priority: Task priority (high, normal, low). Written as metadata comment.
        depends_on: Optional list of task_path strings this story depends on.
            Written as a metadata comment for logging/traceability. The daemon
            does not enforce this; priority ordering is used instead.
    """
    import datetime
    if output_dir is None:
        output_dir = os.path.expanduser("~/GoogleDrive/DriveSyncFiles/sat-tasks/maintenance")
    os.makedirs(output_dir, exist_ok=True)

    # Generate story filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    safe_title = title.lower().replace(" ", "-")[:30]
    filename = f"proactive_{safe_title}_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)

    # Build metadata comments
    metadata_lines = []
    if priority != "normal":
        metadata_lines.append(f"<!-- priority: {priority} -->")
    if depends_on:
        dep_str = ", ".join(os.path.basename(d) for d in depends_on)
        metadata_lines.append(f"<!-- depends_on: {dep_str} -->")
    metadata_block = "\n".join(metadata_lines) + "\n" if metadata_lines else ""

    content = (
        f"{metadata_block}"
        f"# {title}\n\n"
        f"{description}\n\n"
        f"**Type:** {story_type}\n"
        f"**Source:** Proactive Agency (auto-generated)\n"
        f"**Generated:** {datetime.datetime.now().isoformat()}\n\n"
        f"<Pending>\n"
    )

    with open(filepath, "w") as f:
        f.write(content)
    return filepath


def _create_debug_story_with_deps(title, description, db_path=None, output_dir=None,
                                   project=None):
    """Create a Debug story with project-scoped prerequisite chains.

    Queries the task_states DB for in-progress and queued stories for the
    specified project. Sets up prerequisite chains:
    - Debug story depends on in-progress project stories (waits for them)
    - Queued project stories depend on the Debug story (wait for it)
    - If other Debug stories exist for this project, this one depends on them

    The daemon enforces these via the depends_on mechanism in task_states.

    Args:
        title: Debug story title.
        description: Debug story body (markdown).
        db_path: Path to sat.db (defaults to SAT_DB).
        output_dir: Directory to write the story file.
        project: Project name to scope dependencies. Defaults to SAT.

    Returns:
        filepath of the created debug story, or None if creation was skipped.
    """
    import sqlite3

    if db_path is None:
        db_path = str(SAT_DB)

    in_progress, queued = _get_project_stories(project=project, db_path=db_path)

    project_label = project or "structured-achievement-tool"

    # Check for existing debug stories for this project (chain them)
    existing_debug = []
    try:
        if os.path.isfile(db_path):
            conn = sqlite3.connect(db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            rows = conn.execute(
                "SELECT task_path FROM task_states "
                "WHERE project=? AND priority='high' AND status IN ('pending', 'working')",
                (project_label,),
            ).fetchall()
            existing_debug = [row["task_path"] for row in rows]
            conn.close()
    except Exception as e:
        print(f"  Could not query existing debug stories: {e}")

    # Build prerequisite list for the Debug story:
    # - In-progress project stories (wait for them to finish)
    # - Existing debug stories (chain sequentially)
    debug_depends_on = []
    if in_progress:
        debug_depends_on.extend(os.path.basename(tp) for tp in in_progress)
    if existing_debug:
        debug_depends_on.extend(os.path.basename(tp) for tp in existing_debug)

    # Log the dependency context
    if debug_depends_on:
        print(f"  Debug story for {project_label}: prerequisites = {debug_depends_on}")
    if queued:
        print(f"  Debug story for {project_label}: will set as prerequisite for {len(queued)} queued stories")
        for tp in queued:
            print(f"    - {os.path.basename(tp)}")

    # Add dependency context to the description
    dep_context = ""
    if in_progress or queued or existing_debug:
        dep_context = f"\n\n---\n**Dependency context (project: {project_label}):**\n"
        if in_progress:
            dep_context += "- Prerequisites (in-progress stories this debug story waits for):\n"
            for tp in in_progress:
                dep_context += f"  - `{os.path.basename(tp)}`\n"
        if existing_debug:
            dep_context += "- Prerequisites (existing debug stories to run before this one):\n"
            for tp in existing_debug:
                dep_context += f"  - `{os.path.basename(tp)}`\n"
        if queued:
            dep_context += "- Dependents (queued stories that will wait for this debug story):\n"
            for tp in queued:
                dep_context += f"  - `{os.path.basename(tp)}`\n"

    # Include project metadata in the story file
    project_metadata = f"<!-- project: {project_label} -->\n" if project_label else ""

    filepath = _create_maintenance_story(
        title,
        project_metadata + description + dep_context,
        story_type="debug",
        output_dir=output_dir,
        priority="high",
        depends_on=debug_depends_on if debug_depends_on else None,
    )

    # Update queued project stories to depend on this debug story
    if filepath and queued:
        debug_basename = os.path.basename(filepath)
        try:
            if os.path.isfile(db_path):
                conn = sqlite3.connect(db_path, timeout=5)
                conn.execute("PRAGMA journal_mode=WAL")
                for task_path in queued:
                    # Read existing depends_on, add this debug story
                    row = conn.execute(
                        "SELECT depends_on FROM task_states WHERE task_path=?",
                        (task_path,),
                    ).fetchone()
                    if row:
                        import json as _json
                        try:
                            current = _json.loads(row[0] or "[]")
                        except (_json.JSONDecodeError, TypeError):
                            current = []
                        if debug_basename not in current:
                            current.append(debug_basename)
                            conn.execute(
                                "UPDATE task_states SET depends_on=? WHERE task_path=?",
                                (_json.dumps(current), task_path),
                            )
                            print(f"    Added prerequisite '{debug_basename}' to {os.path.basename(task_path)}")
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"  Could not update queued story prerequisites: {e}")

    return filepath

def run_proactive_checks():
    """Run proactive checks and create maintenance stories if needed.

    Called with --proactive flag. Checks intervals and creates stories
    for overdue maintenance tasks.
    """
    import datetime

    # Load config
    config = {}
    config_path = os.path.join(PROJECT_PATH, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    pa_config = config.get("proactive_agency", {})
    if not pa_config.get("enabled", False):
        return []

    output_dir = os.path.expanduser(pa_config.get(
        "story_output_dir",
        "~/GoogleDrive/DriveSyncFiles/sat-tasks/maintenance"
    ))

    state = _load_proactive_state()
    created = []
    now_iso = datetime.datetime.now().isoformat()

    # 1. Config validation
    config_interval = pa_config.get("config_validation_interval_hours", 24)
    if _hours_since(state.get("last_config_check")) >= config_interval:
        # Check for common config issues
        issues = []
        if not os.path.exists(config_path):
            issues.append("config.json is missing")
        else:
            try:
                with open(config_path) as f:
                    cfg = json.load(f)
                if not cfg.get("routing_rules_enabled"):
                    issues.append("routing_rules_enabled is not set")
                if not cfg.get("execution", {}).get("checkpoint_db"):
                    issues.append("checkpoint_db path is not configured")
            except json.JSONDecodeError:
                issues.append("config.json has invalid JSON")

        if issues:
            filepath = _create_debug_story_with_deps(
                "Config Validation Issues",
                "Proactive check found configuration issues:\n\n" +
                "\n".join(f"- {i}" for i in issues),
                output_dir=output_dir,
            )
            created.append(filepath)

        state["last_config_check"] = now_iso

    # 2. Dependency check
    dep_interval = pa_config.get("dependency_check_interval_hours", 336)
    if _hours_since(state.get("last_dependency_check")) >= dep_interval:
        # Check if requirements.txt exists and has content
        req_path = os.path.join(PROJECT_PATH, "requirements.txt")
        if os.path.exists(req_path):
            filepath = _create_debug_story_with_deps(
                "Dependency Update Review",
                "Scheduled dependency review.\n\n"
                "Check for outdated packages, security vulnerabilities, "
                "and compatibility issues.",
                output_dir=output_dir,
            )
            created.append(filepath)

        state["last_dependency_check"] = now_iso

    # 3. General maintenance
    maint_interval = pa_config.get("maintenance_interval_hours", 168)
    if _hours_since(state.get("last_maintenance")) >= maint_interval:
        # Check for cleanup opportunities
        cleanup_items = []
        log_dir = os.path.join(PROJECT_PATH, "logs")
        if os.path.exists(log_dir):
            log_files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
            if len(log_files) > 10:
                cleanup_items.append(f"{len(log_files)} log files in logs/ — consider rotation")

        memory_dir = os.path.join(PROJECT_PATH, ".memory")
        if os.path.exists(memory_dir):
            journal_path = os.path.join(memory_dir, "audit_journal.jsonl")
            if os.path.exists(journal_path):
                size_mb = os.path.getsize(journal_path) / (1024 * 1024)
                if size_mb > 10:
                    cleanup_items.append(f"Audit journal is {size_mb:.1f}MB — consider archiving")

        if cleanup_items:
            filepath = _create_debug_story_with_deps(
                "Scheduled Maintenance",
                "Scheduled maintenance review:\n\n" +
                "\n".join(f"- {i}" for i in cleanup_items),
                output_dir=output_dir,
            )
            created.append(filepath)

        state["last_maintenance"] = now_iso

    _save_proactive_state(state)

    if created:
        notify(
            "SAT: Proactive Maintenance",
            f"Created {len(created)} maintenance stories.",
            tags="wrench,robot",
        )

    return created


if __name__ == "__main__":
    if "--proactive" in sys.argv:
        created = run_proactive_checks()
        if created:
            print(f"Created {len(created)} proactive stories:")
            for f in created:
                print(f"  - {f}")
        else:
            print("No proactive actions needed.")
        sys.exit(0)
    sys.exit(main())
