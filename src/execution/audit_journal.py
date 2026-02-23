import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Define the path to the audit journal file
AUDIT_JOURNAL_FILE = Path(".memory/audit_journal.jsonl")


class AuditRecord(BaseModel):
    """
    Pydantic model for a single audit record, capturing key metrics and metadata
    for each task execution.
    """
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the audit record.")
    task_file: str = Field(description="Path to the task file.")
    story_id: str = Field(description="Unique identifier for the story.")
    story_title: str = Field(description="Title of the story.")
    llm_provider_per_phase: Dict[str, str] = Field(
        default_factory=dict, description="LLM provider used for each phase (e.g., {'DESIGN': 'claude-3-opus'})."
    )
    session_id: str = Field(description="Unique identifier for the entire task session.")
    total_turns: int = Field(description="Total number of turns/interactions during the story execution.")
    exit_code: Optional[int] = Field(None, description="Exit code of the story execution (0 for success).")
    duration_seconds: float = Field(description="Duration of the story execution in seconds.")
    success: bool = Field(description="True if the story execution was successful, False otherwise.")
    phases_completed: List[str] = Field(default_factory=list, description="List of phases completed during the story.")
    error_summary: Optional[str] = Field(None, description="Summary of any errors encountered.")


class AuditJournal:
    """
    Manages the audit journal, providing functionality to log new audit records,
    query existing records, and generate summary statistics.
    """

    def __init__(self, journal_path: Path = AUDIT_JOURNAL_FILE):
        """
        Initializes the AuditJournal, ensuring the journal file and its parent
        directory exist.
        """
        self.journal_file = Path(journal_path)
        self._initialize_journal_file()

    def _initialize_journal_file(self):
        """Ensures the audit journal file and its parent directory exist."""
        self.journal_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.journal_file.exists():
            self.journal_file.touch()

    def log_record(self, record: AuditRecord):
        """
        Appends a new AuditRecord instance to the audit journal file as a JSON line.
        """
        with open(self.journal_file, "a") as f:
            f.write(record.model_dump_json() + "\n")

    def query(
        self,
        since: Optional[datetime] = None,
        task_file: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> List[AuditRecord]:
        """
        Queries the audit journal for records matching the specified criteria.

        Args:
            since: Only return records after this timestamp.
            task_file: Only return records related to this task file.
            success: Only return records with this success status.

        Returns:
            A list of AuditRecord instances matching the criteria.
        """
        records: List[AuditRecord] = []
        if not self.journal_file.exists():
            return records

        with open(self.journal_file, "r") as f:
            for line in f:
                try:
                    record_data = json.loads(line)
                    record = AuditRecord(**record_data)

                    if since and record.timestamp < since:
                        continue
                    if task_file and record.task_file != task_file:
                        continue
                    if success is not None and record.success != success:
                        continue
                    records.append(record)
                except json.JSONDecodeError:
                    # Log error if a line is not valid JSON, but continue processing
                    continue
        return records

    def summary(self) -> Dict[str, any]:
        """
        Generates a summary of the audit journal, including total tasks,
        success rates, and LLM provider usage.

        Returns:
            A dictionary containing summary statistics.
        """
        all_records = self.query()
        total_records = len(all_records)
        successful_records = [r for r in all_records if r.success]
        failed_records = [r for r in all_records if not r.success]

        total_success = len(successful_records)
        total_failed = len(failed_records)
        success_rate = (total_success / total_records * 100) if total_records > 0 else 0.0

        avg_duration_success = (
            sum(r.duration_seconds for r in successful_records) / total_success
            if total_success > 0
            else 0.0
        )
        avg_duration_failed = (
            sum(r.duration_seconds for r in failed_records) / total_failed
            if total_failed > 0
            else 0.0
        )
        avg_duration_overall = (
            sum(r.duration_seconds for r in all_records) / total_records
            if total_records > 0
            else 0.0
        )

        llm_provider_usage: Dict[str, int] = {}
        for record in all_records:
            for provider in record.llm_provider_per_phase.values():
                llm_provider_usage[provider] = llm_provider_usage.get(provider, 0) + 1

        return {
            "total_executions": total_records,
            "successful_executions": total_success,
            "successful_records": total_success,
            "failed_executions": total_failed,
            "success_rate": round(success_rate, 2),
            "avg_duration_success_seconds": round(avg_duration_success, 2),
            "avg_duration_failed_seconds": round(avg_duration_failed, 2),
            "avg_duration_seconds": round(avg_duration_overall, 2),
            "llm_provider_usage": llm_provider_usage,
        }
