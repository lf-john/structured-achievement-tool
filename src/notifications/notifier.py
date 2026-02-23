"""
Notification Service — Push notifications via ntfy + email via SMTP (SES-ready).

Extracted from orchestrator._send_notification() and extended with email support.
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class Notifier:
    """Send notifications via ntfy and/or email."""

    def __init__(
        self,
        ntfy_topic: Optional[str] = None,
        ntfy_server: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        notify_email: Optional[str] = None,
    ):
        self.ntfy_topic = ntfy_topic or os.environ.get("NTFY_TOPIC", "johnlane-claude-tasks")
        self.ntfy_server = ntfy_server or os.environ.get("NTFY_SERVER", "https://ntfy.sh")
        self.smtp_host = smtp_host or os.environ.get("SAT_SMTP_HOST", "")
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user or os.environ.get("SAT_SMTP_USER", "")
        self.smtp_password = smtp_password or os.environ.get("SAT_SMTP_PASSWORD", "")
        self.notify_email = notify_email or os.environ.get("SAT_NOTIFY_EMAIL", "")

    def send_ntfy(self, title: str, message: str, priority: str = "default", tags: str = "") -> bool:
        """Send a push notification via ntfy.sh."""
        if not self.ntfy_topic:
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

    def send_email(self, subject: str, body_html: str, body_text: Optional[str] = None) -> bool:
        """Send an email notification via SMTP (SES-ready)."""
        if not all([self.smtp_host, self.smtp_user, self.notify_email]):
            logger.debug("Email not configured, skipping")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = self.notify_email

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, self.notify_email, msg.as_string())
            return True
        except Exception as e:
            logger.warning(f"Failed to send email: {e}")
            return False

    def notify_task_start(self, task_id: str, story_count: int):
        """Notify that a task has been decomposed and is starting execution."""
        self.send_ntfy(
            title=f"SAT: Task Decomposed ({task_id})",
            message=f"Decomposed into {story_count} stories. Beginning execution.",
            tags="memo,robot",
        )

    def notify_story_complete(self, story_id: str, story_title: str):
        """Notify that a story completed successfully."""
        self.send_ntfy(
            title=f"SAT: Story Complete",
            message=f"{story_id}: {story_title}",
            tags="tada",
        )

    def notify_story_failed(self, story_id: str, story_title: str, reason: str):
        """Notify that a story failed after all retries."""
        self.send_ntfy(
            title=f"SAT: Story Failed",
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
