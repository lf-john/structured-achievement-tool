
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, ValidationError

class AuditRecord(BaseModel):
    """
    Pydantic model for a single audit log entry of a story execution.
    """
    timestamp: str  # ISO formatted datetime string
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
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)

    def log_record(self, record: AuditRecord):
        """
        Appends a structured audit record to the journal file as a JSON line.
        """
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def _read_records(self) -> List[AuditRecord]:
        """
        Reads all audit records from the journal file.
        Returns an empty list if the file does not exist or is empty.
        """
        if not os.path.exists(self.journal_path):
            return []
        
        records = []
        with open(self.journal_path, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    records.append(AuditRecord(**data))
                except (json.JSONDecodeError, ValidationError) as e:
                    # Log error for malformed lines, but continue processing valid ones
                    print(f"Error reading audit journal line: {line.strip()}. Error: {e}")
        return records

    def query(
        self,
        since: Optional[datetime] = None,
        task_file: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> List[AuditRecord]:
        """
        Queries audit records based on optional filters.

        Args:
            since (datetime, optional): Only return records timestamped after this date.
            task_file (str, optional): Only return records for this specific task file.
            success (bool, optional): Only return records based on their success status.

        Returns:
            List[AuditRecord]: A list of matching audit records.
        """
        all_records = self._read_records()
        filtered_records = []

        for record in all_records:
            record_timestamp = datetime.fromisoformat(record.timestamp)
            
            if since and record_timestamp < since:
                continue
            if task_file and record.task_file != task_file:
                continue
            if success is not None and record.success != success:
                continue
            
            filtered_records.append(record)
        
        return filtered_records

    def summary(self) -> Dict[str, any]:
        """
        Calculates and returns aggregate statistics from all audit records.
        """
        all_records = self._read_records()

        total_executions = len(all_records)
        successful_executions = sum(1 for r in all_records if r.success)
        failed_executions = total_executions - successful_executions
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0
        
        total_duration_seconds = sum(r.duration_seconds for r in all_records)
        avg_duration_seconds = (total_duration_seconds / total_executions) if total_executions > 0 else 0.0

        llm_provider_usage: Dict[str, int] = {}
        for record in all_records:
            for provider in record.llm_provider_used_per_phase.values():
                llm_provider_usage[provider] = llm_provider_usage.get(provider, 0) + 1

        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": round(success_rate, 2),
            "avg_duration_seconds": round(avg_duration_seconds, 2),
            "llm_provider_usage": llm_provider_usage,
        }
