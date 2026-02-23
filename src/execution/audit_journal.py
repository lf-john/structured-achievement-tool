
import json
from datetime import datetime
from typing import List, Optional, Dict

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    """
    Pydantic model for storing audit records of task execution.
    """
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
    """
    Manages the appending of AuditRecord instances to a JSONL file.
    """
    def __init__(self, journal_path: str = ".memory/audit_journal.jsonl"):
        self.journal_file_path = journal_path

    def append_record(self, record: AuditRecord):
        """
        Serializes an AuditRecord instance to JSON and appends it as a new line
        to the audit journal file.
        """
        with open(self.journal_file_path, 'a') as f:
            f.write(record.model_dump_json() + '\n')

