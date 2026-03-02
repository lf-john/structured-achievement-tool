"""
Layer 2 LLM-powered system audit (Phase 2 item 2.5).

Runs every 30 minutes via systemd timer. Collects system health data,
sends it to an LLM for assessment, and saves timestamped audit results.
Sends ntfy notifications when issues are detected.
"""

import os
import json
import time
import hashlib
import subprocess
import logging
import shutil
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIT_DIR = ".memory/audits"
from src.core.paths import SAT_TASKS_DIR

TASK_DIRS = [str(SAT_TASKS_DIR)]
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

# Set D-Bus env for systemctl --user from cron context
UID = os.getuid()
os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{UID}")
os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{UID}/bus")


MAINTENANCE_AUDIT_LOG = ".memory/maintenance_audit.jsonl"
MAINTENANCE_AUDIT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


class MaintenanceAuditLog:
    """Append-only JSONL audit log for maintenance operations."""

    def __init__(self, path: str = MAINTENANCE_AUDIT_LOG,
                 max_bytes: int = MAINTENANCE_AUDIT_MAX_BYTES):
        self.path = path
        self.max_bytes = max_bytes
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def write(self, source: str, action: str, details: Optional[dict] = None,
              llm_response_hash: Optional[str] = None):
        """Append one audit entry, rotating if the file exceeds max_bytes."""
        self._rotate_if_needed()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "action": action,
            "details": details,
            "llm_response_hash": llm_response_hash,
        }
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError as e:
            logger.error("Failed to write maintenance audit log: %s", e)

    def _rotate_if_needed(self):
        """Rotate log file if it exceeds max_bytes. Keep 1 backup."""
        try:
            if os.path.exists(self.path) and os.path.getsize(self.path) > self.max_bytes:
                backup = self.path + ".1"
                shutil.move(self.path, backup)
                logger.info("Rotated maintenance audit log to %s", backup)
        except OSError as e:
            logger.warning("Failed to rotate maintenance audit log: %s", e)

    @staticmethod
    def hash_response(response: str) -> str:
        """SHA-256 hash of a raw LLM response string."""
        return hashlib.sha256(response.encode("utf-8")).hexdigest()


class SystemAuditor:
    def __init__(self, audit_dir: str = AUDIT_DIR,
                 maintenance_log: Optional[MaintenanceAuditLog] = None):
        self.audit_dir = audit_dir
        self.audit_log = maintenance_log or MaintenanceAuditLog()
        os.makedirs(audit_dir, exist_ok=True)

    def collect_inputs(self) -> dict:
        """Gather audit data: recent tasks, system metrics, debug history."""
        return {
            "recent_tasks": self._get_recent_tasks(),
            "system_health": self._get_system_health(),
            "debug_history": self._get_debug_history(),
            "service_status": self._get_service_status(),
        }

    def build_audit_prompt(self, inputs: dict) -> str:
        """Build an LLM prompt from collected inputs."""
        prompt = "You are a system health auditor for the SAT (Structured Achievement Tool).\n"
        prompt += "Analyze the following system state and provide an assessment.\n\n"

        prompt += "## Service Status\n"
        for svc, status in inputs.get("service_status", {}).items():
            prompt += f"- {svc}: {'active' if status else 'INACTIVE'}\n"

        prompt += "\n## System Health\n"
        health = inputs.get("system_health", {})
        if health.get("disk"):
            prompt += f"- Disk: {health['disk']}\n"
        if health.get("memory"):
            prompt += f"- Memory: {health['memory']}\n"

        prompt += "\n## Recent Tasks (last hour)\n"
        recent = inputs.get("recent_tasks", [])
        if recent:
            for t in recent:
                prompt += f"- {t.get('file', 'unknown')}: {t.get('status', 'unknown')}\n"
        else:
            prompt += "- No recent task activity\n"

        prompt += "\n## Debug History\n"
        debug = inputs.get("debug_history", [])
        if debug:
            for d in debug:
                prompt += f"- {d}\n"
        else:
            prompt += "- No recent debug attempts\n"

        prompt += "\n## Instructions\n"
        prompt += "Respond with a JSON object containing:\n"
        prompt += '- "status": one of "ok", "warning", "critical"\n'
        prompt += '- "issues": array of issue strings (empty if ok)\n'
        prompt += '- "recommendations": array of recommendation strings\n'
        prompt += "Respond with ONLY the JSON object, no other text.\n"

        return prompt

    def parse_audit_response(self, response: str) -> dict:
        """Parse the LLM response for issues and recommendations.

        Returns: {"status": "ok"|"warning"|"critical", "issues": [...], "recommendations": [...]}
        """
        default = {"status": "ok", "issues": [], "recommendations": []}

        if not response or not response.strip():
            return default

        # Try to extract JSON from response (LLM may wrap in markdown code block)
        text = response.strip()
        if "```" in text:
            # Extract content between code fences
            parts = text.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("{"):
                    text = stripped
                    break

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM audit response as JSON")
            return {
                "status": "warning",
                "issues": ["LLM audit response was not valid JSON"],
                "recommendations": ["Check LLM connectivity"],
            }

        # Validate required fields
        status = parsed.get("status", "ok")
        if status not in ("ok", "warning", "critical"):
            status = "warning"

        return {
            "status": status,
            "issues": parsed.get("issues", []),
            "recommendations": parsed.get("recommendations", []),
        }

    def run_audit(self) -> dict:
        """Execute a full audit cycle. Returns audit result."""
        timestamp = datetime.now().isoformat()

        self.audit_log.write(
            source="audit_cronjob", action="audit_started",
            details={"timestamp": timestamp},
        )

        inputs = self.collect_inputs()
        prompt = self.build_audit_prompt(inputs)

        # Invoke LLM via ollama CLI
        llm_response = self._invoke_llm(prompt)
        response_hash = MaintenanceAuditLog.hash_response(llm_response)
        result = self.parse_audit_response(llm_response)

        self.audit_log.write(
            source="audit_cronjob", action="llm_response_received",
            details={"status": result.get("status", "unknown")},
            llm_response_hash=response_hash,
        )

        # Log detected issues
        issues = result.get("issues", [])
        if issues:
            self.audit_log.write(
                source="audit_cronjob", action="issues_detected",
                details={"issues": issues},
            )

        result["timestamp"] = timestamp
        result["inputs"] = inputs
        result["llm_response_raw"] = llm_response

        return result

    def save_audit_result(self, result: dict) -> str:
        """Save audit result to timestamped file. Returns filepath."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audit_{ts}.json"
        filepath = os.path.join(self.audit_dir, filename)
        os.makedirs(self.audit_dir, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)

        logger.info("Saved audit result to %s", filepath)
        return filepath

    def _get_recent_tasks(self, hours: int = 1) -> list:
        """Get tasks modified in the last N hours."""
        cutoff = time.time() - (hours * 3600)
        recent = []

        for watch_dir in TASK_DIRS:
            if not os.path.exists(watch_dir):
                continue
            for task_dir_name in os.listdir(watch_dir):
                task_dir = os.path.join(watch_dir, task_dir_name)
                if not os.path.isdir(task_dir) or task_dir_name.startswith("_"):
                    continue
                for fname in os.listdir(task_dir):
                    if not fname.endswith(".md") or fname.startswith("_") or "_response" in fname:
                        continue
                    fpath = os.path.join(task_dir, fname)
                    try:
                        mtime = os.path.getmtime(fpath)
                        if mtime >= cutoff:
                            with open(fpath, "r", encoding="utf-8") as f:
                                content = f.read(500)
                            status = "unknown"
                            for tag in ("<Finished>", "<Working>", "<Failed>", "<Pending>"):
                                if tag in content:
                                    status = tag
                                    break
                            recent.append({
                                "file": f"{task_dir_name}/{fname}",
                                "status": status,
                                "mtime": mtime,
                            })
                    except OSError:
                        continue

        return recent

    def _get_system_health(self) -> dict:
        """Get disk, memory usage."""
        health = {}
        try:
            res = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True, text=True, timeout=5,
            )
            if res.returncode == 0:
                health["disk"] = res.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            health["disk"] = "unavailable"

        try:
            res = subprocess.run(
                ["free", "-h"],
                capture_output=True, text=True, timeout=5,
            )
            if res.returncode == 0:
                health["memory"] = res.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            health["memory"] = "unavailable"

        return health

    def _get_debug_history(self) -> list:
        """Get recent debug attempts from budget manager state."""
        debug_file = ".memory/debug_budget.json"
        if not os.path.exists(debug_file):
            return []
        try:
            with open(debug_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = []
            for task_id, info in data.items():
                entries.append(f"{task_id}: attempts={info.get('attempts', '?')}, "
                               f"last={info.get('last_attempt', 'unknown')}")
            return entries
        except (json.JSONDecodeError, OSError):
            return []

    def _get_service_status(self) -> dict:
        """Check status of sat.service, sat-monitor.service, ollama.service."""
        services = ["sat.service", "sat-monitor.service", "ollama.service"]
        result = {}
        for svc in services:
            try:
                res = subprocess.run(
                    ["systemctl", "--user", "is-active", svc],
                    capture_output=True, text=True, timeout=5,
                )
                result[svc] = res.stdout.strip() == "active"
            except (subprocess.TimeoutExpired, OSError):
                result[svc] = False
        return result

    def _invoke_llm(self, prompt: str) -> str:
        """Invoke Ollama for audit analysis."""
        try:
            res = subprocess.run(
                ["ollama", "run", "qwen3:8b", "--", prompt],
                capture_output=True, text=True, timeout=120,
            )
            if res.returncode == 0:
                return res.stdout.strip()
            logger.warning("Ollama returned exit code %d: %s", res.returncode, res.stderr)
            return ""
        except subprocess.TimeoutExpired:
            logger.error("Ollama timed out during audit")
            return ""
        except OSError as e:
            logger.error("Failed to invoke ollama: %s", e)
            return ""

    def send_notification(self, result: dict):
        """Send ntfy notification if issues found."""
        status = result.get("status", "ok")
        if status == "ok":
            return

        self.audit_log.write(
            source="audit_cronjob", action="notification_sent",
            details={"status": status, "issue_count": len(result.get("issues", []))},
        )

        issues = result.get("issues", [])
        recommendations = result.get("recommendations", [])

        title = f"SAT Audit: {status.upper()}"
        body_parts = []
        if issues:
            body_parts.append("Issues:")
            for issue in issues:
                body_parts.append(f"  - {issue}")
        if recommendations:
            body_parts.append("Recommendations:")
            for rec in recommendations:
                body_parts.append(f"  - {rec}")

        body = "\n".join(body_parts)
        priority = "urgent" if status == "critical" else "high"
        tags = "rotating_light" if status == "critical" else "warning"

        try:
            subprocess.run(
                [
                    "curl", "-s",
                    "-H", f"Title: {title}",
                    "-H", f"Priority: {priority}",
                    "-H", f"Tags: {tags}",
                    "-d", body,
                    f"{NTFY_SERVER}/{NTFY_TOPIC}",
                ],
                capture_output=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            logger.error("Failed to send ntfy notification")


def main():
    """Entry point for systemd timer / cron."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    auditor = SystemAuditor()
    result = auditor.run_audit()
    filepath = auditor.save_audit_result(result)
    auditor.send_notification(result)

    logger.info("Audit complete: status=%s, saved to %s", result.get("status"), filepath)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
