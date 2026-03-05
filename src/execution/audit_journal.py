import json
import logging
import os
import shutil
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Rotate the journal when it exceeds this size (bytes)
MAX_JOURNAL_SIZE = 10 * 1024 * 1024  # 10 MB


class AuditRecord(BaseModel):
    timestamp: str
    task_file: str
    story_id: str
    success: bool
    duration_seconds: float
    exit_code: int
    error_summary: str | None = None


class AuditJournal:
    def __init__(self, file_path: str = ".memory/audit_journal.jsonl"):
        self.journal_file_path = Path(file_path)
        os.makedirs(os.path.dirname(self.journal_file_path), exist_ok=True)
        if not self.journal_file_path.exists():
            with open(str(self.journal_file_path), "w", encoding="utf-8"):
                pass

    def _maybe_rotate(self):
        """Rotate the journal file if it exceeds MAX_JOURNAL_SIZE.

        Keeps one rotated backup (.1) and starts a fresh journal.
        """
        try:
            if not self.journal_file_path.exists():
                return
            size = self.journal_file_path.stat().st_size
            if size < MAX_JOURNAL_SIZE:
                return

            rotated = Path(str(self.journal_file_path) + ".1")
            # Remove old rotated file if it exists
            if rotated.exists():
                rotated.unlink()
            # Rename current → .1
            shutil.move(str(self.journal_file_path), str(rotated))
            # Create fresh empty journal
            with open(str(self.journal_file_path), "w", encoding="utf-8"):
                pass
            logger.info(f"Rotated audit journal ({size // 1024}KB) → {rotated.name}")
        except OSError as e:
            logger.warning(f"Audit journal rotation failed: {e}")

    def log(self, record: AuditRecord):
        self._maybe_rotate()
        with open(str(self.journal_file_path), "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())

    def query(self, success: bool | None = None, task_file: str | None = None) -> list[AuditRecord]:
        records = []
        if not self.journal_file_path.exists():
            return records
        with open(str(self.journal_file_path), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record_data = json.loads(line)
                    record = AuditRecord(**record_data)
                    if (success is None or record.success == success) and \
                       (task_file is None or record.task_file == task_file):
                        records.append(record)
                except (json.JSONDecodeError, Exception):
                    continue
        return records

    def summary(self) -> dict:
        records = self.query()
        total_count = len(records)
        if total_count == 0:
            return {"total_count": 0, "successful_count": 0, "failed_count": 0, "success_rate": 0.0, "average_duration_seconds": 0.0}

        successful_records = [r for r in records if r.success]
        success_count = len(successful_records)
        failed_count = total_count - success_count
        success_rate = (success_count / total_count) * 100.0

        total_duration = sum(r.duration_seconds for r in records)
        average_duration_seconds = total_duration / total_count

        return {
            "total_count": total_count,
            "successful_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_rate,
            "average_duration_seconds": average_duration_seconds,
        }
