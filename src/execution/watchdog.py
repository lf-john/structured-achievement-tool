"""
Monitor Watchdog (Phase 2 item 2.6).

Lightweight script that runs every 15 minutes and checks if Layer 1
(sat-monitor) and Layer 2 (audit cronjob) are healthy. Attempts
auto-restart of failed services and sends ntfy alerts.
"""

import logging
import os
import subprocess
import time

logger = logging.getLogger(__name__)

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

# Set D-Bus env for systemctl --user from cron context
UID = os.getuid()
os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{UID}")
os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{UID}/bus")


class Watchdog:
    def __init__(
        self,
        monitor_service: str = "sat-monitor.service",
        daemon_service: str = "sat.service",
        audit_dir: str = ".memory/audits",
        audit_max_age: int = 2700,  # 45 minutes (30 min interval + 15 min slack)
    ):
        self.monitor_service = monitor_service
        self.daemon_service = daemon_service
        self.audit_dir = audit_dir
        self.audit_max_age = audit_max_age

    def check_service(self, service_name: str) -> bool:
        """Check if a systemd service is active."""
        try:
            res = subprocess.run(
                ["systemctl", "--user", "is-active", service_name],
                capture_output=True, text=True, timeout=5,
            )
            return res.stdout.strip() == "active"
        except (subprocess.TimeoutExpired, OSError):
            return False

    def check_audit_freshness(self) -> tuple:
        """Check if audit results are recent enough.

        Returns (is_fresh, last_audit_path).
        """
        if not os.path.isdir(self.audit_dir):
            return False, None

        try:
            entries = sorted(os.listdir(self.audit_dir), reverse=True)
        except OSError:
            return False, None

        # Find the most recent audit file
        for entry in entries:
            if entry.startswith("audit_") and entry.endswith(".json"):
                filepath = os.path.join(self.audit_dir, entry)
                try:
                    mtime = os.path.getmtime(filepath)
                    age = time.time() - mtime
                    return age <= self.audit_max_age, filepath
                except OSError:
                    continue

        return False, None

    def run_checks(self) -> dict:
        """Run all watchdog checks. Returns results dict."""
        results = {
            "timestamp": time.time(),
            "checks": {},
            "alerts": [],
            "restarts": [],
        }

        # Check daemon service
        daemon_ok = self.check_service(self.daemon_service)
        results["checks"]["daemon"] = daemon_ok
        if not daemon_ok:
            results["alerts"].append(f"{self.daemon_service} is not active")
            if self.attempt_restart(self.daemon_service):
                results["restarts"].append(f"{self.daemon_service} restarted successfully")
                results["checks"]["daemon"] = True
            else:
                results["restarts"].append(f"{self.daemon_service} restart FAILED")

        # Check monitor service
        monitor_ok = self.check_service(self.monitor_service)
        results["checks"]["monitor"] = monitor_ok
        if not monitor_ok:
            results["alerts"].append(f"{self.monitor_service} is not active")
            if self.attempt_restart(self.monitor_service):
                results["restarts"].append(f"{self.monitor_service} restarted successfully")
                results["checks"]["monitor"] = True
            else:
                results["restarts"].append(f"{self.monitor_service} restart FAILED")

        # Check audit freshness
        audit_fresh, last_audit = self.check_audit_freshness()
        results["checks"]["audit_fresh"] = audit_fresh
        results["checks"]["last_audit"] = last_audit
        if not audit_fresh:
            if last_audit is None:
                results["alerts"].append("No audit results found")
            else:
                results["alerts"].append("Audit results are stale (older than "
                                         f"{self.audit_max_age}s)")

        # Send alerts if any
        if results["alerts"]:
            alert_msg = "Watchdog Alerts:\n" + "\n".join(
                f"  - {a}" for a in results["alerts"]
            )
            if results["restarts"]:
                alert_msg += "\n\nActions:\n" + "\n".join(
                    f"  - {r}" for r in results["restarts"]
                )
            self.send_alert(alert_msg)

        return results

    def send_alert(self, message: str):
        """Send ntfy alert."""
        try:
            subprocess.run(
                [
                    "curl", "-s",
                    "-H", "Title: SAT Watchdog Alert",
                    "-H", "Priority: high",
                    "-H", "Tags: warning,dog",
                    "-d", message,
                    f"{NTFY_SERVER}/{NTFY_TOPIC}",
                ],
                capture_output=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            logger.error("Failed to send watchdog ntfy alert")

    def attempt_restart(self, service_name: str) -> bool:
        """Try to restart a failed service."""
        try:
            subprocess.run(
                ["systemctl", "--user", "restart", service_name],
                capture_output=True, text=True, timeout=15,
            )
            # Wait briefly for service to come up
            time.sleep(3)
            return self.check_service(service_name)
        except (subprocess.TimeoutExpired, OSError):
            logger.error("Failed to restart %s", service_name)
            return False


def main():
    """Entry point for systemd timer / cron."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    watchdog = Watchdog()
    results = watchdog.run_checks()

    all_ok = not results["alerts"]
    logger.info(
        "Watchdog complete: %s (checks=%s, alerts=%d)",
        "OK" if all_ok else "ISSUES FOUND",
        results["checks"],
        len(results["alerts"]),
    )

    return 0 if all_ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
