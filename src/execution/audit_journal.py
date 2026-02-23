import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

class AuditRecord(BaseModel):
    """
    Pydantic model for a single audit log entry of a story execution.
    """
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the record creation")
    task_file: str = Field(..., description="Path to the task file (e.g., /path/to/task.md)")
    story_id: str = Field(..., description="Unique identifier for the story")
    story_title: str = Field(..., description="Title of the story")
    llm_provider_used_per_phase: Dict[str, str] = Field(default_factory=dict, description="LLM provider used for each phase (e.g., {'plan': 'Claude', 'code': 'Gemini'})")
    session_id: str = Field(..., description="Unique identifier for the execution session")
    total_turns: int = Field(..., description="Total LLM turns taken during story execution")
    exit_code: int = Field(..., description="Exit code of the story execution (0 for success, non-zero for failure)")
    duration_seconds: float = Field(..., description="Duration of the story execution in seconds")
    success: bool = Field(..., description="True if the story execution was successful, False otherwise")
    phases_completed: List[str] = Field(default_factory=list, description="List of phases completed during the story execution")
    error_summary: Optional[str] = Field(None, description="Summary of the error if the story failed")

class AuditJournal:
    """
    Manages the audit journal for SAT story executions.
    Logs records to a JSONL file and provides query and summary capabilities.
    """
    def __init__(self, journal_path: str = ".memory/audit_journal.jsonl"):
        self.journal_path = journal_path
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)

    def log_record(self, record: AuditRecord):
        """
        Appends an AuditRecord to the audit journal file as a JSON line.
        """
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def _read_all_records(self) -> List[AuditRecord]:
        """Reads all records from the journal file."""
        records = []
        if not os.path.exists(self.journal_path):
            return records
        with open(self.journal_path, "r") as f:
            for line in f:
                try:
                    records.append(AuditRecord.model_validate_json(line))
                except Exception as e:
                    # Log error if a line is malformed, but continue processing
                    print(f"Error reading audit record: {e} in line: {line.strip()}")
        return records

    def query(self, since: Optional[datetime] = None, task_file: Optional[str] = None, success: Optional[bool] = None) -> List[AuditRecord]:
        """
        Queries audit records based on optional filters.
        """
        all_records = self._read_all_records()
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

    def summary(self) -> Dict[str, any]:
        """
        Returns aggregate statistics from the audit journal.
        """
        all_records = self._read_all_records()

        total_executions = len(all_records)
        successful_executions = sum(1 for r in all_records if r.success)
        failed_executions = total_executions - successful_executions
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0
        
        total_duration = sum(r.duration_seconds for r in all_records)
        avg_duration_seconds = (total_duration / total_executions) if total_executions > 0 else 0.0

        llm_provider_usage: Dict[str, int] = {}
        for record in all_records:
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
