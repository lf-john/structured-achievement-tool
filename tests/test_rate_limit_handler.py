"""
Tests for RateLimitHandler — rate limit retry queue (Phase 2 item 2.8).

Uses tmp_path for state file isolation. Mocks time.time() and random.uniform()
for deterministic tests.
"""

import json
import os
import pytest
from unittest.mock import patch

from src.execution.rate_limit_handler import (
    RateLimitHandler,
    RetryEntry,
    INITIAL_BACKOFF,
    MAX_BACKOFF,
    BACKOFF_MULTIPLIER,
    JITTER_FACTOR,
)


@pytest.fixture
def state_file(tmp_path):
    """Return a path to a state file in a temp directory."""
    return str(tmp_path / "rate_limit_state.json")


@pytest.fixture
def handler(state_file):
    """Create a fresh RateLimitHandler with a temp state file."""
    return RateLimitHandler(state_file=state_file)


class TestQueueRetry:
    """Test queue_retry() — adding tasks to the retry queue."""

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_queue_new_task(self, mock_time, mock_random, handler):
        """First queue of a task creates attempt 1 with correct backoff."""
        entry = handler.queue_retry("task_001.md", "story_A")

        assert entry.task_file == "task_001.md"
        assert entry.story_id == "story_A"
        assert entry.attempt == 1
        assert entry.reason == "rate_limit"
        # Backoff: 30 * 2^0 * (1 + 0.0) = 30
        assert entry.next_retry_at == 1000.0 + 30.0

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_queue_same_task_increments_attempt(self, mock_time, mock_random, handler):
        """Queuing the same task again increments the attempt counter."""
        handler.queue_retry("task_001.md", "story_A")
        entry = handler.queue_retry("task_001.md", "story_A")

        assert entry.attempt == 2
        # Backoff: 30 * 2^1 * (1 + 0.0) = 60
        assert entry.next_retry_at == 1000.0 + 60.0
        # Only one entry in queue
        assert len(handler._queue) == 1

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_queue_with_token_exhaustion_reason(self, mock_time, mock_random, handler):
        """Reason field is stored correctly."""
        entry = handler.queue_retry("task_001.md", "story_A", reason="token_exhaustion")
        assert entry.reason == "token_exhaustion"


class TestGetReadyTasks:
    """Test get_ready_tasks() — retrieving tasks past their retry time."""

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_no_ready_tasks_before_backoff(self, mock_random, handler):
        """Tasks are not ready immediately after queuing."""
        with patch("src.execution.rate_limit_handler.time.time", return_value=1000.0):
            handler.queue_retry("task_001.md", "story_A")

        with patch("src.execution.rate_limit_handler.time.time", return_value=1010.0):
            ready = handler.get_ready_tasks()
            assert len(ready) == 0

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_task_ready_after_backoff(self, mock_random, handler):
        """Task becomes ready after the backoff period passes."""
        with patch("src.execution.rate_limit_handler.time.time", return_value=1000.0):
            handler.queue_retry("task_001.md", "story_A")

        # 30s backoff, check at 1031
        with patch("src.execution.rate_limit_handler.time.time", return_value=1031.0):
            ready = handler.get_ready_tasks()
            assert len(ready) == 1
            assert ready[0].task_file == "task_001.md"

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_multiple_tasks_mixed_readiness(self, mock_random, handler):
        """Only tasks past their retry time are returned."""
        with patch("src.execution.rate_limit_handler.time.time", return_value=1000.0):
            handler.queue_retry("task_001.md", "story_A")  # retry at 1030

        with patch("src.execution.rate_limit_handler.time.time", return_value=1020.0):
            handler.queue_retry("task_002.md", "story_B")  # retry at 1050

        with patch("src.execution.rate_limit_handler.time.time", return_value=1035.0):
            ready = handler.get_ready_tasks()
            assert len(ready) == 1
            assert ready[0].task_file == "task_001.md"

        with patch("src.execution.rate_limit_handler.time.time", return_value=1051.0):
            ready = handler.get_ready_tasks()
            assert len(ready) == 2


class TestRemoveFromQueue:
    """Test remove_from_queue() — removing tasks after successful processing."""

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_remove_existing_task(self, mock_time, mock_random, handler):
        """Removing a queued task leaves the queue empty."""
        handler.queue_retry("task_001.md", "story_A")
        handler.remove_from_queue("task_001.md")
        assert len(handler._queue) == 0

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_remove_nonexistent_task_is_noop(self, mock_time, mock_random, handler):
        """Removing a task not in the queue does nothing."""
        handler.queue_retry("task_001.md", "story_A")
        handler.remove_from_queue("task_999.md")
        assert len(handler._queue) == 1

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_remove_only_target_task(self, mock_time, mock_random, handler):
        """Removing one task leaves others intact."""
        handler.queue_retry("task_001.md", "story_A")
        handler.queue_retry("task_002.md", "story_B")
        handler.remove_from_queue("task_001.md")
        assert len(handler._queue) == 1
        assert handler._queue[0].task_file == "task_002.md"


class TestTokenExhaustion:
    """Test token exhaustion flag management."""

    def test_not_exhausted_by_default(self, handler):
        assert handler.is_token_exhausted() is False

    def test_mark_exhausted(self, handler):
        handler.mark_token_exhausted()
        assert handler.is_token_exhausted() is True

    def test_clear_exhaustion(self, handler):
        handler.mark_token_exhausted()
        handler.clear_token_exhaustion()
        assert handler.is_token_exhausted() is False


class TestCalculateBackoff:
    """Test calculate_backoff() — exponential backoff with jitter."""

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_attempt_1_base_backoff(self, mock_random, handler):
        """Attempt 1: 30 * 2^0 = 30s."""
        assert handler.calculate_backoff(1) == 30.0

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_attempt_2_doubles(self, mock_random, handler):
        """Attempt 2: 30 * 2^1 = 60s."""
        assert handler.calculate_backoff(2) == 60.0

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_attempt_3_quadruples(self, mock_random, handler):
        """Attempt 3: 30 * 2^2 = 120s."""
        assert handler.calculate_backoff(3) == 120.0

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_caps_at_max_backoff(self, mock_random, handler):
        """High attempts cap at MAX_BACKOFF (900s)."""
        # 30 * 2^9 = 15360 > 900, so capped at 900
        assert handler.calculate_backoff(10) == 900.0

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_backoff_progression_doubles(self, mock_random, handler):
        """Each attempt doubles the backoff until the cap."""
        b1 = handler.calculate_backoff(1)
        b2 = handler.calculate_backoff(2)
        b3 = handler.calculate_backoff(3)
        assert b2 == b1 * BACKOFF_MULTIPLIER
        assert b3 == b2 * BACKOFF_MULTIPLIER

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=JITTER_FACTOR)
    def test_positive_jitter(self, mock_random, handler):
        """Positive jitter increases backoff by JITTER_FACTOR."""
        result = handler.calculate_backoff(1)
        expected = INITIAL_BACKOFF * (1 + JITTER_FACTOR)
        assert result == pytest.approx(expected)

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=-JITTER_FACTOR)
    def test_negative_jitter(self, mock_random, handler):
        """Negative jitter decreases backoff by JITTER_FACTOR."""
        result = handler.calculate_backoff(1)
        expected = INITIAL_BACKOFF * (1 - JITTER_FACTOR)
        assert result == pytest.approx(expected)

    def test_jitter_within_bounds(self, handler):
        """Backoff with real jitter stays within expected bounds."""
        for attempt in range(1, 8):
            base = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** (attempt - 1)), MAX_BACKOFF)
            low = base * (1 - JITTER_FACTOR)
            high = base * (1 + JITTER_FACTOR)
            for _ in range(50):
                result = handler.calculate_backoff(attempt)
                assert low <= result <= high, (
                    f"attempt={attempt}, result={result}, expected [{low}, {high}]"
                )


class TestStatePersistence:
    """Test _save_state() / _load_state() — state survives restart."""

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_save_and_reload_queue(self, mock_time, mock_random, state_file):
        """Queue entries survive a handler restart."""
        h1 = RateLimitHandler(state_file=state_file)
        h1.queue_retry("task_001.md", "story_A")
        h1.queue_retry("task_002.md", "story_B")

        # Create a new handler reading the same state file
        h2 = RateLimitHandler(state_file=state_file)
        assert len(h2._queue) == 2
        assert h2._queue[0].task_file == "task_001.md"
        assert h2._queue[1].task_file == "task_002.md"
        assert h2._queue[0].attempt == 1
        assert h2._queue[0].next_retry_at == 1030.0

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_save_and_reload_token_exhaustion(self, mock_time, mock_random, state_file):
        """Token exhaustion flag survives a handler restart."""
        h1 = RateLimitHandler(state_file=state_file)
        h1.mark_token_exhausted()

        h2 = RateLimitHandler(state_file=state_file)
        assert h2.is_token_exhausted() is True

    def test_load_missing_file(self, tmp_path):
        """Loading from a nonexistent state file starts with empty state."""
        missing = str(tmp_path / "nonexistent" / "state.json")
        h = RateLimitHandler(state_file=missing)
        assert len(h._queue) == 0
        assert h.is_token_exhausted() is False

    def test_load_corrupt_file(self, tmp_path):
        """Loading from a corrupt state file starts with empty state."""
        bad_file = str(tmp_path / "bad_state.json")
        with open(bad_file, "w") as f:
            f.write("not valid json{{{")

        h = RateLimitHandler(state_file=bad_file)
        assert len(h._queue) == 0
        assert h.is_token_exhausted() is False

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_state_file_format(self, mock_time, mock_random, state_file):
        """State file is valid JSON with expected structure."""
        h = RateLimitHandler(state_file=state_file)
        h.queue_retry("task_001.md", "story_A")
        h.mark_token_exhausted()

        with open(state_file, "r") as f:
            data = json.load(f)

        assert data["token_exhausted"] is True
        assert len(data["queue"]) == 1
        assert data["queue"][0]["task_file"] == "task_001.md"
        assert data["queue"][0]["story_id"] == "story_A"
        assert data["queue"][0]["attempt"] == 1

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    @patch("src.execution.rate_limit_handler.time.time", return_value=1000.0)
    def test_remove_persists(self, mock_time, mock_random, state_file):
        """Removal is persisted to disk."""
        h1 = RateLimitHandler(state_file=state_file)
        h1.queue_retry("task_001.md", "story_A")
        h1.queue_retry("task_002.md", "story_B")
        h1.remove_from_queue("task_001.md")

        h2 = RateLimitHandler(state_file=state_file)
        assert len(h2._queue) == 1
        assert h2._queue[0].task_file == "task_002.md"


class TestQueueStatus:
    """Test get_queue_status() — status reporting."""

    def test_empty_queue_status(self, handler):
        """Empty queue returns zero size and no entries."""
        status = handler.get_queue_status()
        assert status["queue_size"] == 0
        assert status["token_exhausted"] is False
        assert status["entries"] == []

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_queue_status_with_entries(self, mock_random, handler):
        """Status includes per-entry details."""
        with patch("src.execution.rate_limit_handler.time.time", return_value=1000.0):
            handler.queue_retry("task_001.md", "story_A")

        with patch("src.execution.rate_limit_handler.time.time", return_value=1010.0):
            status = handler.get_queue_status()

        assert status["queue_size"] == 1
        entry = status["entries"][0]
        assert entry["task_file"] == "task_001.md"
        assert entry["story_id"] == "story_A"
        assert entry["attempt"] == 1
        assert entry["reason"] == "rate_limit"
        assert entry["seconds_until_retry"] == pytest.approx(20.0, abs=0.1)
        assert entry["ready"] is False

    @patch("src.execution.rate_limit_handler.random.uniform", return_value=0.0)
    def test_queue_status_ready_entry(self, mock_random, handler):
        """Ready entries show ready=True and seconds_until_retry=0."""
        with patch("src.execution.rate_limit_handler.time.time", return_value=1000.0):
            handler.queue_retry("task_001.md", "story_A")

        with patch("src.execution.rate_limit_handler.time.time", return_value=1031.0):
            status = handler.get_queue_status()

        entry = status["entries"][0]
        assert entry["ready"] is True
        assert entry["seconds_until_retry"] == 0

    def test_queue_status_reflects_token_exhaustion(self, handler):
        """Token exhaustion flag is included in status."""
        handler.mark_token_exhausted()
        status = handler.get_queue_status()
        assert status["token_exhausted"] is True
