import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    task_file: str
    story_id: str
    story_title: str
    llm_provider_per_phase: Dict[str, str]
    session_id: str
    total_turns: int
    exit_code: Optional[int] = None
    duration_seconds: float
    success: bool
    phases_completed: List[str]
    error_summary: Optional[str] = None


class AuditJournal:
    def __init__(self, journal_path: Path | str = Path(".memory/audit_journal.jsonl")):
        self.journal_path = Path(journal_path)
        self._initialize_journal()

    def _initialize_journal(self):
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.journal_path.exists():
            self.journal_path.touch()

    def log_record(self, record: AuditRecord):
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def _read_all_records(self) -> List[AuditRecord]:
        records = []
        if not self.journal_path.exists():
            return records
        with open(self.journal_path, "r") as f:
            for line in f:
                try:
                    records.append(AuditRecord.model_validate_json(line))
                except Exception as e:
                    print(f"Error parsing audit record: {e} in line: {line.strip()}")
        return records

    def query(
        self,
        since: Optional[datetime] = None,
        task_file: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> List[AuditRecord]:
        all_records = self._read_all_records()
        filtered_records = []
        for record in all_records:
            if since and record.timestamp < since:
                continue
            if task_file and record.task_file != task_file:
                continue
            if success is not None and record.success != success:
                continue
            filtered_records.append(record)
        return filtered_records

    def summary(self) -> Dict:
        all_records = self._read_all_records()
        total_records = len(all_records)
        successful_records = sum(1 for r in all_records if r.success)
        failed_records = total_records - successful_records
        
        total_duration = sum(r.duration_seconds for r in all_records)
        avg_duration = total_duration / total_records if total_records > 0 else 0

        llm_provider_usage: Dict[str, Dict[str, int]] = {}
        for record in all_records:
            for phase, provider in record.llm_provider_per_phase.items():
                if provider not in llm_provider_usage:
                    llm_provider_usage[provider] = {"total": 0, "success": 0, "failure": 0}
                llm_provider_usage[provider]["total"] += 1
                if record.success:
                    llm_provider_usage[provider]["success"] += 1
                else:
                    llm_provider_usage[provider]["failure"] += 1

        return {
            "total_records": total_records,
            "successful_records": successful_records,
            "failed_records": failed_records,
            "success_rate": (successful_records / total_records) * 100 if total_records > 0 else 0.0,
            "average_duration_seconds": avg_duration,
            "llm_provider_usage": {provider: data["total"] for provider, data in llm_provider_usage.items()},
        }
