from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import json
import os

class AuditRecord(BaseModel):
    """
    Pydantic model defining the schema for a single structured audit log entry.
    """
    timestamp: datetime = Field(..., description="Timestamp of the story execution.")
    task_file: str = Field(..., description="Path or identifier of the task file.")
    story_id: str = Field(..., description="Unique ID of the story.")
    story_title: str = Field(..., description="Title of the story.")
    llm_provider_per_phase: Dict[str, str] = Field(default_factory=dict, description="LLM provider used per phase (e.g., {'plan': 'Claude', 'code': 'Gemini'}).")
    session_id: str = Field(..., description="Unique ID for the session/run.")
    total_turns: int = Field(..., description="Total number of turns/interactions in the story.")
    exit_code: int = Field(..., description="Exit code of the story execution (0 for success, non-zero for failure).")
    duration_seconds: float = Field(..., description="Total duration of the story execution in seconds.")
    success: bool = Field(..., description="True if the story execution was successful, False otherwise.")
    phases_completed: List[str] = Field(default_factory=list, description="List of phases successfully completed.")
    error_summary: Optional[str] = Field(None, description="Summary of the error if the story failed.")

class AuditJournal:
    """
    Manages structured logging of story execution records to a JSONL file.
    """
    def __init__(self, journal_file: str):
        self.journal_file = journal_file
        os.makedirs(os.path.dirname(self.journal_file), exist_ok=True)

    def _read_records(self) -> List[AuditRecord]:
        """Reads all audit records from the journal file."""
        records = []
        if not os.path.exists(self.journal_file):
            return records
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f.readlines():
                try:
                    data = json.loads(line)
                    print(f"DEBUG: Processing line: {line.strip()}")
                    records.append(record)
                except json.JSONDecodeError as e:
                    print(f"Warning: Malformed JSON line in audit journal: {line.strip()} - {e}")
                except Exception as e:
                    print(f"Warning: Could not parse audit record: {line.strip()} - {e}")
        return records

    def append_record(self, record: AuditRecord):
        """Appends a Pydantic AuditRecord instance as a JSON line to the journal file."""
        with open(self.journal_file, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def query(self, since: Optional[datetime] = None, task_file: Optional[str] = None, success: Optional[bool] = None) -> List[AuditRecord]:
        """
        Filters and retrieves AuditRecord instances from the journal based on provided criteria.
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
        return filtered_records

    def summary(self) -> Dict[str, any]:
        """
        Calculates and returns aggregate statistics from all records in the journal.
        """
        all_records = self._read_records()
        total_executions = len(all_records)
        successful_executions = sum(1 for r in all_records if r.success)
        failed_executions = total_executions - successful_executions

        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0
        
        total_duration = sum(r.duration_seconds for r in all_records)
        average_duration_seconds = (total_duration / total_executions) if total_executions > 0 else 0.0

        total_turns_sum = sum(r.total_turns for r in all_records)
        average_total_turns = (total_turns_sum / total_executions) if total_executions > 0 else 0.0

        llm_provider_usage = {}
        total_llm_calls = 0
        for record in all_records:
            for provider in record.llm_provider_per_phase.values():
                llm_provider_usage[provider] = llm_provider_usage.get(provider, 0) + 1
                total_llm_calls += 1

        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": success_rate,
            "average_duration_seconds": average_duration_seconds,
            "total_llm_calls": total_llm_calls,
            "llm_provider_usage": llm_provider_usage,
            "average_total_turns": average_total_turns,
        }
