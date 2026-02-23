from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict
import json
import os

class AuditRecord(BaseModel):
    timestamp: datetime
    task_file: str
    story_id: str
    story_title: str
    llm_provider_per_phase: Dict[str, str] = Field(default_factory=dict)
    session_id: str
    total_turns: int
    exit_code: int
    duration_seconds: float
    success: bool
    phases_completed: List[str] = Field(default_factory=list)
    error_summary: Optional[str] = None

class AuditJournal:
    def __init__(self, journal_file: str):
        self.journal_file = journal_file

    def append_record(self, record: AuditRecord):
        # Instruction: Append a new AuditRecord to the journal file as a JSON line.
        # This will ensure that new records are added to the end of the file.
        # The file is opened in append mode ('a') and encoded in UTF-8.
        # A newline character is added after each JSON line to ensure proper formatting.
        with open(self.journal_file, 'a', encoding='utf-8') as f:
            f.write(record.model_dump_json() + '\n')

    def _read_records(self) -> List[AuditRecord]:
        # Instruction: Read all records from the journal file.
        # If the file does not exist, return an empty list.
        # Each line is parsed as a JSON object and validated against the AuditRecord model.
        if not os.path.exists(self.journal_file):
            return []
        
        records = []
        with open(self.journal_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    records.append(AuditRecord.model_validate_json(line))
                except json.JSONDecodeError as e:
                    # Log error for malformed JSON, but continue processing other records
                    print(f"Warning: Malformed JSON line in {self.journal_file}: {e} - Line: {line.strip()}")
                except Exception as e:
                    print(f"Warning: Could not validate record: {e} - Line: {line.strip()}")
        return records

    def query(self, since: Optional[datetime] = None, task_file: Optional[str] = None, success: Optional[bool] = None) -> List[AuditRecord]:
        # Instruction: Query records from the journal based on optional filters:
        # 'since' (timestamp greater than or equal to), 'task_file' (exact match), and 'success' (boolean match).
        # Filters are applied cumulatively.
        records = self._read_records()
        
        filtered_records = []
        for record in records:
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
        # Instruction: Generate a summary of audit journal statistics including:
        # total_executions, successful_executions, failed_executions, success_rate,
        # average_duration_seconds, total_llm_calls, llm_provider_usage, and average_total_turns.
        # Handles cases with no records gracefully by returning default zero/empty values.
        records = self._read_records()
        
        total_executions = len(records)
        successful_executions = sum(1 for r in records if r.success)
        failed_executions = total_executions - successful_executions
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0
        
        total_duration = sum(r.duration_seconds for r in records)
        average_duration_seconds = (total_duration / total_executions) if total_executions > 0 else 0.0

        total_llm_calls = sum(len(r.llm_provider_per_phase) for r in records)
        
        llm_provider_usage: Dict[str, int] = {}
        for record in records:
            for provider in record.llm_provider_per_phase.values():
                llm_provider_usage[provider] = llm_provider_usage.get(provider, 0) + 1
        
        total_turns_sum = sum(r.total_turns for r in records)
        average_total_turns = (total_turns_sum / total_executions) if total_executions > 0 else 0.0

        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": round(success_rate, 2), # Round to 2 decimal places for consistency
            "average_duration_seconds": round(average_duration_seconds, 2), # Round to 2 decimal places
            "total_llm_calls": total_llm_calls,
            "llm_provider_usage": llm_provider_usage,
            "average_total_turns": round(average_total_turns, 2), # Round to 2 decimal places
        }
