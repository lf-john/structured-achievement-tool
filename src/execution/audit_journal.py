from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import os
import fcntl # For file locking
import logging

logger = logging.getLogger(__name__)

class AuditRecord(BaseModel):
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
    def __init__(self, journal_path: str = ".memory/audit_journal.jsonl"):
        self.journal_path = journal_path
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)

    def log_record(self, record: AuditRecord):
        """Appends an AuditRecord to the journal file as a JSON line."""
        try:
            with open(self.journal_path, "a") as f:
                fcntl.flock(f, fcntl.LOCK_EX)  # Acquire an exclusive lock
                f.write(record.model_dump_json() + "\n")
                fcntl.flock(f, fcntl.LOCK_UN)  # Release the lock
        except IOError as e:
            logger.error(f"Failed to write audit record to {self.journal_path}: {e}")

    def query(self, since: Optional[datetime] = None, task_file: Optional[str] = None, success: Optional[bool] = None) -> List[AuditRecord]:
        """
        Queries audit records based on filters.
        :param since: datetime - Only return records after this timestamp.
        :param task_file: str - Only return records for a specific task file.
        :param success: bool - Only return records that succeeded or failed.
        :return: List[AuditRecord] - A list of matching audit records.
        """
        records = []
        if not os.path.exists(self.journal_path):
            return []

        try:
            with open(self.journal_path, "r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)  # Acquire a shared lock
                for line in f:
                    try:
                        data = json.loads(line)
                        record = AuditRecord(**data)
                        
                        match = True
                        if since and record.timestamp < since:
                            match = False
                        if task_file and record.task_file != task_file:
                            match = False
                        if success is not None and record.success != success:
                            match = False
                        
                        if match:
                            records.append(record)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping malformed JSON line in audit journal: {e} - Line: {line.strip()}")
                    except Exception as e:
                        logger.warning(f"Skipping record due to validation error: {e} - Line: {line.strip()}")
                fcntl.flock(f, fcntl.LOCK_UN)  # Release the lock
        except IOError as e:
            logger.error(f"Failed to read audit journal from {self.journal_path}: {e}")
        return records

    def summary(self) -> Dict[str, Any]:
        """
        Generates aggregate statistics from the audit journal.
        :return: Dict[str, Any] - A dictionary containing total executions, success rate, avg duration, etc.
        """
        all_records = self.query()
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
            "success_rate": round(success_rate, 2),
            "avg_duration_seconds": round(avg_duration_seconds, 2),
            "llm_provider_usage": llm_provider_usage,
        }
