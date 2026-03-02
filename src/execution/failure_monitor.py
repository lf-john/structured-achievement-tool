"""
Layer 1 failure detection and debug story creation.

Detects task failures (non-zero exit codes, error patterns, timeouts)
and creates debug story files that trigger the debug workflow.

Part of Phase 2 (item 2.4): Enhanced Monitor.
"""

import os
import re
import time
import json
import shutil
import logging
import subprocess
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default failure patterns (regex)
DEFAULT_FAILURE_PATTERNS = [
    r"(?i)error:",
    r"(?i)traceback",
    r"(?i)exception",
    r"exit code[:\s]+[1-9]",
    r"(?i)failed",
    r"(?i)timeout",
    r"(?i)SIGTERM|SIGKILL",
]

# Limits for content included in debug stories
MAX_STDERR_LINES = 100
MAX_STDOUT_LINES = 80
DEFAULT_LOG_TAIL_LINES = 50
from src.core.paths import SAT_LOG, SAT_TASKS_DIR

DEFAULT_LOG_FILE = str(SAT_LOG)


@dataclass
class FailureContext:
    """Context captured when a task failure is detected."""

    task_file: str
    task_name: str
    exit_code: int
    stderr: str
    stdout: str
    log_tail: str
    timestamp: float = field(default_factory=time.time)


class FailureMonitor:
    """Monitors task execution for failures and creates debug story files.

    When a failure is detected, a markdown debug story file is written to
    the output directory. The story ends with ``<Pending>`` so the SAT
    daemon picks it up for the debug workflow.

    Rate limiting prevents flooding: at most one debug story per task
    per ``rate_limit_seconds`` (default 10 minutes).
    """

    def __init__(
        self,
        output_dir: str = str(SAT_TASKS_DIR / "debug"),
        rate_limit_seconds: int = 600,  # 10 minutes
        patterns: Optional[list[str]] = None,
    ):
        self.output_dir = output_dir
        self.rate_limit_seconds = rate_limit_seconds
        self.patterns = [
            re.compile(p) for p in (patterns or DEFAULT_FAILURE_PATTERNS)
        ]
        self._last_debug_story: dict[str, float] = {}  # task_name -> timestamp

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_failure(self, exit_code: int, stdout: str, stderr: str) -> bool:
        """Return True if exit code or output patterns indicate a failure."""
        if exit_code != 0:
            return True
        combined = stdout + stderr
        return any(p.search(combined) for p in self.patterns)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def is_rate_limited(self, task_name: str) -> bool:
        """Return True if a debug story was created for *task_name* recently."""
        last = self._last_debug_story.get(task_name, 0)
        return (time.time() - last) < self.rate_limit_seconds

    # ------------------------------------------------------------------
    # Debug story creation
    # ------------------------------------------------------------------

    def create_debug_story(self, context: FailureContext) -> Optional[str]:
        """Create a debug story file from *context*.

        Returns the file path on success, or ``None`` if rate-limited or if
        the failing task is itself a debug story (prevents recursive debug
        story creation).
        """
        # Guard against debug stories creating debug stories (Failure State 9)
        if "debug" in context.task_name.lower():
            logger.warning(
                "Skipping debug story creation for '%s' — task is itself a debug story",
                context.task_name,
            )
            return None

        if self.is_rate_limited(context.task_name):
            logger.info(
                "Rate limited: skipping debug story for %s", context.task_name
            )
            return None

        os.makedirs(self.output_dir, exist_ok=True)

        timestamp_str = time.strftime(
            "%Y%m%d_%H%M%S", time.localtime(context.timestamp)
        )
        filename = f"debug_{context.task_name}_{timestamp_str}.md"
        filepath = os.path.join(self.output_dir, filename)

        content = self._build_debug_content(context)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        self._last_debug_story[context.task_name] = time.time()
        logger.info("Created debug story: %s", filepath)
        return filepath

    # ------------------------------------------------------------------
    # Content builders
    # ------------------------------------------------------------------

    def _build_debug_content(self, ctx: FailureContext) -> str:
        """Build markdown content for a debug story."""
        stderr_truncated = _truncate(ctx.stderr, MAX_STDERR_LINES)
        stdout_truncated = _truncate(ctx.stdout, MAX_STDOUT_LINES)
        env_context = self.capture_env_context()
        ts_human = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(ctx.timestamp)
        )

        sections = [
            f"# Debug: {ctx.task_name}",
            "",
            f"**Auto-generated** by FailureMonitor at {ts_human}",
            "",
            "## Failure Summary",
            "",
            f"- **Task file:** `{ctx.task_file}`",
            f"- **Exit code:** {ctx.exit_code}",
            f"- **Timestamp:** {ts_human}",
            "",
            "## Stderr",
            "",
            "```",
            stderr_truncated if stderr_truncated else "(empty)",
            "```",
            "",
            "## Stdout",
            "",
            "```",
            stdout_truncated if stdout_truncated else "(empty)",
            "```",
            "",
            "## Log Tail",
            "",
            "```",
            ctx.log_tail if ctx.log_tail else "(no log data)",
            "```",
            "",
            "## Environment",
            "",
            "```",
            env_context,
            "```",
            "",
            "## Instructions",
            "",
            "Investigate the failure above. Identify the root cause and propose a fix.",
            "",
            "<Pending>",
            "",
        ]
        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Context capture helpers
    # ------------------------------------------------------------------

    def capture_log_tail(
        self, log_file: Optional[str] = None, lines: int = DEFAULT_LOG_TAIL_LINES
    ) -> str:
        """Read the last *lines* lines from *log_file*.

        Returns the tail content, or an informative message on failure.
        """
        path = log_file or DEFAULT_LOG_FILE
        try:
            if not os.path.isfile(path):
                return f"(log file not found: {path})"
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            tail = all_lines[-lines:]
            return "".join(tail).rstrip("\n")
        except Exception as exc:
            logger.warning("Failed to read log tail from %s: %s", path, exc)
            return f"(error reading log: {exc})"

    def capture_env_context(self) -> str:
        """Capture a snapshot of the environment: disk, memory, services."""
        parts: list[str] = []

        # Disk usage
        try:
            total, used, free = shutil.disk_usage("/")
            gb = 1 << 30
            parts.append(
                f"Disk: {used / gb:.1f}G used / {total / gb:.1f}G total "
                f"({free / gb:.1f}G free)"
            )
        except Exception:
            parts.append("Disk: (unavailable)")

        # Memory (from /proc/meminfo)
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()
            mem_total = _parse_meminfo(meminfo, "MemTotal")
            mem_avail = _parse_meminfo(meminfo, "MemAvailable")
            if mem_total and mem_avail:
                parts.append(
                    f"Memory: {mem_avail // 1024}M available / "
                    f"{mem_total // 1024}M total"
                )
        except Exception:
            parts.append("Memory: (unavailable)")

        # Key services
        for svc in ("sat.service", "sat-monitor.service", "ollama.service"):
            try:
                res = subprocess.run(
                    ["systemctl", "--user", "is-active", svc],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                status = res.stdout.strip() or "unknown"
            except Exception:
                status = "check-failed"
            parts.append(f"Service {svc}: {status}")

        return "\n".join(parts)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _truncate(text: str, max_lines: int) -> str:
    """Truncate *text* to at most *max_lines* lines."""
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text.rstrip("\n")
    kept = lines[:max_lines]
    omitted = len(lines) - max_lines
    kept.append(f"... ({omitted} more lines omitted)")
    return "\n".join(kept)


def _parse_meminfo(meminfo: str, key: str) -> Optional[int]:
    """Extract a kB value from /proc/meminfo content."""
    for line in meminfo.splitlines():
        if line.startswith(key + ":"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    return None
    return None
