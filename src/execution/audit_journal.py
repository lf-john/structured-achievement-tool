import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    task_file: str
    story_id: str
    story_title: str
    llm_provider_per_phase: Dict[str, str]
    session_id: str
    total_turns: int
    exit_code: int
    duration_seconds: float
    success: bool
    phases_completed: List[str]
    error_summary: Optional[str] = None


class AuditJournal:
    def __init__(self, journal_file: Path = Path(".memory/audit_journal.jsonl")):
        self.journal_file = journal_file
        self.journal_file.parent.mkdir(parents=True, exist_ok=True)

    def append_record(self, record: AuditRecord):
        with open(self.journal_file, "a") as f:
            f.write(record.model_dump_json() + '\n')

    def query(
        self,
        since: Optional[datetime] = None,
        task_file: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> List[AuditRecord]:
        records = []
        if not self.journal_file.exists():
            return []

        with open(self.journal_file, "r") as f:
            for line in f:
                try:
                    record_data = json.loads(line)
                    record = AuditRecord(**record_data)

                    if since and record.timestamp < since:
                        continue
                    if task_file and record.task_file != task_file:
                        continue
                    if success is not None and record.success != success:
                        continue
                    records.append(record)
                except json.JSONDecodeError:
                    continue  # Skip invalid JSON lines
        return records

    def summary(self) -> Dict[str, Any]:
        records = self.query()
        if not records:
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "success_rate": 0.0,
                "average_duration_seconds": 0.0,
                "provider_usage_counts": {},
            }

        total_executions = len(records)
        successful_executions = sum(1 for r in records if r.success)
        failed_executions = total_executions - successful_executions
        success_rate = (
            (successful_executions / total_executions) * 100 if total_executions > 0 else 0.0
        )
        total_duration = sum(r.duration_seconds for r in records)
        average_duration_seconds = (
            total_duration / total_executions if total_executions > 0 else 0.0
        )

        provider_usage_counts: Dict[str, int] = {}
        total_llm_calls = 0
        total_turns = 0
        for record in records:
            total_llm_calls += len(record.llm_provider_per_phase)
            total_turns += record.total_turns
            for provider in record.llm_provider_per_phase.values():
                provider_usage_counts[provider] = provider_usage_counts.get(provider, 0) + 1
        
        average_total_turns = total_turns / total_executions if total_executions > 0 else 0.0

        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": success_rate,
            "average_duration_seconds": average_duration_seconds,
            "provider_usage_counts": provider_usage_counts,
            "total_llm_calls": total_llm_calls,
            "average_total_turns": average_total_turns,
        }
