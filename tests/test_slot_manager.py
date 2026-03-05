import asyncio
import time

import pytest

from src.execution.slot_manager import DEFAULT_MAX_SLOTS, MAX_SLOTS_LIMIT, SlotManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr(tmp_path):
    """SlotManager with default slots using a temporary lock directory."""
    return SlotManager(max_slots=DEFAULT_MAX_SLOTS, lock_dir=str(tmp_path / "locks"))


@pytest.fixture
def full_mgr(tmp_path):
    """SlotManager with all slots occupied."""
    sm = SlotManager(max_slots=2, lock_dir=str(tmp_path / "locks"))
    for i in range(sm.max_slots):
        sm.assign_task(i, f"task_{i}.md")
    return sm


# ---------------------------------------------------------------------------
# get_available_slot
# ---------------------------------------------------------------------------

class TestGetAvailableSlot:
    def test_initially_all_available(self, mgr):
        """First call should return slot 0 (first idle slot)."""
        assert mgr.get_available_slot() == 0

    def test_returns_next_after_first_busy(self, mgr):
        mgr.assign_task(0, "task_a.md")
        assert mgr.get_available_slot() == 1

    def test_none_when_all_busy(self, full_mgr):
        assert full_mgr.get_available_slot() is None


# ---------------------------------------------------------------------------
# assign_task / release_slot
# ---------------------------------------------------------------------------

class TestAssignRelease:
    def test_assign_sets_fields(self, mgr):
        mgr.assign_task(0, "hello.md")
        slot = mgr._slots[0]
        assert slot.status == "active"
        assert slot.task_file == "hello.md"
        assert slot.started_at is not None

    def test_release_resets_fields(self, mgr):
        mgr.assign_task(0, "hello.md")
        mgr.release_slot(0)
        slot = mgr._slots[0]
        assert slot.status == "idle"
        assert slot.task_file is None
        assert slot.started_at is None

    def test_release_makes_slot_available_again(self, full_mgr):
        assert full_mgr.get_available_slot() is None
        full_mgr.release_slot(1)
        assert full_mgr.get_available_slot() == 1


# ---------------------------------------------------------------------------
# LLM lock acquire / release (flock-based)
# ---------------------------------------------------------------------------

class TestLLMLock:
    def test_acquire_returns_true(self, mgr):
        assert mgr.acquire_llm_lock("ollama") is True

    def test_release_after_acquire(self, mgr):
        mgr.acquire_llm_lock("ollama")
        mgr.release_llm_lock("ollama")
        assert "ollama" not in mgr._lock_fds

    def test_second_flock_same_provider_fails(self, tmp_path):
        """Two managers sharing the same lock_dir: second acquire must fail."""
        lock_dir = str(tmp_path / "shared_locks")
        sm1 = SlotManager(max_slots=1, lock_dir=lock_dir)
        sm2 = SlotManager(max_slots=1, lock_dir=lock_dir)

        assert sm1.acquire_llm_lock("ollama") is True
        assert sm2.acquire_llm_lock("ollama") is False

        # Cleanup
        sm1.release_llm_lock("ollama")

    def test_lock_reacquirable_after_release(self, tmp_path):
        lock_dir = str(tmp_path / "locks")
        sm1 = SlotManager(max_slots=1, lock_dir=lock_dir)
        sm2 = SlotManager(max_slots=1, lock_dir=lock_dir)

        sm1.acquire_llm_lock("ollama")
        sm1.release_llm_lock("ollama")
        assert sm2.acquire_llm_lock("ollama") is True
        sm2.release_llm_lock("ollama")

    def test_different_providers_independent(self, mgr):
        assert mgr.acquire_llm_lock("ollama") is True
        assert mgr.acquire_llm_lock("openai") is True
        mgr.release_llm_lock("ollama")
        mgr.release_llm_lock("openai")


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_idle_status(self, mgr):
        statuses = mgr.get_status()
        assert len(statuses) == mgr.max_slots
        for s in statuses:
            assert s["status"] == "idle"
            assert s["task_file"] is None
            assert "elapsed_seconds" not in s

    def test_active_status_includes_elapsed(self, mgr):
        mgr.assign_task(0, "work.md")
        # Small sleep so elapsed > 0
        time.sleep(0.05)
        statuses = mgr.get_status()
        active = statuses[0]
        assert active["status"] == "active"
        assert active["task_file"] == "work.md"
        assert active["elapsed_seconds"] > 0


# ---------------------------------------------------------------------------
# active_count
# ---------------------------------------------------------------------------

class TestActiveCount:
    def test_zero_initially(self, mgr):
        assert mgr.active_count() == 0

    def test_increments_on_assign(self, mgr):
        mgr.assign_task(0, "a.md")
        assert mgr.active_count() == 1
        mgr.assign_task(1, "b.md")
        assert mgr.active_count() == 2

    def test_decrements_on_release(self, full_mgr):
        full_mgr.release_slot(0)
        assert full_mgr.active_count() == 1


# ---------------------------------------------------------------------------
# is_task_running
# ---------------------------------------------------------------------------

class TestIsTaskRunning:
    def test_false_when_idle(self, mgr):
        assert mgr.is_task_running("x.md") is False

    def test_true_when_assigned(self, mgr):
        mgr.assign_task(0, "x.md")
        assert mgr.is_task_running("x.md") is True

    def test_false_after_release(self, mgr):
        mgr.assign_task(0, "x.md")
        mgr.release_slot(0)
        assert mgr.is_task_running("x.md") is False

    def test_different_task_not_running(self, mgr):
        mgr.assign_task(0, "x.md")
        assert mgr.is_task_running("y.md") is False


# ---------------------------------------------------------------------------
# Max slots capped at MAX_SLOTS_LIMIT
# ---------------------------------------------------------------------------

class TestMaxSlotsCap:
    def test_capped_at_limit(self, tmp_path):
        sm = SlotManager(max_slots=100, lock_dir=str(tmp_path / "locks"))
        assert sm.max_slots == MAX_SLOTS_LIMIT

    def test_under_limit_unchanged(self, tmp_path):
        sm = SlotManager(max_slots=3, lock_dir=str(tmp_path / "locks"))
        assert sm.max_slots == 3

    def test_exact_limit_unchanged(self, tmp_path):
        sm = SlotManager(max_slots=MAX_SLOTS_LIMIT, lock_dir=str(tmp_path / "locks"))
        assert sm.max_slots == MAX_SLOTS_LIMIT


# ---------------------------------------------------------------------------
# graceful_shutdown
# ---------------------------------------------------------------------------

class TestGracefulShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_with_no_active_slots(self, mgr):
        """Shutdown completes immediately when nothing is active."""
        await mgr.graceful_shutdown(timeout=1)
        assert mgr.active_count() == 0

    @pytest.mark.asyncio
    async def test_shutdown_releases_llm_locks(self, mgr):
        mgr.acquire_llm_lock("ollama")
        mgr.acquire_llm_lock("openai")
        assert len(mgr._lock_fds) == 2

        await mgr.graceful_shutdown(timeout=1)
        assert len(mgr._lock_fds) == 0

    @pytest.mark.asyncio
    async def test_shutdown_times_out_with_active_slots(self, mgr):
        """Slots still active after timeout -- shutdown should not hang."""
        mgr.assign_task(0, "stuck.md")
        start = time.time()
        await mgr.graceful_shutdown(timeout=1)
        elapsed = time.time() - start
        # Should have waited roughly 1 second, not longer
        assert elapsed < 3
        # Slot is still active (nothing external released it)
        assert mgr.active_count() == 1

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_slot_release(self, mgr):
        """If a slot is released during shutdown, it exits early."""
        mgr.assign_task(0, "finishing.md")

        async def release_later():
            await asyncio.sleep(0.3)
            mgr.release_slot(0)

        task = asyncio.create_task(release_later())
        start = time.time()
        await mgr.graceful_shutdown(timeout=5)
        elapsed = time.time() - start

        await task
        assert mgr.active_count() == 0
        # Should finish well before the 5-second timeout
        assert elapsed < 2
