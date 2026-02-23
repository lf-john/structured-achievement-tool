from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import os
from collections import defaultdict

class AuditRecord(BaseModel):
    """
    Pydantic model for a single audit log entry of a story execution.
    """
    timestamp: datetime = Field(default_factory=datetime.now)
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
    """
    Manages the logging, querying, and summarizing of story execution audit records.
    Records are stored as JSON lines in a specified file.
    """
    def __init__(self, journal_path: str = ".memory/audit_journal.jsonl"):
        self.journal_path = journal_path
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)

    def log_record(self, record: AuditRecord):
        """
        Appends an AuditRecord instance as a JSON line to the journal file.
        """
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def _read_records(self) -> List[AuditRecord]:
        """
        Reads all records from the journal file.
        Returns an empty list if the file does not exist or is empty.
        """
        records = []
        if not os.path.exists(self.journal_path):
            return records
        
        with open(self.journal_path, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    records.append(AuditRecord(**data))
                except (json.JSONDecodeError, ValidationError) as e:
                    # Log error for malformed lines but continue processing
                    print(f"Error reading audit record: {e} in line: {line.strip()}")
        return records

    def query(self, since: Optional[datetime] = None, task_file: Optional[str] = None, success: Optional[bool] = None) -> List[AuditRecord]:
        """
        Queries audit records based on optional filters.

        Args:
            since: Only return records after this datetime.
            task_file: Only return records for this specific task file path.
            success: Only return records with this success status (True for successful, False for failed).

        Returns:
            A list of matching AuditRecord instances.
        """
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
        
        # Sort by timestamp to ensure consistent ordering for tests
        return sorted(filtered_records, key=lambda r: r.timestamp)

    def summary(self) -> Dict[str, Any]:
        """
        Generates aggregate statistics from all audit records.

        Returns:
            A dictionary containing:
                - total_executions: Total number of story executions.
                - successful_executions: Number of successful executions.
                - failed_executions: Number of failed executions.
                - success_rate: Percentage of successful executions.
                - avg_duration_seconds: Average duration of executions.
                - llm_provider_usage: Dictionary of LLM provider usage counts across all phases.
        """
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
