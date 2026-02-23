import json
import os
from datetime import datetime
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
    def __init__(self, journal_path: str = ".memory/audit_journal.jsonl"):
        self.journal_path = journal_path
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)
        if not os.path.exists(self.journal_path):
            with open(self.journal_path, "w") as f:
                pass  # Create an empty file if it doesn't exist

    def log_record(self, record: AuditRecord):
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def query(
        self,
        since: Optional[datetime] = None,
        task_file: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> List[AuditRecord]:
        records = []
        if not os.path.exists(self.journal_path):
            return records
        with open(self.journal_path, "r") as f:
            for line in f:
                try:
                    record_dict = json.loads(line)
                    record = AuditRecord(**record_dict)
                    
                    if since and record.timestamp < since:
                        continue
                    if task_file and record.task_file != task_file:
                        continue
                    if success is not None and record.success != success:
                        continue
                    records.append(record)
                except json.JSONDecodeError:
                    # Log error or handle corrupted line
                    continue
        return records

    def summary(self) -> Dict[str, any]:
        records = self.query()  # Use query to get all records
        total_records = len(records)
        successful_records = sum(1 for r in records if r.success)
        failed_records = total_records - successful_records
        
        total_duration = sum(r.duration_seconds for r in records)
        
        llm_provider_usage = {}
        for record in records:
            for provider in record.llm_provider_used_per_phase.values():
                llm_provider_usage[provider] = llm_provider_usage.get(provider, 0) + 1
        
        return {
            "total_executions": total_records,
            "successful_executions": successful_records,
            "failed_executions": failed_records,
            "avg_duration_seconds": total_duration / total_records if total_records > 0 else 0,
            "success_rate": (successful_records / total_records) * 100 if total_records > 0 else 0.0,
            "llm_provider_usage": llm_provider_usage,
        }
