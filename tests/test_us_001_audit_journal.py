"""
IMPLEMENTATION PLAN for US-001:

Components:
  - src/execution/audit_journal.py: This file will contain the Pydantic model AuditRecord and the AuditJournal class.
  - AuditRecord (Pydantic BaseModel): Defines the structure for audit log entries with fields like timestamp, task_file, story_id, etc.
  - AuditJournal (Class): Manages the appending of AuditRecord instances to a JSONL file (`.memory/audit_journal.jsonl`).
    - `log_record(self, record: AuditRecord)`: Appends a record to the journal.
    - `query(self, since=None, task_file=None, success=None)`: Filters and reads records.
    - `summary()`: Returns aggregate statistics.

Test Cases:
  1. Test that AuditRecord can be imported and instantiated with valid data. (AC: `AuditRecord` Pydantic model is defined with all specified fields and correct types.)
  2. Test AuditRecord field types and optionality (e.g., `error_summary` can be None). (AC: `AuditRecord` Pydantic model is defined with all specified fields and correct types.)
  3. Test that AuditRecord raises validation error for invalid type. (AC: `AuditRecord` Pydantic model is defined with all specified fields and correct types.)
  4. Test that AuditJournal can be imported and instantiated, and its `log_record` method exists. (AC: `AuditJournal` class is defined with a `log_record` method.)
  5. Test that `log_record` correctly serializes an `AuditRecord` to JSONL format and appends it to the specified file. (AC: `log_record` correctly writes `AuditRecord` data as JSON lines to `.memory/audit_journal.jsonl`.)
  6. Test that `log_record` creates the journal file if it doesn't exist. (AC: `log_record` correctly writes `AuditRecord` data as JSON lines to `.memory/audit_journal.jsonl`.)
  7. Test appending multiple records to ensure each is on a new line. (AC: `A sample `AuditRecord` can be successfully appended to the journal file.`)\
  8. Test the full cycle of creating an AuditRecord and appending it, then verifying content by reading. (AC: `A sample `AuditRecord` can be successfully appended to the journal file.`)\
  9. Test `query()` returns all records when no filters are applied. (AC: `query()` correctly filters by date, task, and success status.)
  10. Test `query()` filters records by `since` date. (AC: `query()` correctly filters by date, task, and success status.)
  11. Test `query()` filters records by `task_file`. (AC: `query()` correctly filters by date, task, and success status.)
  12. Test `query()` filters records by `success` status. (AC: `query()` correctly filters by date, task, and success status.)
  13. Test `query()` filters records by multiple criteria. (AC: `query()` correctly filters by date, task, and success status.)
  14. Test `query()` returns an empty list when no records match filters. (AC: `query()` correctly filters by date, task, and success status.)
  15. Test `query()` handles an empty journal file. (AC: `query()` correctly filters by date, task, and success status.)
  16. Test `summary()` returns correct aggregate statistics for mixed records. (AC: `summary()` returns accurate aggregate statistics.)
  17. Test `summary()` returns correct aggregate statistics for only successful records. (AC: `summary()` returns accurate aggregate statistics.)
  18. Test `summary()` returns correct aggregate statistics for only failed records. (AC: `summary()` returns accurate aggregate statistics.)
  19. Test `summary()` handles an empty journal file. (AC: `summary()` returns default/zero values for an empty journal file.)
  20. Test `summary()` accurately counts LLM provider usage. (AC: `summary()` returns accurate aggregate statistics.)

Edge Cases:
  - `error_summary` field being `None`.
  - `phases_completed` being an empty list.
  - The audit journal file not existing before the first write.
  - No records matching `query` filters.
  - Empty journal file for `query` or `summary`.
"""
import pytest
from datetime import datetime, timedelta
import json
import os
import sys

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

@pytest.fixture
def create_sample_records(sample_audit_record_data):
    """Fixture to create and write multiple sample audit records."""
    def _creator(num_records=3, task_file_prefix="/path/to/task", success_ratio=0.5):
        records_data = []
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH) # Instantiate here to ensure it's available for logging
        for i in range(num_records):
            data = sample_audit_record_data.copy()
            data["timestamp"] = (datetime.now() - timedelta(days=num_records - 1 - i)).isoformat()
            data["task_file"] = f"{task_file_prefix}_{i}.md"
            data["story_id"] = f"US-00{i+1}"
            data["story_title"] = f"Story {i+1}"
            data["success"] = (i < num_records * success_ratio)
            data["exit_code"] = 0 if data["success"] else 1
            data["duration_seconds"] = 60 + i * 10.0
            data["llm_provider_per_phase"] = {"plan": "Claude" if i % 2 == 0 else "Gemini", "code": "Gemini"}
            data["error_summary"] = "Error" if not data["success"] else None
            records_data.append(data)
            # Log record as it's created, to build up the journal file for later query/summary
            journal.log_record(AuditRecord(**data))
        return records_data
    return _creator


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
    # AMENDED BY US-001: Renamed method `append_record` to `log_record` as per story requirements.
    def test_audit_journal_can_be_instantiated_and_log_record_method_exists(self):
        """
        AC: `AuditJournal` class is defined with a `log_record` method.
        Test instantiation of AuditJournal and existence of log_record method.
        """
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        assert isinstance(journal, AuditJournal)
        assert hasattr(journal, "log_record")
        assert callable(journal.log_record)

    # AMENDED BY US-001: Renamed method `append_record` to `log_record` as per story requirements.
    def test_log_record_creates_file_and_writes_jsonl(self, clean_audit_journal, sample_audit_record_data):
        """
        AC: `log_record` correctly writes `AuditRecord` data as JSON lines to `.memory/audit_journal.jsonl`.
        AC: A sample `AuditRecord` can be successfully appended to the journal file.
        Test that `log_record` creates the file and writes a single record as JSONL.
        """
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        record = AuditRecord(**sample_audit_record_data)
        journal.log_record(record)

        assert os.path.exists(TEST_AUDIT_JOURNAL_PATH)
        with open(TEST_AUDIT_JOURNAL_PATH, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            written_record = json.loads(lines[0])
            # Pydantic serializes datetime objects to ISO format, so ensure comparison is consistent
            expected_record = json.loads(record.model_dump_json())
            assert written_record == expected_record

    # AMENDED BY US-001: Renamed method `append_record` to `log_record` as per story requirements.
    def test_log_record_appends_multiple_records(self, clean_audit_journal, sample_audit_record_data):
        """
        AC: `log_record` correctly writes `AuditRecord` data as JSON lines to `.memory/audit_journal.jsonl`.
        Test that `log_record` appends multiple records correctly, each on a new line.
        """
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        record1 = AuditRecord(**sample_audit_record_data)
        
        second_record_data = sample_audit_record_data.copy()
        second_record_data["story_id"] = "US-002"
        second_record_data["error_summary"] = "Something went wrong"
        record2 = AuditRecord(**second_record_data)

        journal.log_record(record1)
        journal.log_record(record2)

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

    def test_query_returns_all_records_when_no_filters(self, clean_audit_journal, create_sample_records):
        """
        AC: `query()` correctly filters by date, task, and success status.
        Test that query returns all records when no filters are applied.
        """
        expected_records_data = create_sample_records(num_records=5)
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        queried_records = journal.query()
        assert len(queried_records) == 5
        assert [r.story_id for r in queried_records] == [d["story_id"] for d in expected_records_data]

    def test_query_filters_by_since_date(self, clean_audit_journal, create_sample_records):
        """
        AC: `query()` correctly filters by date, task, and success status.
        Test that query filters records correctly by a 'since' date.
        """
        records_data = create_sample_records(num_records=5)
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        
        # Query for records since the third record's timestamp
        since_date = datetime.fromisoformat(records_data[2]["timestamp"])
        queried_records = journal.query(since=since_date)
        
        assert len(queried_records) == 3 # Records 2, 3, 4 (0-indexed)
        assert queried_records[0].story_id == records_data[2]["story_id"]
        assert queried_records[2].story_id == records_data[4]["story_id"]

    def test_query_filters_by_task_file(self, clean_audit_journal, create_sample_records):
        """
        AC: `query()` correctly filters by date, task, and success status.
        Test that query filters records correctly by task_file.
        """
        records_data = create_sample_records(num_records=5, task_file_prefix="/my/task")
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        
        target_task_file = "/my/task_1.md"
        queried_records = journal.query(task_file=target_task_file)
        
        assert len(queried_records) == 1
        assert queried_records[0].task_file == target_task_file
        assert queried_records[0].story_id == records_data[1]["story_id"]

    def test_query_filters_by_success_status(self, clean_audit_journal, create_sample_records):
        """
        AC: `query()` correctly filters by date, task, and success status.
        Test that query filters records correctly by success status.
        """
        records_data = create_sample_records(num_records=4, success_ratio=0.5) # 2 success, 2 failed
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        
        successful_records = journal.query(success=True)
        assert len(successful_records) == 2
        assert all(r.success for r in successful_records)

        failed_records = journal.query(success=False)
        assert len(failed_records) == 2
        assert all(not r.success for r in failed_records)

    def test_query_filters_by_multiple_criteria(self, clean_audit_journal, create_sample_records):
        """
        AC: `query()` correctly filters by date, task, and success status.
        Test that query filters records correctly by multiple criteria.
        """
        records_data = create_sample_records(num_records=5, task_file_prefix="/complex/task", success_ratio=0.6)
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)

        # Example: successful records since day 1 for task_file_3.md
        since_date = datetime.fromisoformat(records_data[1]["timestamp"]) # Second record timestamp
        target_task_file = "/complex/task_2.md" # Third record
        
        # The third record (index 2) is successful and after since_date
        # records_data[0] = success, oldest
        # records_data[1] = fail
        # records_data[2] = success, task_file_2.md
        # records_data[3] = fail
        # records_data[4] = success, newest
        
        queried_records = journal.query(since=since_date, task_file=target_task_file, success=True)
        
        assert len(queried_records) == 1
        assert queried_records[0].story_id == records_data[2]["story_id"]
        assert queried_records[0].task_file == target_task_file
        assert queried_records[0].success is True

    def test_query_returns_empty_list_when_no_matches(self, clean_audit_journal, create_sample_records):
        """
        AC: `query()` correctly filters by date, task, and success status.
        Test that query returns an empty list when no records match the filters.
        """
        create_sample_records(num_records=3)
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        
        queried_records = journal.query(task_file="/non/existent/task.md")
        assert len(queried_records) == 0

        queried_records = journal.query(since=datetime.now() + timedelta(days=1))
        assert len(queried_records) == 0

    def test_query_handles_empty_journal_file(self, clean_audit_journal):
        """
        AC: `query()` correctly filters by date, task, and success status.
        Test that query returns an empty list when the journal file does not exist or is empty.
        """
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        queried_records = journal.query()
        assert len(queried_records) == 0

    def test_summary_returns_correct_stats_for_mixed_records(self, clean_audit_journal, create_sample_records):
        """
        AC: `summary()` returns accurate aggregate statistics.
        Test that summary returns correct aggregate statistics for a mix of successful and failed records.
        """
        # 3 successful, 2 failed
        records_data = create_sample_records(num_records=5, success_ratio=0.6) 
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        summary = journal.summary()

        assert summary["successful_records"] == 3
        assert summary["success_rate"] == 60.0 # 3/5 * 100
        
        # Calculate expected average duration
        total_duration = sum(d["duration_seconds"] for d in records_data)
        assert pytest.approx(summary["avg_duration_seconds"], 0.01) == total_duration / 5
        
        assert summary["llm_provider_usage"]["Claude"] == 3 # record 0, 2, 4 (plan phase)
        assert summary["llm_provider_usage"]["Gemini"] == 7 # record 1, 3 (plan phase) + all 5 (code phase)

    def test_summary_returns_correct_stats_for_only_successful_records(self, clean_audit_journal, create_sample_records):
        """
        AC: `summary()` returns accurate aggregate statistics.
        Test that summary returns correct aggregate statistics for only successful records.
        """
        records_data = create_sample_records(num_records=3, success_ratio=1.0) # All successful
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        summary = journal.summary()

        assert summary["total_executions"] == 3
        assert summary["successful_executions"] == 3
        assert summary["failed_executions"] == 0
        assert summary["success_rate"] == 100.0
        
        total_duration = sum(d["duration_seconds"] for d in records_data)
        assert pytest.approx(summary["avg_duration_seconds"], 0.01) == total_duration / 3
        
        assert summary["llm_provider_usage"]["Claude"] == 2
        assert summary["llm_provider_usage"]["Gemini"] == 4

    def test_summary_returns_correct_stats_for_only_failed_records(self, clean_audit_journal, create_sample_records):
        """
        AC: `summary()` returns accurate aggregate statistics.
        Test that summary returns correct aggregate statistics for only failed records.
        """
        records_data = create_sample_records(num_records=3, success_ratio=0.0) # All failed
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        summary = journal.summary()

        assert summary["total_executions"] == 3
        assert summary["successful_executions"] == 0
        assert summary["failed_executions"] == 3
        assert summary["success_rate"] == 0.0
        
        total_duration = sum(d["duration_seconds"] for d in records_data)
        assert pytest.approx(summary["avg_duration_seconds"], 0.01) == total_duration / 3
        
        assert summary["llm_provider_usage"]["Claude"] == 2
        assert summary["llm_provider_usage"]["Gemini"] == 4

    def test_summary_handles_empty_journal_file(self, clean_audit_journal):
        """
        AC: `summary()` returns accurate aggregate statistics.
        Test that summary returns default/zero values for an empty journal file.
        """
        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        summary = journal.summary()

        assert summary["total_executions"] == 0
        assert summary["successful_executions"] == 0
        assert summary["failed_executions"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["avg_duration_seconds"] == 0.0
        assert summary["llm_provider_usage"] == {}

    def test_summary_accurately_counts_llm_provider_usage(self, clean_audit_journal, create_sample_records):
        """
        AC: `summary()` returns accurate aggregate statistics.
        Test that summary accurately counts LLM provider usage across phases.
        """
        # Records with varied LLM usage
        records_data = [
            {
                "timestamp": datetime.now().isoformat(), "task_file": "t1", "story_id": "s1", "story_title": "st1",
                "llm_provider_per_phase": {"plan": "Claude", "code": "Gemini", "verify": "Claude"},
                "session_id": "se1", "total_turns": 5, "exit_code": 0, "duration_seconds": 100, "success": True,
                "phases_completed": ["PLAN", "CODE", "VERIFY"], "error_summary": None,
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(), "task_file": "t2", "story_id": "s2", "story_title": "st2",
                "llm_provider_per_phase": {"plan": "Gemini", "design": "Gemini"},
                "session_id": "se2", "total_turns": 3, "exit_code": 1, "duration_seconds": 50, "success": False,
                "phases_completed": ["PLAN", "DESIGN"], "error_summary": "Design failed",
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(), "task_file": "t3", "story_id": "s3", "story_title": "st3",
                "llm_provider_per_phase": {"code": "Claude"},
                "session_id": "se3", "total_turns": 2, "exit_code": 0, "duration_seconds": 75, "success": True,
                "phases_completed": ["CODE"], "error_summary": None,
            },
        ]

        journal = AuditJournal(journal_path=TEST_AUDIT_JOURNAL_PATH)
        for data in records_data:
            journal.log_record(AuditRecord(**data))
        
        summary = journal.summary()
        
        expected_provider_usage = {
            "Claude": 3, # s1 (plan, verify), s3 (code)
            "Gemini": 3, # s1 (code), s2 (plan, design)
        }
        assert summary["llm_provider_usage"] == expected_provider_usage

# At the END of your test file, ALWAYS include:
if __name__ == "__main__":
    # In TDD-RED phase, we expect tests to fail. pytest.main returns an exit code.
    # We exit with 1 to indicate failure for the orchestrator, as per instructions.
    sys.exit(pytest.main([__file__]))
