import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# Define the path to the audit journal file
AUDIT_JOURNAL_PATH = Path(".memory/audit_journal.jsonl")

class AuditRecord(BaseModel):
    """Pydantic model for an audit record."""
    timestamp: datetime = Field(default_factory=datetime.now)
    task_file: str
    story_id: str
    story_title: str
    llm_provider_per_phase: Dict[str, str] = Field(default_factory=dict)
    session_id: str
    total_turns: int
    exit_code: Optional[int] = None
    duration_seconds: float
    success: bool
    phases_completed: List[str] = Field(default_factory=list)
    error_summary: Optional[str] = None

class AuditJournal:
    """Manages appending AuditRecord instances to a JSONL file."""

    def __init__(self, journal_path: Path | str = AUDIT_JOURNAL_PATH):
        self.journal_path = Path(journal_path)
        self._ensure_journal_file_exists()

    def _ensure_journal_file_exists(self):
        """Ensures the audit journal file and its parent directory exist."""
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.journal_path.exists():
            self.journal_path.touch()

    def log_record(self, record: AuditRecord):
        """Appends an AuditRecord instance to the journal file as a JSON line."""
        with open(self.journal_path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def query(
        self,
        since: Optional[datetime] = None,
        task_file: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> List[AuditRecord]:
        """
        Queries the audit journal for records matching specified criteria.
        """
        records = []
        if not self.journal_path.exists():
            return []

        with open(self.journal_path, "r") as f:
            for line in f:
                try:
                    record_dict = json.loads(line)
                    record = AuditRecord(**record_dict)
                    
                    match = True
                    if since and record.timestamp < since:
                        match = False
                    if task_file and record.task_file != task_file:
                        match = False
                    if success is not None and record.success != success:
                        match = False
                    
                    if match:
                        records.append(record)
                except json.JSONDecodeError:
                    # Log error or handle corrupted line
                    continue
                except Exception:
                    # Handle other potential parsing errors
                    continue
        return records

    def summary(self) -> Dict[str, any]:
        """
        Returns aggregate statistics from the audit journal.
        """
        all_records = self.query()
        total_records = len(all_records)
        successful_executions = sum(1 for r in all_records if r.success)
        failed_executions = total_records - successful_executions
        
        total_duration = sum(r.duration_seconds for r in all_records)
        
        llm_provider_usage: Dict[str, int] = {}
        for record in all_records:
            for provider in record.llm_provider_per_phase.values():
                llm_provider_usage[provider] = llm_provider_usage.get(provider, 0) + 1
                
        if total_records == 0:
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "success_rate": 0.0,
                "avg_duration_seconds": 0.0,
                "llm_provider_usage": {},
            }
                
        return {
            "total_executions": total_records,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": (successful_executions / total_records) * 100,
            "avg_duration_seconds": total_duration / total_records,
            "llm_provider_usage": llm_provider_usage,
        }
