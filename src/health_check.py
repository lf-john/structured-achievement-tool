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

import os, subprocess, sys, time, json, requests

# Cron doesn't have the user D-Bus session. Set the env vars so systemctl --user works.
UID = os.getuid()
os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{UID}")
os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{UID}/bus")

WATCH_DIRS = [
    "/home/johnlane/GoogleDrive/DriveSyncFiles/sat-tasks",
]
NTFY_TOPIC = "johnlane-claude-tasks"
NTFY_SERVER = "https://ntfy.sh"
PROJECT_PATH = "/home/johnlane/projects/structured-achievement-tool"

def notify(title, message, priority="default", tags=""):
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
    """Check if Google Drive mount is accessible."""
    return os.path.exists("/home/johnlane/GoogleDrive/DriveSyncFiles/sat-tasks")

def check_dashboard():
    """Check if the SAT dashboard is responding."""
    try:
        res = requests.get("http://localhost:8765/api/status", timeout=5)
        return res.status_code == 200
    except:
        return False

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
                    with open(path, 'r') as file:
                        content = file.read()
                    if '<!-- CLAUDE-RESPONSE -->' in content[:200]:
                        continue
                    if "<Finished>" in content:
                        status["finished"] += 1
                    elif "<Working>" in content:
                        status["working"] += 1
                        issues.append(f"WORKING: {task_dir_name}/{f}")
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

    # 6. Scan tasks
    task_status, task_issues = scan_tasks()

    # Build report
    report = f"SAT Health Check Report\n"
    report += f"{'='*40}\n"
    report += f"Services: sat={'OK' if check_service('sat.service') else 'DOWN'}, "
    report += f"monitor={'OK' if check_service('sat-monitor.service') else 'DOWN'}, "
    report += f"ollama={'OK' if check_ollama() else 'DOWN'}\n"
    report += f"GDrive: {'OK' if check_gdrive() else 'DOWN'}\n"
    report += f"Tasks: {task_status['finished']} done, {task_status['working']} active, "
    report += f"{task_status['failed']} failed, {task_status['queued']} queued, {task_status['waiting']} waiting\n"

    if problems:
        report += f"\nProblems:\n"
        for p in problems:
            report += f"  - {p}\n"

    if actions:
        report += f"\nActions taken:\n"
        for a in actions:
            report += f"  - {a}\n"

    if task_issues:
        report += f"\nTask issues:\n"
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

    return 0 if not problems else 1

## --- Proactive Agency ---

PROACTIVE_STATE_FILE = os.path.join(PROJECT_PATH, ".memory", "proactive_state.json")

def _load_proactive_state():
    """Load last-run timestamps for proactive checks."""
    if os.path.exists(PROACTIVE_STATE_FILE):
        try:
            with open(PROACTIVE_STATE_FILE, "r") as f:
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

def _create_maintenance_story(title, description, story_type="maintenance", output_dir=None):
    """Create a story file for proactive maintenance."""
    import datetime
    if output_dir is None:
        output_dir = os.path.expanduser("~/GoogleDrive/DriveSyncFiles/sat-tasks/maintenance")
    os.makedirs(output_dir, exist_ok=True)

    # Generate story filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    safe_title = title.lower().replace(" ", "-")[:30]
    filename = f"proactive_{safe_title}_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)

    content = (
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
            with open(config_path, "r") as f:
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
            filepath = _create_maintenance_story(
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
            filepath = _create_maintenance_story(
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
            filepath = _create_maintenance_story(
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
