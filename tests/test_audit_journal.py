import pytest
from unittest.mock import mock_open, patch
from datetime import datetime
import json
import os
import sys
from pathlib import Path

# This import will cause ModuleNotFoundError in TDD-RED phase
from src.execution.audit_journal import AuditJournal, AuditRecord
from pydantic import ValidationError

"""
IMPLEMENTATION PLAN for US-001: Implement Audit Journaling Module

Components:
  - AuditRecord (Pydantic Model, src/execution/audit_journal.py):
      - Responsibility: Define the schema for a single audit log entry.
      - Fields: timestamp (str), task_file (str), story_id (str), success (bool), duration_seconds (float), exit_code (int), error_summary (Optional[str]).
  - AuditJournal (Class, src/execution/audit_journal.py):
      - Responsibility: Manage the audit log file, including logging, querying, and summarizing records.
      - Methods:
          - __init__(file_path: str = ".memory/audit_journal.jsonl"): Initializes the journal, ensuring the directory exists.
          - log(record: AuditRecord): Appends an AuditRecord as a JSON line to the journal file.
          - query(success: Optional[bool] = None) -> list[AuditRecord]: Filters and retrieves AuditRecord objects.
          - summary() -> dict: Calculates and returns aggregate statistics (total count, success rate, average duration).

Data Flow:
  - An AuditRecord instance is created with execution details.
  - This instance is passed to AuditJournal.log() where it's serialized to a JSON line and appended to the journal file.
  - query() and summary() methods read from the journal file, parse JSON lines back into AuditRecord instances, and process them.

Integration Points:
  - Requires pydantic for data validation and serialization/deserialization.
  - Interacts with the file system to read from and write to the journal file.

Edge Cases:
  - Empty audit journal file: query() should return an empty list, summary() should return default (zero/empty) statistics.
  - Non-existent audit journal file: log() should create it, query()/summary() should handle gracefully (return empty results).
  - Malformed JSON lines in the journal file: query() and summary() should gracefully skip these lines without raising errors.
  - query() method: No success filter (return all), success=True, success=False.
  - summary() method: All successful records, all failed records, mixed records.
  - Records with duration_seconds = 0.0.

Test Cases:
  1. AuditRecord Model Definition (AC 2):
     - test_audit_record_model_definition_valid_data: Verifies correct instantiation with valid data.
     - test_audit_record_model_validation_fails_on_missing_required_fields: Ensures Pydantic validation for missing fields.
     - test_audit_record_model_validation_fails_on_invalid_types: Ensures Pydantic validation for incorrect types.
     - test_audit_record_model_handles_optional_error_summary: Verifies optional field behavior.
  2. AuditJournal Initialization (AC 3):
     - test_audit_journal_initialization_creates_directory_if_not_exists: Ensures the parent directory is created.
     - test_audit_journal_initialization_sets_correct_file_path: Verifies the file path is stored correctly.
  3. AuditJournal.log method (AC 4):
     - test_log_appends_single_record_as_json_line: Verifies a single record is written as a JSON line.
     - test_log_appends_multiple_records_as_json_lines: Verifies multiple records are written correctly.
     - test_log_creates_journal_file_if_not_exists: Ensures file creation on first log.
  4. AuditJournal.query method (AC 5):
     - test_query_returns_all_records_no_filter: Returns all records when no filter is applied.
     - test_query_filters_by_success_true: Filters by success=True.
     - test_query_filters_by_success_false: Filters by success=False.
     - test_query_returns_empty_list_no_matches: Returns empty list if no records match filters.
     - test_query_handles_empty_journal_file: Query on an empty journal file.
     - test_query_skips_malformed_json_lines: Ensures malformed lines are skipped gracefully.
  5. AuditJournal.summary method (AC 6):
     - test_summary_calculates_correct_statistics_multiple_records: Verifies all aggregate statistics (total, success, failed, success_rate, avg_duration).
     - test_summary_handles_empty_journal_file: Summary on an empty journal returns default values.
     - test_summary_handles_single_record: Summary for a single record.
     - test_summary_calculates_success_rate_correctly_mixed_results: Specific check for success rate calculation.
"""

JOURNAL_FILE = ".memory/audit_journal.jsonl"
JOURNAL_DIR = os.path.dirname(JOURNAL_FILE)

@pytest.fixture
def mock_audit_records():
    """Fixture to provide sample audit records."""
    return [
        AuditRecord(
            timestamp=datetime(2023, 1, 1, 10, 0, 0).isoformat(),
            task_file="task_A.md",
            story_id="story_1",
            success=True,
            duration_seconds=120.5,
            exit_code=0,
            error_summary=None,
        ),
        AuditRecord(
            timestamp=datetime(2023, 1, 1, 11, 0, 0).isoformat(),
            task_file="task_B.md",
            story_id="story_2",
            success=False,
            duration_seconds=60.0,
            exit_code=1,
            error_summary="Task failed due to X",
        ),
        AuditRecord(
            timestamp=datetime(2023, 1, 2, 9, 30, 0).isoformat(),
            task_file="task_A.md",
            story_id="story_3",
            success=True,
            duration_seconds=180.0,
            exit_code=0,
            error_summary=None,
        ),
        AuditRecord(
            timestamp=datetime(2023, 1, 2, 12, 0, 0).isoformat(),
            task_file="task_C.md",
            story_id="story_4",
            success=True,
            duration_seconds=90.0,
            exit_code=0,
            error_summary=None,
        ),
    ]

@pytest.fixture
def mock_jsonl_content(mock_audit_records):
    """Fixture to provide JSONL content string from mock records."""
    return "\n".join(record.model_dump_json() for record in mock_audit_records) + "\n"

@pytest.fixture
def mock_filesystem_write():
    """Fixture to mock file system operations for AuditJournal for write/creation tests."""
    m_open = mock_open()
    with patch("builtins.open", m_open):
        with patch("os.path.exists", return_value=True):  # Assume file exists by default for writes
            with patch("pathlib.Path.mkdir") as mock_mkdir: # Mock Path.mkdir
                yield m_open, mock_mkdir

@pytest.fixture
def mock_filesystem_read(mock_jsonl_content):
    """Fixture to mock file system operations for AuditJournal for read tests."""
    m_open = mock_open(read_data=mock_jsonl_content)
    with patch("builtins.open", m_open):
        with patch("os.path.exists", return_value=True):  # Assume file exists for reads
            yield m_open

@pytest.fixture
def mock_empty_journal():
    """Fixture to mock an empty journal file for read tests."""
    m_open = mock_open(read_data="")
    with patch("builtins.open", m_open):
        with patch("os.path.exists", return_value=True):
            yield m_open

class TestAuditRecord:
    """Tests for the AuditRecord Pydantic model."""

    def test_audit_record_model_definition_valid_data(self):
        """AC 2: Verifies AuditRecord can be instantiated with valid data."""
        record = AuditRecord(
            timestamp=datetime.now().isoformat(),
            task_file="test_task.md",
            story_id="test_story_id",
            success=True,
            duration_seconds=300.5,
            exit_code=0,
            error_summary="All good",
        )
        assert isinstance(record.timestamp, str)
        assert record.task_file == "test_task.md"
        assert record.success is True
        assert record.duration_seconds == 300.5
        assert record.error_summary == "All good"

    def test_audit_record_model_validation_fails_on_missing_required_fields(self):
        """AC 2: Ensures Pydantic validation works for missing required fields."""
        with pytest.raises(ValidationError):
            AuditRecord(
                timestamp=datetime.now().isoformat(),
                task_file="test_task.md",
                story_id="test_story_id",
                success=True,
                duration_seconds=300.5,
                # exit_code is missing
                error_summary=None,
            )
        with pytest.raises(ValidationError):
            AuditRecord(
                timestamp=datetime.now().isoformat(),
                task_file="test_task.md",
                story_id="test_story_id",
                # success is missing
                duration_seconds=300.5,
                exit_code=0,
                error_summary=None,
            )

    def test_audit_record_model_validation_fails_on_invalid_types(self):
        """AC 2: Ensures Pydantic validation works for invalid types."""
        with pytest.raises(ValidationError):
            AuditRecord(
                timestamp=123,  # Invalid type
                task_file="test_task.md",
                story_id="test_story_id",
                success=True,
                duration_seconds=300.5,
                exit_code=0,
                error_summary=None,
            )
        with pytest.raises(ValidationError):
            AuditRecord(
                timestamp=datetime.now().isoformat(),
                task_file=["test_task.md"],  # Invalid type
                story_id="test_story_id",
                success=True,
                duration_seconds=300.5,
                exit_code=0,
                error_summary=None,
            )

    def test_audit_record_model_handles_optional_error_summary(self):
        """AC 2: Verifies error_summary can be None."""
        record_with_error = AuditRecord(
            timestamp=datetime.now().isoformat(),
            task_file="task.md",
            story_id="s1",
            success=False,
            duration_seconds=10.0,
            exit_code=1,
            error_summary="Something went wrong",
        )
        assert record_with_error.error_summary == "Something went wrong"

        record_no_error = AuditRecord(
            timestamp=datetime.now().isoformat(),
            task_file="task.md",
            story_id="s2",
            success=True,
            duration_seconds=5.0,
            exit_code=0,
            error_summary=None,
        )
        assert record_no_error.error_summary is None


class TestAuditJournal:
    """Tests for the AuditJournal class."""

    @patch("os.path.exists", return_value=False)
    def test_audit_journal_initialization_creates_directory_if_not_exists(self, mock_os_path_exists):
        """AC 3: Ensures AuditJournal creates the journal directory if it doesn't exist."""
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            AuditJournal(JOURNAL_FILE)
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_audit_journal_initialization_sets_correct_file_path(self, mock_filesystem_write):
        """AC 3: Ensures AuditJournal can be instantiated and sets the correct file path."""
        m_open, mock_mkdir = mock_filesystem_write
        journal = AuditJournal(JOURNAL_FILE)
        assert journal.journal_file_path == Path(JOURNAL_FILE)

    def test_log_appends_single_record_as_json_line(self, mock_filesystem_write):
        """AC 4: Verifies a single record is written as a correct JSON line."""
        m_open, mock_mkdir = mock_filesystem_write
        journal = AuditJournal(JOURNAL_FILE)
        record = AuditRecord(
            timestamp=datetime(2023, 1, 1, 12, 0, 0).isoformat(),
            task_file="single_task.md",
            story_id="single_story",
            success=True,
            duration_seconds=45.0,
            exit_code=0,
            error_summary=None,
        )
        journal.log(record)

        m_open().write.assert_called_once()
        written_content = m_open().write.call_args[0][0]
        assert written_content == record.model_dump_json() + "\\n"
        # Verify it's valid JSON
        assert json.loads(written_content) == json.loads(record.model_dump_json())

    def test_log_appends_multiple_records_as_json_lines(self, mock_filesystem_write, mock_audit_records):
        """AC 4: Verifies multiple records are written correctly."""
        m_open, mock_mkdir = mock_filesystem_write
        journal = AuditJournal(JOURNAL_FILE)
        for record in mock_audit_records:
            journal.log(record)

        assert m_open().write.call_count == len(mock_audit_records)
        for i, record in enumerate(mock_audit_records):
            expected_jsonl = record.model_dump_json() + "\\n"
            assert m_open().write.call_args_list[i].args[0] == expected_jsonl

    @patch("os.path.exists", return_value=False) # File does not exist initially
    def test_log_creates_journal_file_if_not_exists(self, mock_os_path_exists):
        """AC 4: Ensures journal file is created if it does not exist."""
        with patch("builtins.open", mock_open()) as m_open:
            with patch("pathlib.Path.mkdir", return_value=None):
                journal = AuditJournal(JOURNAL_FILE)
                record = AuditRecord(
                    timestamp=datetime(2023, 1, 1, 12, 0, 0).isoformat(),
                    task_file="new_task.md",
                    story_id="new_story",
                    success=True,
                    duration_seconds=10.0,
                    exit_code=0,
                    error_summary=None,
                )
                journal.log(record)
                m_open.assert_called_with(JOURNAL_FILE, "a", encoding="utf-8")

    def test_query_returns_all_records_no_filter(self, mock_filesystem_read, mock_audit_records):
        """AC 5: Tests query returns all records when no filters are applied."""
        journal = AuditJournal(JOURNAL_FILE)
        results = journal.query()
        assert len(results) == len(mock_audit_records)
        assert all(isinstance(r, AuditRecord) for r in results)
        assert [r.story_id for r in results] == [r.story_id for r in mock_audit_records]

    def test_query_filters_by_success_true(self, mock_filesystem_read):
        """AC 5: Tests query filters records based on success=True status."""
        journal = AuditJournal(JOURNAL_FILE)
        results_success = journal.query(success=True)
        expected_story_ids = ["story_1", "story_3", "story_4"]
        assert [r.story_id for r in results_success] == expected_story_ids

    def test_query_filters_by_success_false(self, mock_filesystem_read):
        """AC 5: Tests query filters records based on success=False status."""
        journal = AuditJournal(JOURNAL_FILE)
        results_failure = journal.query(success=False)
        expected_story_ids = ["story_2"]
        assert [r.story_id for r in results_failure] == expected_story_ids

    def test_query_returns_empty_list_no_matches(self, mock_filesystem_read):
        """AC 5: Tests query returns an empty list if no records match the filters."""
        journal = AuditJournal(JOURNAL_FILE)
        results = journal.query(success=False, task_file="non_existent.md")
        assert len(results) == 0

    def test_query_handles_empty_journal_file(self, mock_empty_journal):
        """AC 5: Tests query on an empty journal file."""
        journal = AuditJournal(JOURNAL_FILE)
        results = journal.query()
        assert len(results) == 0

    def test_query_skips_malformed_json_lines(self):
        """AC 5: Tests that query gracefully handles and skips malformed JSON lines."""
        # A valid record, a malformed JSON line, another valid record
        malformed_content = [
            AuditRecord(
                timestamp=datetime(2023, 1, 1, 10, 0, 0).isoformat(),
                task_file="task_A.md",
                story_id="story_1",
                success=True,
                duration_seconds=120.5,
                exit_code=0,
                error_summary=None,
            ).model_dump_json() + "\\n",
            "{\\\"invalid_json\\\": \\\"missing_brace\\\"}\\n",
            AuditRecord(
                timestamp=datetime(2023, 1, 1, 11, 0, 0).isoformat(),
                task_file="task_B.md",
                story_id="story_2",
                success=False,
                duration_seconds=60.0,
                exit_code=1,
                error_summary="Design phase failed",
            ).model_dump_json() + "\\n",
        ]
        with patch("builtins.open", mock_open(read_data="".join(malformed_content))) as m_open:
            with patch("os.path.exists", return_value=True):
                journal = AuditJournal(JOURNAL_FILE)
                results = journal.query()

            assert len(results) == 2  # Only the two valid records should be returned
            assert results[0].story_id == "story_1"
            assert results[1].story_id == "story_2"

    def test_summary_calculates_correct_statistics_multiple_records(self, mock_filesystem_read):
        """AC 6: Verifies all aggregate statistics are correct for a set of records."""
        journal = AuditJournal(JOURNAL_FILE)
        summary = journal.summary()

        assert summary["total_count"] == 4
        assert summary["successful_count"] == 3
        assert summary["failed_count"] == 1
        assert summary["success_rate"] == 75.0
        assert pytest.approx(summary["average_duration_seconds"], 0.01) == (120.5 + 60.0 + 180.0 + 90.0) / 4

    def test_summary_handles_empty_journal_file(self, mock_empty_journal):
        """AC 6: Tests summary on an empty journal file."""
        journal = AuditJournal(JOURNAL_FILE)
        summary = journal.summary()

        assert summary["total_count"] == 0
        assert summary["successful_count"] == 0
        assert summary["failed_count"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["average_duration_seconds"] == 0.0

    def test_summary_handles_single_record(self):
        """AC 6: Tests summary calculation for a single record."""
        record = AuditRecord(
            timestamp=datetime(2023, 1, 1, 10, 0, 0).isoformat(),
            task_file="single.md",
            story_id="s1",
            success=True,
            duration_seconds=100.0,
            exit_code=0,
            error_summary=None,
        )
        jsonl_content = record.model_dump_json() + "\\n"
        with patch("builtins.open", mock_open(read_data=jsonl_content)) as m_open:
            with patch("os.path.exists", return_value=True):
                journal = AuditJournal(JOURNAL_FILE)
                summary = journal.summary()

            assert summary["total_count"] == 1
            assert summary["successful_count"] == 1
            assert summary["failed_count"] == 0
            assert summary["success_rate"] == 100.0
            assert summary["average_duration_seconds"] == 100.0

    def test_summary_calculates_success_rate_correctly_mixed_results(self):
        """AC 6: Specific check for success rate with mixed results."""
        records = [
            AuditRecord(timestamp=datetime.now().isoformat(), task_file="t1", story_id="s1", success=True, duration_seconds=10.0, exit_code=0, error_summary=None),
            AuditRecord(timestamp=datetime.now().isoformat(), task_file="t2", story_id="s2", success=False, duration_seconds=10.0, exit_code=1, error_summary="Fail"),
            AuditRecord(timestamp=datetime.now().isoformat(), task_file="t3", story_id="s3", success=True, duration_seconds=10.0, exit_code=0, error_summary=None),
        ]
        jsonl_content = "\\n".join(r.model_dump_json() for r in records) + "\\n"
        with patch("builtins.open", mock_open(read_data=jsonl_content)) as m_open:
            with patch("os.path.exists", return_value=True):
                journal = AuditJournal(JOURNAL_FILE)
                summary = journal.summary()
            assert pytest.approx(summary["success_rate"], 0.01) == (2/3) * 100

# Ensure that the test suite fails if any test fails
if __name__ == "__main__":
    pytest.main([__file__])
    sys.exit(0) # Pytest itself handles exit codes, so ensure this script returns 0 if pytest is called, or 1 if invoked directly and tests fail (though we expect ModuleNotFoundError)
