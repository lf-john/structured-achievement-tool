import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel, Field, ValidationError


class AuditRecord(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    task_file: str
    story_id: str
    story_title: str
    llm_provider_per_phase: Dict[str, str] = Field(default_factory=dict)
    session_id: str
    total_turns: int
    exit_code: int
    duration_seconds: float
    success: bool
    phases_completed: List[str] = Field(default_factory=list)
    error_summary: Optional[str] = None


class AuditJournal:
    def __init__(self, journal_file_path: Union[str, Path]):
        self.journal_file_path = Path(journal_file_path)
        self.journal_file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.journal_file_path.exists():
            with open(self.journal_file_path, 'w') as f:
                pass  # Create an empty file if it doesn't exist

    def append_record(self, record: AuditRecord):
        with open(str(self.journal_file_path), 'a', encoding='utf-8') as f:
            f.write(record.model_dump_json() + '\n')

    def _read_records(self) -> List[AuditRecord]:
        records = []
        if not self.journal_file_path.exists():
            return records
        with open(str(self.journal_file_path), 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record_data = json.loads(line)
                    records.append(AuditRecord(**record_data))
                except (json.JSONDecodeError, ValidationError) as e:
                    # Log or handle malformed lines, for now, just skip
                    print(f"Skipping malformed audit record: {line.strip()} - Error: {e}")
        return records

    def query(
        self,
        since: Optional[datetime] = None,
        task_file: Optional[str] = None,
        success: Optional[bool] = None
    ) -> List[AuditRecord]:
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

        total_duration = sum(r.duration_seconds for r in all_records)
        total_turns = sum(r.total_turns for r in all_records)
        total_llm_calls = sum(len(r.llm_provider_per_phase) for r in all_records)

        avg_duration = total_duration / total_executions if total_executions > 0 else 0
        avg_turns = total_turns / total_executions if total_executions > 0 else 0
        success_rate = (successful_executions / total_executions) * 100 if total_executions > 0 else 0

        # Collect unique task files and LLM providers
        unique_task_files = set(r.task_file for r in all_records)
        llm_provider_counts = {}
        for record in all_records:
            for provider in record.llm_provider_per_phase.values():
                llm_provider_counts[provider] = llm_provider_counts.get(provider, 0) + 1

        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": round(success_rate, 2),
            "total_duration_seconds": round(total_duration, 2),
            "average_duration_seconds": round(avg_duration, 2),
            "total_turns": total_turns,
            "average_total_turns": round(avg_turns, 2),
            "total_llm_calls": total_llm_calls,
            "unique_task_files": len(unique_task_files),
            "llm_provider_usage": llm_provider_counts,
        }
