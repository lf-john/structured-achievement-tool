import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel


class AuditRecord(BaseModel):
    timestamp: datetime
    task_file: str
    story_id: str
    story_title: str
    llm_provider_per_phase: dict
    session_id: str
    total_turns: int
    exit_code: Optional[int]
    duration_seconds: float
    success: bool
    phases_completed: List[str]
    error_summary: Optional[str]


class AuditJournal:
    def __init__(self, journal_file: Path = Path(".memory/audit_journal.jsonl")):
        self.journal_file = journal_file
        self.journal_file.parent.mkdir(parents=True, exist_ok=True)

    def append_record(self, record: AuditRecord):
        with open(self.journal_file, "a") as f:
            f.write(record.model_dump_json() + "\n")
