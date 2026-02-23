from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    task_file: str
    story_id: str
    story_title: str
    llm_provider_per_phase: dict[str, str]
    session_id: str
    total_turns: int
    exit_code: Optional[int] = None
    duration_seconds: float
    success: bool
    phases_completed: List[str]
    error_summary: Optional[str] = None


class AuditJournal:
    def __init__(self, journal_path: Path | str = Path(".memory/audit_journal.jsonl")):
        self.journal_path = Path(journal_path)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def append_record(self, record: AuditRecord):
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")
