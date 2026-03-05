"""
Centralized logging configuration — Hierarchical Correlation IDs + Structured Event Logging.

Enhancement #12: Correlation IDs via contextvars — set once per task, automatically
included in all log output from that execution context.

Hierarchical format: sat-{task_id}-{story_id}-{phase}
- Task level: sat-{task_id}            (set at process_task_file)
- Story level: sat-{task_id}-{story_id} (set at story_executor)
- Phase level: sat-{task_id}-{story_id}-{phase} (set at phase_node)

Enhancement #13: Structured JSONL event stream — machine-parseable events alongside
human-readable logs. Events written to .memory/events.jsonl.
"""

import json
import logging
import os
import uuid
from contextvars import ContextVar
from datetime import datetime

# --- Hierarchical Correlation ID (Enhancement #12) ---

# ContextVars hold each level independently. The full ID is assembled from all set levels.
_task_id_var: ContextVar[str] = ContextVar("corr_task_id", default="")
_story_id_var: ContextVar[str] = ContextVar("corr_story_id", default="")
_phase_var: ContextVar[str] = ContextVar("corr_phase", default="")
# Legacy flat var for backward compatibility
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def set_correlation_id(corr_id: str | None = None, task_id: str | None = None) -> str:
    """Set the task-level correlation ID for the current execution context.

    Call this at the start of process_task_file() or any top-level entry point.
    Returns the ID (generated if not provided).
    """
    if corr_id:
        # Legacy: set flat ID directly
        correlation_id_var.set(corr_id)
        return corr_id

    # Hierarchical: generate from task_id
    safe_task = (task_id or uuid.uuid4().hex[:8])[:20].replace("/", "-").replace(" ", "-")
    cid = f"sat-{safe_task}"
    _task_id_var.set(safe_task)
    _story_id_var.set("")
    _phase_var.set("")
    correlation_id_var.set(cid)
    return cid


def set_story_context(story_id: str):
    """Set story-level context. Call at start of story execution."""
    safe_story = story_id[:20].replace("/", "-").replace(" ", "-")
    _story_id_var.set(safe_story)
    _phase_var.set("")
    # Update assembled ID
    task = _task_id_var.get()
    correlation_id_var.set(f"sat-{task}-{safe_story}" if task else f"sat-{safe_story}")


def set_phase_context(phase: str):
    """Set phase-level context. Call at start of each phase."""
    safe_phase = phase[:15].lower()
    _phase_var.set(safe_phase)
    # Update assembled ID
    task = _task_id_var.get()
    story = _story_id_var.get()
    parts = ["sat"]
    if task:
        parts.append(task)
    if story:
        parts.append(story)
    parts.append(safe_phase)
    correlation_id_var.set("-".join(parts))


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return correlation_id_var.get()


class CorrelationFilter(logging.Filter):
    """Logging filter that injects correlation_id into every log record."""

    def filter(self, record):
        record.correlation_id = correlation_id_var.get() or "-"
        return True


def configure_logging(level: int = logging.INFO):
    """Configure root logger with correlation ID support.

    Human-readable format for journalctl, with correlation ID prefix.
    """
    root = logging.getLogger()
    if root.handlers:
        # Already configured — just add filter
        for handler in root.handlers:
            handler.addFilter(CorrelationFilter())
        return

    handler = logging.StreamHandler()
    handler.addFilter(CorrelationFilter())
    formatter = logging.Formatter(
        "%(asctime)s [%(correlation_id)s] %(levelname)s %(name)s — %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level)


# --- Structured JSONL Event Stream (Enhancement #13) ---

# Default events file location
_EVENTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".memory",
)
_EVENTS_FILE = os.path.join(_EVENTS_DIR, "events.jsonl")


def log_event(
    event_type: str,
    component: str = "",
    data: dict | None = None,
    events_file: str | None = None,
):
    """Write a structured event to the JSONL event stream.

    Args:
        event_type: Event category (e.g., "llm_invocation", "story_complete",
                    "circuit_breaker_open", "provider_failure")
        component: Source component (e.g., "cli_runner", "routing_engine")
        data: Arbitrary event-specific data
    """
    target = events_file or _EVENTS_FILE
    event = {
        "ts": datetime.now().isoformat(),
        "correlation_id": correlation_id_var.get() or "-",
        "event_type": event_type,
        "component": component,
    }
    if data:
        event["data"] = data

    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
    except Exception:
        pass  # Best-effort — never fail the main operation
