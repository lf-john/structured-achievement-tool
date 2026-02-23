from pydantic import BaseModel, ValidationError
from datetime import datetime
from typing import Optional, List, Dict
import json
import os

class AuditRecord(BaseModel):
    timestamp: str
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

class AuditJournal:
    def __init__(self, journal_path: str = ".memory/audit_journal.jsonl"):
        self.journal_path = journal_path
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)

    def log_record(self, record: AuditRecord):
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def query(self, since: Optional[datetime] = None, task_file: Optional[str] = None, success: Optional[bool] = None) -> List[AuditRecord]:
        records = []
        if not os.path.exists(self.journal_path):
            return []

        with open(self.journal_path, "r") as f:
            for line in f:
                try:
                    record_data = json.loads(line)
                    record = AuditRecord(**record_data)
                    
                    if since and datetime.fromisoformat(record.timestamp) < since:
                        continue
                    if task_file and record.task_file != task_file:
                        continue
                    if success is not None and record.success != success:
                        continue
                    records.append(record)
                except (json.JSONDecodeError, ValidationError) as e:
                    print(f"Error reading audit record: {e} in line: {line.strip()}")
                    continue
        return records

    def summary(self) -> Dict:
        records = self.query()
        total_executions = len(records)
        successful_executions = sum(1 for r in records if r.success)
        failed_executions = total_executions - successful_executions
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0
        
        total_duration = sum(r.duration_seconds for r in records)
        avg_duration_seconds = (total_duration / total_executions) if total_executions > 0 else 0.0

        llm_provider_usage: Dict[str, int] = {}
        for record in records:
            for provider in record.llm_provider_used_per_phase.values():
                llm_provider_usage[provider] = llm_provider_usage.get(provider, 0) + 1
        
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": success_rate,
            "avg_duration_seconds": avg_duration_seconds,
            "llm_provider_usage": llm_provider_usage,
        }
