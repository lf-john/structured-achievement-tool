import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

class AuditRecord(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    task_file: str
    story_id: str
    story_title: str
    llm_provider_used_per_phase: Dict[str, str] = Field(default_factory=dict)
    session_id: str
    total_turns: int
    exit_code: Optional[int] = None
    duration_seconds: float
    success: bool
    phases_completed: List[str] = Field(default_factory=list)
    error_summary: Optional[str] = None

class AuditJournal:
    def __init__(self, journal_path: Optional[Path] = None):
        self.journal_path = Path(journal_path) if journal_path else Path(".memory/audit_journal.jsonl")
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
            if task_file and task_file not in record.task_file:
                continue
            if success is not None and record.success != success:
                continue
            filtered_records.append(record)
        return filtered_records

    def summary(self) -> Dict[str, any]:
        all_records = self._read_all_records()
        if not all_records:
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "avg_duration_seconds": 0.0,
                "llm_provider_usage": {},
                "success_rate": 0.0,
            }

        total_records = len(all_records)
        successful_executions = sum(1 for r in all_records if r.success)
        failed_executions = total_records - successful_executions
        total_duration = sum(r.duration_seconds for r in all_records)
        average_duration_seconds = total_duration / total_records if total_records > 0 else 0.0

        llm_provider_usage: Dict[str, int] = {}
        for record in all_records:
            for provider in record.llm_provider_used_per_phase.values():
                llm_provider_usage[provider] = llm_provider_usage.get(provider, 0) + 1

        success_rate = (successful_executions / total_records * 100) if total_records > 0 else 0.0

        return {
            "total_executions": total_records,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "avg_duration_seconds": average_duration_seconds,
            "success_rate": success_rate,
            "llm_provider_usage": llm_provider_usage,
        }
