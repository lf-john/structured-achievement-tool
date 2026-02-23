"""
IMPLEMENTATION PLAN for US-001:

Components:
  - src/execution/audit_journal.py: This file will contain the Pydantic model AuditRecord and the AuditJournal class.
  - AuditRecord (Pydantic BaseModel): Defines the structure for audit log entries with fields like timestamp, task_file, story_id, etc.
  - AuditJournal (Class): Manages the appending of AuditRecord instances to a JSONL file (`.memory/audit_journal.jsonl`).

Test Cases:
  1. Test that AuditRecord can be imported and instantiated with valid data. (AC: `AuditRecord` Pydantic model is defined with all specified fields and correct types.)
  2. Test AuditRecord field types and optionality (e.g., `error_summary` can be None). (AC: `AuditRecord` Pydantic model is defined with all specified fields and correct types.)
  3. Test that AuditJournal can be imported and instantiated, and its `append_record` method exists. (AC: `AuditJournal` class is defined with an `append_record` method.)
  4. Test that `append_record` correctly serializes an `AuditRecord` to JSONL format and appends it to the specified file. (AC: `append_record` correctly writes `AuditRecord` data as JSON lines to `.memory/audit_journal.jsonl`.)
  5. Test that `append_record` creates the journal file if it doesn't exist. (AC: `append_record` correctly writes `AuditRecord` data as JSON lines to `.memory/audit_journal.jsonl`.)
  6. Test appending multiple records to ensure each is on a new line. (AC: `A sample `AuditRecord` can be successfully appended to the journal file.`)
  7. Test the full cycle of creating an AuditRecord and appending it, then verifying content by reading. (AC: `A sample `AuditRecord` can be successfully appended to the journal file.`)

Edge Cases:
  - `error_summary` field being `None`.
  - `phases_completed` being an empty list.
  - The audit journal file not existing before the first write.
"""
import pytest
from datetime import datetime
import json
import os

# This import is expected to fail with ModuleNotFoundError in TDD-RED phase
# Pytest will fail during collection due to this missing module, which is the desired TDD-RED outcome.
from src.execution.audit_journal import AuditRecord, AuditJournal

# Define the path to the audit journal file for testing
TEST_AUDIT_JOURNAL_PATH = ".memory/test_audit_journal.jsonl"

@pytest.fixture
def clean_audit_journal():
    """Fixture to ensure the test audit journal file is clean before and after tests."""
    if os.path.exists(TEST_AUDIT_JOURNAL_PATH):
        os.remove(TEST_AUDIT_JOURNAL_PATH)
    yield
    if os.path.exists(TEST_AUDIT_JOURNAL_PATH):
        os.remove(TEST_AUDIT_JOURNAL_PATH)

@pytest.fixture
def sample_audit_record_data():
    """Provides a dictionary of valid data for AuditRecord."""
    return {
        "timestamp": datetime.now().isoformat(),
        "task_file": "/path/to/task.md",
        "story_id": "US-001",
        "story_title": "Implement AuditJournal",
        "llm_provider_per_phase": {"plan": "Claude", "code": "Gemini"},
        "session_id": "sess-12345",
        "total_turns": 10,
        "exit_code": 0,
        "duration_seconds": 120.5,
        "success": True,
        "phases_completed": ["PLAN", "DESIGN", "TDD_RED"],
        "error_summary": None,
    }

class TestAuditRecord:
    def test_audit_record_can_be_instantiated_with_valid_data(self, sample_audit_record_data):
        """
        AC: `AuditRecord` Pydantic model is defined with all specified fields and correct types.
        Test instantiation of AuditRecord with valid data.
        """
        record = AuditRecord(**sample_audit_record_data)
        assert isinstance(record, AuditRecord)
        assert record.task_file == "/path/to/task.md"
        assert record.success is True
        assert record.error_summary is None

    def test_audit_record_handles_missing_optional_fields(self, sample_audit_record_data):
        """
        AC: `AuditRecord` Pydantic model is defined with all specified fields and correct types.
        Test instantiation of AuditRecord without an optional field (error_summary).
        """
        data_without_error_summary = sample_audit_record_data.copy()
        del data_without_error_summary["error_summary"]
        record = AuditRecord(**data_without_error_summary)
        assert record.error_summary is None

    def test_audit_record_raises_validation_error_for_invalid_type(self, sample_audit_record_data):
        """
        AC: `AuditRecord` Pydantic model is defined with all specified fields and correct types.
        Test that AuditRecord raises validation error for invalid types.
        """
        invalid_data = sample_audit_record_data.copy()
        invalid_data["total_turns"] = "not_an_int"
        with pytest.raises(ValueError):
            AuditRecord(**invalid_data)

class TestAuditJournal:
    def test_audit_journal_can_be_instantiated_and_append_record_method_exists(self):
        """
        AC: `AuditJournal` class is defined with an `append_record` method.
        Test instantiation of AuditJournal and existence of append_record method.
        """
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        assert isinstance(journal, AuditJournal)
        assert hasattr(journal, "append_record")
        assert callable(journal.append_record)

    def test_append_record_creates_file_and_writes_jsonl(self, clean_audit_journal, sample_audit_record_data):
        """
        AC: `append_record` correctly writes `AuditRecord` data as JSON lines to `.memory/audit_journal.jsonl`.
        AC: A sample `AuditRecord` can be successfully appended to the journal file.
        Test that `append_record` creates the file and writes a single record as JSONL.
        """
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        record = AuditRecord(**sample_audit_record_data)
        journal.append_record(record)

        assert os.path.exists(TEST_AUDIT_JOURNAL_PATH)
        with open(TEST_AUDIT_JOURNAL_PATH, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            written_record = json.loads(lines[0])
            # Pydantic serializes datetime objects to ISO format, so ensure comparison is consistent
            expected_record = json.loads(record.model_dump_json())
            assert written_record == expected_record

    def test_append_record_appends_multiple_records(self, clean_audit_journal, sample_audit_record_data):
        """
        AC: `append_record` correctly writes `AuditRecord` data as JSON lines to `.memory/audit_journal.jsonl`.
        Test that `append_record` appends multiple records correctly, each on a new line.
        """
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        record1 = AuditRecord(**sample_audit_record_data)
        
        second_record_data = sample_audit_record_data.copy()
        second_record_data["story_id"] = "US-002"
        second_record_data["error_summary"] = "Something went wrong"
        record2 = AuditRecord(**second_record_data)

        journal.append_record(record1)
        journal.append_record(record2)

        assert os.path.exists(TEST_AUDIT_JOURNAL_PATH)
        with open(TEST_AUDIT_JOURNAL_PATH, "r") as f:
            lines = f.readlines()
            assert len(lines) == 2
            
            written_record1 = json.loads(lines[0])
            expected_record1 = json.loads(record1.model_dump_json())
            assert written_record1 == expected_record1

            written_record2 = json.loads(lines[1])
            expected_record2 = json.loads(record2.model_dump_json())
            assert written_record2 == expected_record2
