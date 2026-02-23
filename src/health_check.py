#!/usr/bin/env python3
"""SAT Health Check Script - Run via cron to monitor system health.

Checks:
1. SAT daemon is running
2. SAT monitor is running
3. Ollama is healthy
4. No tasks stuck in <Working> or <Failed>
5. Google Drive mount is accessible
6. Ralph Pro is available

Outputs a status report and takes corrective action where possible.
Sends ntfy notification on failures.
"""

import os, subprocess, sys, time, json, requests

# Cron doesn't have the user D-Bus session. Set the env vars so systemctl --user works.
UID = os.getuid()
os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{UID}")
os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{UID}/bus")

WATCH_DIRS = [
    "/home/johnlane/GoogleDrive/DriveSyncFiles/claude-tasks/sat-enhancements",
    "/home/johnlane/GoogleDrive/DriveSyncFiles/claude-tasks/marketing-automation"
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
    return os.path.exists("/home/johnlane/GoogleDrive/DriveSyncFiles/claude-tasks")

def check_ralph_pro():
    """Check if Ralph Pro CLI exists."""
    return os.path.exists("/home/johnlane/ralph-pro/cli/ralph-pro.js")

def scan_tasks():
    """Scan task directories for status."""
    status = {"finished": 0, "working": 0, "failed": 0, "queued": 0, "waiting": 0}
    issues = []

    for d in WATCH_DIRS:
        if not os.path.exists(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith('.md') or f.startswith('_') or '_response' in f:
                continue
            path = os.path.join(d, f)
            try:
                with open(path, 'r') as file:
                    content = file.read()
                if "<Finished>" in content:
                    status["finished"] += 1
                elif "<Working>" in content:
                    status["working"] += 1
                    issues.append(f"WORKING: {os.path.basename(d)}/{f}")
                elif "<Failed>" in content:
                    status["failed"] += 1
                    issues.append(f"FAILED: {os.path.basename(d)}/{f}")
                elif "<User>" in content and "# <User>" not in content:
                    status["queued"] += 1
                elif "# <User>" in content:
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

    # 5. Check Ralph Pro
    if not check_ralph_pro():
        problems.append("Ralph Pro CLI not found")

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

if __name__ == "__main__":
    sys.exit(main())
