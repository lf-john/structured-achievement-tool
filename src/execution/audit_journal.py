from datetime import datetime
from typing import List, Optional
import json
import os

from pydantic import BaseModel


class AuditRecord(BaseModel):
    timestamp: datetime
    task_file: str
    story_id: str
    story_title: str
    llm_provider_per_phase: dict
    session_id: str
    total_turns: int
    exit_code: int
    duration_seconds: float
    success: bool
    phases_completed: List[str]
    error_summary: Optional[str] = None


class AuditJournal:
    def __init__(self, journal_path: str = '.memory/audit_journal.jsonl'):
        self.journal_file_path = journal_path
        os.makedirs(os.path.dirname(self.journal_file_path), exist_ok=True)

    def append_record(self, record: AuditRecord):
        with open(self.journal_file_path, 'a') as f:
            f.write(record.model_dump_json() + '\n')
