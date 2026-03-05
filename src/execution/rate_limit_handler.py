"""
Rate Limit Handler — Retry queue with exponential backoff (Phase 2 item 2.8).

Builds on top of existing rate limit detection in:
- src/llm/cli_runner.py (RATE_LIMIT_PATTERN regex for 429 errors)
- src/llm/routing_engine.py (mark_rate_limited / _is_rate_limited with 120s cooldown)
- src/agents/failure_classifier.py (FailureType.RATE_LIMIT with 60s retry delay)

This module provides:
- Retry queue for rate-limited tasks
- Exponential backoff with jitter (30s initial, max 15 min)
- Token exhaustion detection and notification
- Persistent state (survives daemon restart)
"""

import json
import logging
import os
import random
import time
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)

INITIAL_BACKOFF = 30  # seconds
MAX_BACKOFF = 900  # 15 minutes
BACKOFF_MULTIPLIER = 2
JITTER_FACTOR = 0.25  # +/-25% jitter


@dataclass
class RetryEntry:
    task_file: str
    story_id: str
    attempt: int
    next_retry_at: float  # timestamp
    reason: str  # "rate_limit" or "token_exhaustion"
    created_at: float = field(default_factory=time.time)


class RateLimitHandler:
    """Manages a persistent retry queue for rate-limited tasks.

    Tasks that hit rate limits are queued with exponential backoff.
    Token exhaustion pauses all processing until cleared.
    State is persisted to disk so the queue survives daemon restarts.
    """

    def __init__(self, state_file: str = ".memory/rate_limit_state.json"):
        self.state_file = state_file
        self._queue: list[RetryEntry] = []
        self._token_exhausted = False
        self._load_state()

    def queue_retry(self, task_file: str, story_id: str, reason: str = "rate_limit") -> RetryEntry:
        """Add a task to the retry queue with exponential backoff.

        If the task is already queued, increment its attempt counter and
        recalculate the backoff. Otherwise, create a new entry at attempt 1.

        Args:
            task_file: Path to the task markdown file.
            story_id: Identifier of the story within the task.
            reason: Why the task is being retried ("rate_limit" or "token_exhaustion").

        Returns:
            The RetryEntry that was created or updated.
        """
        # Check if task is already in queue
        existing = self._find_entry(task_file)
        if existing is not None:
            existing.attempt += 1
            existing.reason = reason
            existing.next_retry_at = time.time() + self.calculate_backoff(existing.attempt)
            logger.info(
                f"Rate limit retry queued: {task_file} attempt {existing.attempt}, "
                f"next retry at +{existing.next_retry_at - time.time():.0f}s"
            )
            self._save_state()
            return existing

        attempt = 1
        backoff = self.calculate_backoff(attempt)
        entry = RetryEntry(
            task_file=task_file,
            story_id=story_id,
            attempt=attempt,
            next_retry_at=time.time() + backoff,
            reason=reason,
        )
        self._queue.append(entry)
        logger.info(
            f"Rate limit retry queued: {task_file} attempt {attempt}, "
            f"next retry at +{backoff:.0f}s"
        )
        self._save_state()
        return entry

    def get_ready_tasks(self) -> list[RetryEntry]:
        """Return tasks whose retry time has passed.

        Does not remove tasks from the queue; caller should call
        remove_from_queue() after successful processing.
        """
        now = time.time()
        return [entry for entry in self._queue if entry.next_retry_at <= now]

    def remove_from_queue(self, task_file: str):
        """Remove a task from the retry queue (after successful processing).

        Args:
            task_file: Path to the task file to remove.
        """
        before = len(self._queue)
        self._queue = [e for e in self._queue if e.task_file != task_file]
        if len(self._queue) < before:
            logger.info(f"Removed {task_file} from rate limit retry queue")
            self._save_state()

    def mark_token_exhausted(self):
        """Mark token budget as exhausted. Pause all processing."""
        self._token_exhausted = True
        logger.warning("Token exhaustion detected — all processing paused")
        self._save_state()

    def clear_token_exhaustion(self):
        """Resume processing after token exhaustion resolved."""
        self._token_exhausted = False
        logger.info("Token exhaustion cleared — processing resumed")
        self._save_state()

    def is_token_exhausted(self) -> bool:
        """Check if processing is paused due to token exhaustion."""
        return self._token_exhausted

    def calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter.

        Formula: min(INITIAL_BACKOFF * BACKOFF_MULTIPLIER^(attempt-1), MAX_BACKOFF)
                 * (1 + random.uniform(-JITTER_FACTOR, JITTER_FACTOR))

        Args:
            attempt: The attempt number (1-based).

        Returns:
            Backoff duration in seconds.
        """
        base = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** (attempt - 1)), MAX_BACKOFF)
        jitter = 1 + random.uniform(-JITTER_FACTOR, JITTER_FACTOR)
        return base * jitter

    def get_queue_status(self) -> dict:
        """Return current queue state for status reporting.

        Returns:
            Dict with queue_size, token_exhausted flag, and per-entry details.
        """
        now = time.time()
        entries = []
        for entry in self._queue:
            entries.append({
                "task_file": entry.task_file,
                "story_id": entry.story_id,
                "attempt": entry.attempt,
                "reason": entry.reason,
                "seconds_until_retry": max(0, entry.next_retry_at - now),
                "ready": entry.next_retry_at <= now,
            })
        return {
            "queue_size": len(self._queue),
            "token_exhausted": self._token_exhausted,
            "entries": entries,
        }

    # Aliases for backwards compatibility / test expectations
    def enqueue(self, task_file: str, story_id: str, reason: str = "rate_limit") -> RetryEntry:
        return self.queue_retry(task_file=task_file, story_id=story_id, reason=reason)

    def get_ready(self) -> list:
        return self.get_ready_tasks()

    @property
    def queue(self) -> list:
        return self._queue

    def _find_entry(self, task_file: str) -> RetryEntry | None:
        """Find an existing queue entry by task file path."""
        for entry in self._queue:
            if entry.task_file == task_file:
                return entry
        return None

    def _load_state(self):
        """Load retry queue from disk.

        Gracefully handles missing or corrupt state files.
        """
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file) as f:
                data = json.load(f)
            self._token_exhausted = data.get("token_exhausted", False)
            self._queue = [
                RetryEntry(**entry) for entry in data.get("queue", [])
            ]
            logger.debug(f"Loaded rate limit state: {len(self._queue)} entries")
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning(f"Failed to load rate limit state from {self.state_file}: {e}")
            self._queue = []
            self._token_exhausted = False

    def _save_state(self):
        """Persist retry queue to disk.

        Creates parent directories if they don't exist.
        """
        state_dir = os.path.dirname(self.state_file)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
        data = {
            "token_exhausted": self._token_exhausted,
            "queue": [asdict(entry) for entry in self._queue],
        }
        try:
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save rate limit state to {self.state_file}: {e}")
