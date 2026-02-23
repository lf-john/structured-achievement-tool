import os
import json
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from collections import defaultdict

class AuditRecord(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    task_file: str
    story_id: str
    story_title: str
    llm_provider_used_per_phase: Dict[str, str]
    session_id: str = "N/A" # Default if not explicitly provided
    total_turns: int
    exit_code: int
    duration_seconds: float
    success: bool
    phases_completed: List[str]
    error_summary: Optional[str] = None

class AuditJournal:
    def __init__(self, journal_path: str = ".memory/audit_journal.jsonl"):
        self.journal_path = journal_path
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)

    def log_record(self, record: AuditRecord):
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def _read_records(self) -> List[AuditRecord]:
        records = []
        if not os.path.exists(self.journal_path):
            return records
        with open(self.journal_path, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    records.append(AuditRecord(**data))
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from audit journal: {e} - Line: {line.strip()}")
                except ValueError as e:
                    print(f"Error validating AuditRecord from audit journal: {e} - Data: {data}")
        return records

    def query(self, since: Optional[datetime] = None, task_file: Optional[str] = None, success: Optional[bool] = None) -> List[AuditRecord]:
        all_records = self._read_records()
        filtered_records = []
        for record in all_records:
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

    def summary(self) -> Dict[str, Any]:
        all_records = self._read_records()
        
        total_executions = len(all_records)
        successful_executions = sum(1 for r in all_records if r.success)
        failed_executions = total_executions - successful_executions
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0
        
        total_duration = sum(r.duration_seconds for r in all_records)
        avg_duration_seconds = (total_duration / total_executions) if total_executions > 0 else 0.0
        
        llm_provider_usage = defaultdict(int)
        for record in all_records:
            for provider in record.llm_provider_used_per_phase.values():
                llm_provider_usage[provider] += 1
                
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": round(success_rate, 2),
            "avg_duration_seconds": round(avg_duration_seconds, 2),
            "llm_provider_usage": dict(llm_provider_usage),
        }
