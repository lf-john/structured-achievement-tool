from datetime import datetime
from typing import List, Optional
from pathlib import Path
import json

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    """
    Pydantic model for storing audit records.
    """
    timestamp: datetime = Field(default_factory=datetime.now)
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
    """
    Manages appending AuditRecord instances to a JSONL file.
    """
    def __init__(self, journal_path: Path | str = Path(".memory/audit_journal.jsonl")):
        self.journal_path = Path(journal_path)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def append_record(self, record: AuditRecord):
        """
        Serializes an AuditRecord to a JSON line and appends it to the journal file.
        """
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")
