import asyncio
import fcntl
import logging
import os
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_MAX_SLOTS = 2
MAX_SLOTS_LIMIT = 4


@dataclass
class SlotInfo:
    slot_id: int
    task_file: str | None = None
    started_at: float | None = None
    status: str = "idle"  # idle, active, error


class SlotManager:
    def __init__(
        self,
        max_slots: int = DEFAULT_MAX_SLOTS,
        lock_dir: str = ".memory/locks",
    ):
        self.max_slots = min(max_slots, MAX_SLOTS_LIMIT)
        self.lock_dir = lock_dir
        os.makedirs(lock_dir, exist_ok=True)
        self._slots: list[SlotInfo] = [SlotInfo(slot_id=i) for i in range(self.max_slots)]
        self._lock_fds: dict[str, object] = {}

    def get_available_slot(self) -> int | None:
        """Return the ID of an available slot, or None if all busy."""
        for slot in self._slots:
            if slot.status == "idle":
                return slot.slot_id
        return None

    def assign_task(self, slot_id: int, task_file: str):
        """Mark a slot as active with the given task."""
        slot = self._slots[slot_id]
        slot.task_file = task_file
        slot.started_at = time.time()
        slot.status = "active"
        logger.info(f"Slot {slot_id}: assigned {task_file}")

    def release_slot(self, slot_id: int):
        """Release a slot back to idle."""
        slot = self._slots[slot_id]
        logger.info(f"Slot {slot_id}: released (was {slot.task_file})")
        slot.task_file = None
        slot.started_at = None
        slot.status = "idle"

    def acquire_llm_lock(self, provider_name: str) -> bool:
        """Acquire exclusive flock for an LLM provider. Returns True if acquired."""
        lock_path = os.path.join(self.lock_dir, f"{provider_name}.lock")
        try:
            fd = open(lock_path, 'w')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fd.write(f"{os.getpid()}\n")
            fd.flush()
            self._lock_fds[provider_name] = fd
            return True
        except OSError:
            try:
                fd.close()
            except:
                pass
            return False

    def release_llm_lock(self, provider_name: str):
        """Release the flock for an LLM provider."""
        fd = self._lock_fds.pop(provider_name, None)
        if fd:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                fd.close()
            except:
                pass

    def get_status(self) -> list[dict]:
        """Return status of all slots."""
        result = []
        for slot in self._slots:
            info = {
                "slot_id": slot.slot_id,
                "status": slot.status,
                "task_file": slot.task_file,
            }
            if slot.started_at:
                info["elapsed_seconds"] = time.time() - slot.started_at
            result.append(info)
        return result

    def active_count(self) -> int:
        """Return number of active slots."""
        return sum(1 for s in self._slots if s.status == "active")

    def is_task_running(self, task_file: str) -> bool:
        """Check if a specific task is already running in any slot."""
        return any(s.task_file == task_file and s.status == "active" for s in self._slots)

    async def graceful_shutdown(self, timeout: int = 5):
        """Wait for active slots to finish, with timeout."""
        start = time.time()
        while self.active_count() > 0:
            if time.time() - start > timeout:
                logger.warning(f"Shutdown timeout: {self.active_count()} slots still active")
                break
            await asyncio.sleep(0.5)

        # Release all LLM locks
        for provider in list(self._lock_fds.keys()):
            self.release_llm_lock(provider)
