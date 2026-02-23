import json
import os
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from pydantic import BaseModel


class AuditRecord(BaseModel):
    timestamp: str
    task_file: str
    story_id: str
    success: bool
    duration_seconds: float
    exit_code: int
    error_summary: Optional[str] = None


class AuditJournal:
    def __init__(self, file_path: str = ".memory/audit_journal.jsonl"):
        self.journal_file_path = Path(file_path)
        os.makedirs(os.path.dirname(self.journal_file_path), exist_ok=True)
        if not self.journal_file_path.exists():
            with open(str(self.journal_file_path), "w", encoding="utf-8") as f:
                pass

    def log(self, record: AuditRecord):
        with open(str(self.journal_file_path), "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def query(self, success: Optional[bool] = None, task_file: Optional[str] = None) -> List[AuditRecord]:
        records = []
        if not self.journal_file_path.exists():
            return records
        with open(str(self.journal_file_path), "r", encoding="utf-8") as f:
            for line in f:
                print(f"DEBUG: Reading line: {line.strip()}") # Re-enabled debug print
                try:
                    record_data = json.loads(line)
                    print(f"DEBUG: Parsed record_data: {record_data}") # Re-enabled debug print
                    record = AuditRecord(**record_data)
                    
                    # Apply filters
                    if (success is None or record.success == success) and \
                       (task_file is None or record.task_file == task_file):
                        records.append(record)
                except json.JSONDecodeError:
                    print(f"DEBUG: Malformed JSON line skipped: {line.strip()}") # Added debug print
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
