import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ValidationError, field_validator


class AuditRecord(BaseModel):
    timestamp: datetime
    task_file: str
    story_id: str
    story_title: str
    llm_provider_used_per_phase: Dict[str, str]
    session_id: str
    total_turns: int
    exit_code: int
    duration_seconds: float
    success: bool
    phases_completed: List[str]
    error_summary: Optional[str] = None

    @field_validator('timestamp', mode='before')
    def parse_timestamp(cls, value):
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value

class AuditJournal:
    def __init__(self, journal_path: str = ".memory/audit_journal.jsonl"):
        self.journal_path = journal_path
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)

    def _read_journal(self) -> List[AuditRecord]:
        records = []
        if not os.path.exists(self.journal_path):
            return records
        with open(self.journal_path, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    records.append(AuditRecord(**data))
                except (json.JSONDecodeError, ValidationError) as e:
                    print(f"Error reading audit record from journal: {e} in line: {line.strip()}")
        return records

    def log_record(self, record: AuditRecord):
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def query(
        self,
        since: Optional[datetime] = None,
        task_file: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> List[AuditRecord]:
        records = self._read_journal()
        
        filtered_records = []
        for record in records:
            match = True
            if since and record.timestamp < since:
                match = False
            if task_file and record.task_file != task_file:
                match = False
            if success is not None and record.success != success:
                match = False
            
            if match:
                filtered_records.append(record)
        
        return filtered_records

    def summary(self) -> Dict[str, any]:
        records = self._read_journal()
        
        total_executions = len(records)
        successful_executions = sum(1 for r in records if r.success)
        failed_executions = total_executions - successful_executions
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0
        
        total_duration = sum(r.duration_seconds for r in records)
        avg_duration_seconds = (total_duration / total_executions) if total_executions > 0 else 0.0
        
        llm_provider_usage = {}
        for record in records:
            for provider in record.llm_provider_used_per_phase.values():
                llm_provider_usage[provider] = llm_provider_usage.get(provider, 0) + 1

        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": round(success_rate, 2), # Round to 2 decimal places
            "avg_duration_seconds": round(avg_duration_seconds, 2), # Round to 2 decimal places
            "llm_provider_usage": llm_provider_usage,
        }
