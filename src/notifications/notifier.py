"""
Notification Service — Push notifications via ntfy + email via SMTP (SES-ready).

Extracted from orchestrator._send_notification() and extended with email support.
"""

import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

logger = logging.getLogger(__name__)


class Notifier:
    """Send notifications via ntfy and/or email."""

    # Priority levels in ascending order
    PRIORITY_LEVELS = {"min": 0, "low": 1, "default": 2, "high": 3, "urgent": 4}

    def __init__(
        self,
        ntfy_topic: str | None = None,
        ntfy_server: str | None = None,
        ntfy_min_priority: str | None = None,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        notify_email: str | None = None,
        config: dict | None = None,
    ):
        # Load notification config from config.json if not provided
        if config is None:
            config = self._load_notification_config()
        self._config = config

        self.ntfy_topic = ntfy_topic or os.environ.get("NTFY_TOPIC", "")
        self.ntfy_server = ntfy_server or os.environ.get("NTFY_SERVER", "https://ntfy.sh")
        self.ntfy_min_priority = (
            ntfy_min_priority or config.get("ntfy_min_priority") or os.environ.get("SAT_NTFY_MIN_PRIORITY", "default")
        )
        self.smtp_host = smtp_host or os.environ.get("SAT_SMTP_HOST", "")
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user or os.environ.get("SAT_SMTP_USER", "")
        self.smtp_password = smtp_password or os.environ.get("SAT_SMTP_PASSWORD", "")
        self.notify_email = notify_email or os.environ.get("SAT_NOTIFY_EMAIL", "")
        self._email_warning_logged = False

    @staticmethod
    def _load_notification_config() -> dict:
        """Load the notifications section from config.json."""
        try:
            from src.core.paths import CONFIG_JSON

            config_path = str(CONFIG_JSON)
        except ImportError:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config.json",
            )
        try:
            with open(config_path) as f:
                return json.load(f).get("notifications", {})
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def send_ntfy(self, title: str, message: str, priority: str = "default", tags: str = "") -> bool:
        """Send a push notification via ntfy.sh.

        Respects SAT_NTFY_MIN_PRIORITY: notifications below the minimum
        priority are silently dropped. Set to 'high' to only receive
        important notifications (failures, escalations, human action required).
        """
        if not self.ntfy_topic:
            return False

        # Filter by minimum priority
        msg_level = self.PRIORITY_LEVELS.get(priority, 2)
        min_level = self.PRIORITY_LEVELS.get(self.ntfy_min_priority, 2)
        if msg_level < min_level:
            logger.debug(f"Ntfy filtered: {title} (priority={priority} < min={self.ntfy_min_priority})")
            return False

        url = f"{self.ntfy_server}/{self.ntfy_topic}"
        headers = {}
        if title:
            headers["Title"] = title
        if priority != "default":
            headers["Priority"] = priority
        if tags:
            headers["Tags"] = tags

        try:
            resp = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=5)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to send ntfy notification: {e}")
            return False

    def send_email(
        self,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        recipient: str | None = None,
    ) -> bool:
        """Send an email notification via SMTP (SES-ready).

        Args:
            subject: Email subject line.
            body_html: HTML body content.
            body_text: Plain text body (optional fallback).
            recipient: Override recipient address. Defaults to self.notify_email.
        """
        to_addr = recipient or self.notify_email
        if not all([self.smtp_host, self.smtp_user, to_addr]):
            if not self._email_warning_logged:
                missing = []
                if not self.smtp_host:
                    missing.append("SAT_SMTP_HOST")
                if not self.smtp_user:
                    missing.append("SAT_SMTP_USER")
                if not to_addr:
                    missing.append("SAT_NOTIFY_EMAIL")
                logger.warning(
                    "Email not configured (missing: %s). "
                    "Set these env vars or pass them to Notifier to enable email notifications. "
                    "This warning will not repeat.",
                    ", ".join(missing),
                )
                self._email_warning_logged = True
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = to_addr

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, to_addr, msg.as_string())
            return True
        except Exception as e:
            logger.warning(f"Failed to send email: {e}")
            return False

    def notify_task_start(self, task_id: str, story_count: int):
        """Notify that a task has been decomposed and is starting execution.

        Silently skips notification if story_count is 0 (decomposition failure).
        """
        if story_count == 0:
            return
        self.send_ntfy(
            title=f"SAT: {task_id} - {story_count} stories",
            message="Task decomposed and beginning execution.",
            tags="memo,robot",
        )

    def notify_story_complete(self, story_id: str, story_title: str):
        """Notify that a story completed successfully.

        Skipped unless config notify_on_story_complete is true (default: false)
        to avoid excessive notifications during multi-story tasks.
        """
        if not self._config.get("notify_on_story_complete", False):
            return
        self.send_ntfy(
            title="SAT: Story Complete",
            message=f"{story_id}: {story_title}",
            priority="high",
            tags="tada",
        )

    def notify_story_failed(self, story_id: str, story_title: str, reason: str):
        """Notify that a story failed after all retries."""
        self.send_ntfy(
            title="SAT: Story Failed",
            message=f"{story_id}: {story_title}\nReason: {reason}",
            tags="x",
            priority="high",
        )

    def notify_task_complete(self, task_id: str, completed: int, total: int, success: bool):
        """Notify task completion with summary."""
        status = "Complete" if success else "Partial"
        self.send_ntfy(
            title=f"SAT: Task {status} ({task_id})",
            message=f"{completed}/{total} stories completed.",
            tags="white_check_mark" if success else "warning",
            priority="default" if success else "high",
        )

        # Also send email if configured
        if self.smtp_host:
            html = f"""
            <h2>SAT Task {status}: {task_id}</h2>
            <p><strong>{completed}/{total}</strong> stories completed.</p>
            """
            self.send_email(
                subject=f"SAT: Task {status} - {task_id}",
                body_html=html,
                body_text=f"SAT Task {status}: {task_id}\n{completed}/{total} stories completed.",
            )

    def notify_human_action_required(
        self,
        story_id: str,
        story_title: str,
        story_type: str,
        signal_path: str,
    ):
        """Notify that a human story requires action."""
        type_tags = {
            "assignment": "clipboard,hand",
            "approval": "hand,warning",
            "qa_feedback": "mag,clipboard",
            "escalation": "rotating_light,warning",
        }
        self.send_ntfy(
            title=f"SAT: {story_type.title()} Required ({story_id})",
            message=f"Story: {story_title}\nSignal file: {signal_path}",
            priority="high" if story_type != "escalation" else "urgent",
            tags=type_tags.get(story_type, "hand"),
        )

    def notify_human_response_received(self, story_id: str, story_type: str):
        """Notify that a human response was received and processing continues."""
        self.send_ntfy(
            title=f"SAT: Response Received ({story_id})",
            message=f"{story_type.title()} response received. Processing continues.",
            tags="white_check_mark",
        )

    def notify_escalation(
        self,
        story_id: str,
        story_title: str,
        failure_summary: str,
        recipient: str | None = None,
    ):
        """Send escalation notification via ntfy and optionally email."""
        self.send_ntfy(
            title=f"SAT: ESCALATION ({story_id})",
            message=f"Story: {story_title}\n{failure_summary}",
            priority="urgent",
            tags="rotating_light,warning",
        )
        if self.smtp_host:
            html = (
                f"<h2>Escalation: {story_id}</h2><p><strong>Story:</strong> {story_title}</p><p>{failure_summary}</p>"
            )
            self.send_email(
                subject=f"SAT: ESCALATION - {story_id}",
                body_html=html,
                body_text=f"Escalation: {story_id}\n{story_title}\n{failure_summary}",
                recipient=recipient,
            )

    # --- Progress Bar ---

    def send_progress(
        self,
        task_id: str,
        completed: int,
        total: int,
        current_story: str = "",
        current_phase: str = "",
    ) -> bool:
        """Send a single updating progress notification for a task.

        Uses ntfy's message update feature (same topic + tag combination)
        to show a visual progress bar that updates in place.

        Format:
            SAT: task-id [████████░░] 8/10
            Current: story-title (PHASE)
        """
        if total == 0:
            return False

        # Build progress bar (10 chars wide)
        filled = round(completed / total * 10)
        bar = "█" * filled + "░" * (10 - filled)

        message_parts = [f"[{bar}] {completed}/{total} stories"]
        if current_story:
            phase_str = f" ({current_phase})" if current_phase else ""
            message_parts.append(f"Current: {current_story}{phase_str}")

        message = "\n".join(message_parts)

        if completed == total:
            tags = "white_check_mark"
            priority = "default"
        elif completed == 0:
            tags = "hourglass"
            priority = "default"
        else:
            tags = "rocket"
            priority = "default"

        return self.send_ntfy(
            title=f"SAT: {task_id} [{completed}/{total}]",
            message=message,
            priority=priority,
            tags=tags,
        )

    def notify_debug_budget_exhausted(self, task_id: str, attempts: int, last_error_summary: str):
        """Notify that a task has exhausted its debug budget."""
        error_summary = last_error_summary if last_error_summary else "(No summary provided)"
        message = f"Task: {task_id}\nAttempts: {attempts}\nLast Error: {error_summary}"
        self.send_ntfy(
            title=f"SAT: Debug Budget Exhausted ({task_id})",
            message=message,
            priority="urgent",
            tags="warning",
        )

    def notify_ollama_unavailable(self, task_id: str):
        """Notify that Ollama is unavailable and the task will be retried."""
        self.send_ntfy(
            title=f"SAT: Ollama Unavailable ({task_id})",
            message="Ollama is currently down. Task will be queued for retry.",
            priority="high",
            tags="warning,hourglass",
        )
