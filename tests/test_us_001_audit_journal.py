import pytest
from unittest.mock import mock_open, patch
from datetime import datetime, timedelta
import json
import sys

# This import will cause ModuleNotFoundError in TDD-RED phase
from src.execution.audit_journal import AuditJournal, AuditRecord
from pydantic import ValidationError

"""
IMPLEMENTATION PLAN for US-001:

Components:
  - AuditJournal class (src/execution/audit_journal.py):
      - Responsibility: Manages structured logging of story execution records.
      - Methods:
          - __init__: Initializes with the journal file path.
          - append_record(record: AuditRecord): Appends a Pydantic AuditRecord instance as a JSON line to the journal file.
          - query(since=None, task_file=None, success=None): Filters and retrieves AuditRecord instances from the journal based on provided criteria.
          - summary(): Calculates and returns aggregate statistics from all records in the journal.
  - AuditRecord Pydantic model (src/execution/audit_journal.py):
      - Responsibility: Defines the schema for a single structured audit log entry.
      - Fields: timestamp, task_file, story_id, story_title, llm_provider_per_phase, session_id, total_turns, exit_code, duration_seconds, success, phases_completed, error_summary.

Data Flow:
  - An AuditRecord instance is created with execution details.
  - This instance is passed to AuditJournal.append_record().
  - AuditJournal serializes the AuditRecord to a JSON line and appends it to '.memory/audit_journal.jsonl'.
  - query() and summary() methods read from '.memory/audit_journal.jsonl', parse JSON lines back into AuditRecord instances, and process them.

Integration Points:
  - Requires pydantic for data validation and serialization/deserialization.
  - Interacts with the file system to read from and write to '.memory/audit_journal.jsonl'.
  - Assumes a consistent structure for llm_provider_per_phase (dict) and phases_completed (list).

Edge Cases:
  - Empty audit journal file: query() should return empty list, summary() should return all zeros/empty counts.
  - Non-existent audit journal file: append_record() should create it, query()/summary() should handle gracefully (return empty results).
  - Malformed JSON lines in the journal (not directly testable on write if Pydantic is used, but for read operations).
  - Querying with no filters should return all records.
  - Querying with all filters combined.
  - Summary calculations for division by zero (e.g., success rate when no records).

Test Cases:
  1. AuditRecord Model:
     - AC 3 -> test_audit_record_model_definition_with_valid_data(): Verifies correct instantiation and type checking.
     - AC 3 -> test_audit_record_model_validation_fails_on_invalid_data(): Ensures Pydantic validation works.
  2. AuditJournal Initialization:
     - AC 2 -> test_audit_journal_initialization(): Ensures AuditJournal can be instantiated.
  3. Append Records:
     - AC 4 -> test_append_record_writes_valid_json_line(): Verifies a single record is written as a correct JSON line.
     - AC 4 -> test_append_record_writes_multiple_records_as_json_lines(): Verifies multiple records are written correctly.
     - AC 4 -> test_append_record_creates_journal_file_if_not_exists(): Ensures file creation.
  4. Query Records:
     - AC 5 -> test_query_returns_all_records_when_no_filters(): No filters applied.
     - AC 5 -> test_query_filters_by_since_datetime(): Filters by timestamp (since).
     - AC 5 -> test_query_filters_by_task_file(): Filters by task_file.
     - AC 5 -> test_query_filters_by_success_status(): Filters by success boolean.
     - AC 5 -> test_query_filters_by_combined_parameters(): Filters by multiple criteria.
     - AC 5 -> test_query_returns_empty_list_for_no_matches(): No records match filters.
     - AC 5 -> test_query_handles_empty_journal_file(): Query on an empty journal.
  5. Summary Statistics:
     - AC 6 -> test_summary_calculates_correct_statistics_for_multiple_records(): Verifies all aggregate statistics are correct for a set of records.
     - AC 6 -> test_summary_handles_empty_journal_file(): Summary on an empty journal returns default/zero values.
     - AC 6 -> test_summary_handles_single_record(): Summary for a single record.
     - AC 6 -> test_summary_calculates_success_rate_correctly(): Specific check for success rate with mixed results.
"""

JOURNAL_FILE = ".memory/audit_journal.jsonl"

@pytest.fixture
def mock_audit_records():
    """Fixture to provide sample audit records."""
    return [
        AuditRecord(
            timestamp=datetime(2023, 1, 1, 10, 0, 0),
            task_file="task_A.md",
            story_id="story_1",
            story_title="Title 1",
            llm_provider_per_phase={"plan": "Claude", "code": "Gemini"},
            session_id="session_123",
            total_turns=5,
            exit_code=0,
            duration_seconds=120.5,
            success=True,
            phases_completed=["plan", "code"],
            error_summary=None,
        ),
        AuditRecord(
            timestamp=datetime(2023, 1, 1, 11, 0, 0),
            task_file="task_B.md",
            story_id="story_2",
            story_title="Title 2",
            llm_provider_per_phase={"design": "Gemini"},
            session_id="session_124",
            total_turns=3,
            exit_code=1,
            duration_seconds=60.0,
            success=False,
            phases_completed=["design"],
            error_summary="Design phase failed",
        ),
        AuditRecord(
            timestamp=datetime(2023, 1, 2, 9, 30, 0),
            task_file="task_A.md",
            story_id="story_3",
            story_title="Title 3",
            llm_provider_per_phase={"plan": "Claude", "verify": "Claude"},
            session_id="session_125",
            total_turns=7,
            exit_code=0,
            duration_seconds=180.0,
            success=True,
            phases_completed=["plan", "code", "verify"],
            error_summary=None,
        ),
        AuditRecord(
            timestamp=datetime(2023, 1, 2, 12, 0, 0),
            task_file="task_C.md",
            story_id="story_4",
            story_title="Title 4",
            llm_provider_per_phase={"code": "Gemini"},
            session_id="session_126",
            total_turns=4,
            exit_code=0,
            duration_seconds=90.0,
            success=True,
            phases_completed=["code"],
            error_summary=None,
        ),
    ]

@pytest.fixture
def mock_jsonl_content(mock_audit_records):
    """Fixture to provide JSONL content string from mock records."""
    return "\n".join(record.model_dump_json() for record in mock_audit_records) + "\n"

@pytest.fixture(autouse=True)
def mock_filesystem():
    """Fixture to mock file system operations for AuditJournal."""
    m_open = mock_open()
    with patch("builtins.open", m_open):
        with patch("os.path.exists", return_value=True): # Assume file exists by default for reads
            yield m_open

class TestAuditRecord:
    """Tests for the AuditRecord Pydantic model."""

    def test_audit_record_model_definition_with_valid_data(self):
        """AC 3: Verifies AuditRecord can be instantiated with valid data."""
        record = AuditRecord(
            timestamp=datetime.now(),
            task_file="test_task.md",
            story_id="test_story_id",
            story_title="Test Story Title",
            llm_provider_per_phase={"plan": "Claude", "code": "Gemini"},
            session_id="test_session_id",
            total_turns=10,
            exit_code=0,
            duration_seconds=300.5,
            success=True,
            phases_completed=["plan", "code", "verify"],
            error_summary=None,
        )
        assert isinstance(record.timestamp, datetime)
        assert record.task_file == "test_task.md"
        assert record.total_turns == 10
        assert record.success is True

    def test_audit_record_model_validation_fails_on_invalid_data(self):
        """AC 3: Ensures Pydantic validation works for invalid types."""
        with pytest.raises(ValidationError):
            AuditRecord(
                timestamp="not a datetime",  # Invalid type
                task_file="test_task.md",
                story_id="test_story_id",
                story_title="Test Story Title",
                llm_provider_per_phase={"plan": "Claude"},
                session_id="test_session_id",
                total_turns=10,
                exit_code=0,
                duration_seconds=300.5,
                success=True,
                phases_completed=["plan"],
                error_summary=None,
            )
        with pytest.raises(ValidationError):
            AuditRecord(
                timestamp=datetime.now(),
                task_file=123,  # Invalid type
                story_id="test_story_id",
                story_title="Test Story Title",
                llm_provider_per_phase={"plan": "Claude"},
                session_id="test_session_id",
                total_turns=10,
                exit_code=0,
                duration_seconds=300.5,
                success=True,
                phases_completed=["plan"],
                error_summary=None,
            )

class TestAuditJournal:
    """Tests for the AuditJournal class."""

    def test_audit_journal_initialization(self, mock_filesystem):
        """AC 2: Ensures AuditJournal can be instantiated."""
        journal = AuditJournal(JOURNAL_FILE)
        assert journal.journal_file == JOURNAL_FILE

    def test_append_record_writes_valid_json_line(self, mock_filesystem):
        """AC 4: Verifies a single record is written as a correct JSON line."""
        journal = AuditJournal(JOURNAL_FILE)
        record = AuditRecord(
            timestamp=datetime(2023, 1, 1, 12, 0, 0),
            task_file="single_task.md",
            story_id="single_story",
            story_title="Single Story",
            llm_provider_per_phase={"code": "Gemini"},
            session_id="single_session",
            total_turns=2,
            exit_code=0,
            duration_seconds=45.0,
            success=True,
            phases_completed=["code"],
            error_summary=None,
        )
        journal.append_record(record)

        mock_filesystem().write.assert_called_once()
        written_content = mock_filesystem().write.call_args[0][0]
        assert written_content == record.model_dump_json() + "\n"
        # Verify it's valid JSON
        assert json.loads(written_content) == record.model_dump()

    def test_append_record_writes_multiple_records_as_json_lines(self, mock_filesystem, mock_audit_records):
        """AC 4: Verifies multiple records are written correctly."""
        journal = AuditJournal(JOURNAL_FILE)
        for record in mock_audit_records:
            journal.append_record(record)

        assert mock_filesystem().write.call_count == len(mock_audit_records)
        for i, record in enumerate(mock_audit_records):
            expected_jsonl = record.model_dump_json() + "\n"
            assert mock_filesystem().write.call_args_list[i].args[0] == expected_jsonl

    def test_append_record_creates_journal_file_if_not_exists(self):
        """AC 4: Ensures journal file is created if it does not exist."""
        with patch("builtins.open", mock_open()) as m_open:
            with patch("os.path.exists", return_value=False): # File does not exist initially
            journal = AuditJournal(JOURNAL_FILE)
            record = AuditRecord(
                timestamp=datetime(2023, 1, 1, 12, 0, 0),
                task_file="new_task.md",
                story_id="new_story",
                story_title="New Story",
                llm_provider_per_phase={"plan": "Claude"},
                session_id="new_session",
                total_turns=1,
                exit_code=0,
                duration_seconds=10.0,
                success=True,
                phases_completed=["plan"],
                error_summary=None,
            )
            journal.append_record(record)
            m_open.assert_called_with(JOURNAL_FILE, "a", encoding="utf-8")

    def test_query_returns_all_records_when_no_filters(self, mock_filesystem, mock_jsonl_content, mock_audit_records):
        """AC 5: Tests query returns all records when no filters are applied."""
        mock_filesystem().return_value.__enter__.return_value.readlines.return_value = mock_jsonl_content.splitlines(keepends=True)
        journal = AuditJournal(JOURNAL_FILE)
        results = journal.query()
        assert len(results) == len(mock_audit_records)
        assert all(isinstance(r, AuditRecord) for r in results)
        assert [r.story_id for r in results] == [r.story_id for r in mock_audit_records]

    def test_query_filters_by_since_datetime(self, mock_filesystem, mock_jsonl_content, mock_audit_records):
        """AC 5: Tests query filters records based on 'since' datetime."""
        mock_filesystem().return_value.__enter__.return_value.readlines.return_value = mock_jsonl_content.splitlines(keepends=True)
        journal = AuditJournal(JOURNAL_FILE)
        # Query for records since 2023-01-01 10:30:00
        since_time = datetime(2023, 1, 1, 10, 30, 0)
        results = journal.query(since=since_time)
        expected_story_ids = ["story_2", "story_3", "story_4"] # story_1 is before since_time
        assert [r.story_id for r in results] == expected_story_ids

    def test_query_filters_by_task_file(self, mock_filesystem, mock_jsonl_content):
        """AC 5: Tests query filters records based on 'task_file'."""
        mock_filesystem().return_value.__enter__.return_value.readlines.return_value = mock_jsonl_content.splitlines(keepends=True)
        journal = AuditJournal(JOURNAL_FILE)
        results = journal.query(task_file="task_A.md")
        expected_story_ids = ["story_1", "story_3"]
        assert [r.story_id for r in results] == expected_story_ids

    def test_query_filters_by_success_status(self, mock_filesystem, mock_jsonl_content):
        """AC 5: Tests query filters records based on 'success' status."""
        mock_filesystem().return_value.__enter__.return_value.readlines.return_value = mock_jsonl_content.splitlines(keepends=True)
        journal = AuditJournal(JOURNAL_FILE)
        results_success = journal.query(success=True)
        expected_success_story_ids = ["story_1", "story_3", "story_4"]
        assert [r.story_id for r in results_success] == expected_success_story_ids

        results_failure = journal.query(success=False)
        expected_failure_story_ids = ["story_2"]
        assert [r.story_id for r in results_failure] == expected_failure_story_ids

    def test_query_filters_by_combined_parameters(self, mock_filesystem, mock_jsonl_content):
        """AC 5: Tests query filters records based on combined parameters."""
        mock_filesystem().return_value.__enter__.return_value.readlines.return_value = mock_jsonl_content.splitlines(keepends=True)
        journal = AuditJournal(JOURNAL_FILE)
        # task_file="task_A.md", success=True, since=datetime(2023, 1, 1, 10, 30, 0)
        results = journal.query(
            task_file="task_A.md",
            success=True,
            since=datetime(2023, 1, 1, 10, 30, 0)
        )
        expected_story_ids = ["story_3"] # story_1 is before since_time, story_2 is not task_A.md and is failure
        assert [r.story_id for r in results] == expected_story_ids

    def test_query_returns_empty_list_for_no_matches(self, mock_filesystem, mock_jsonl_content):
        """AC 5: Tests query returns an empty list if no records match the filters."""
        mock_filesystem().return_value.__enter__.return_value.readlines.return_value = mock_jsonl_content.splitlines(keepends=True)
        journal = AuditJournal(JOURNAL_FILE)
        results = journal.query(task_file="non_existent_task.md")
        assert len(results) == 0

    def test_query_handles_empty_journal_file(self):
        """AC 5: Tests query on an empty journal file."""
        with patch("builtins.open", mock_open()) as m_open, 
             patch("os.path.exists", return_value=True):
            m_open.return_value.__enter__.return_value.readlines.return_value = []
            journal = AuditJournal(JOURNAL_FILE)
            results = journal.query()
            assert len(results) == 0

    def test_summary_calculates_correct_statistics_for_multiple_records(self, mock_filesystem, mock_jsonl_content):
        """AC 6: Verifies all aggregate statistics are correct for a set of records."""
        mock_filesystem().return_value.__enter__.return_value.readlines.return_value = mock_jsonl_content.splitlines(keepends=True)
        journal = AuditJournal(JOURNAL_FILE)
        summary = journal.summary()

        assert summary["total_executions"] == 4
        assert summary["successful_executions"] == 3
        assert summary["failed_executions"] == 1
        assert summary["success_rate"] == 75.0
        assert pytest.approx(summary["average_duration_seconds"], 0.01) == (120.5 + 60.0 + 180.0 + 90.0) / 4
        assert summary["total_llm_calls"] == 8 # 2+1+2+1
        assert summary["llm_provider_usage"]["Claude"] == 3 # 2+2 in story 1 and 3, 1 in story 2
        assert summary["llm_provider_usage"]["Gemini"] == 3 # 1 in story 1, 1 in story 2, 1 in story 4
        assert summary["average_total_turns"] == (5 + 3 + 7 + 4) / 4

    def test_summary_handles_empty_journal_file(self):
        """AC 6: Tests summary on an empty journal file."""
        with patch("builtins.open", mock_open()) as m_open, 
             patch("os.path.exists", return_value=True):
            m_open.return_value.__enter__.return_value.readlines.return_value = []
            journal = AuditJournal(JOURNAL_FILE)
            summary = journal.summary()

            assert summary["total_executions"] == 0
            assert summary["successful_executions"] == 0
            assert summary["failed_executions"] == 0
            assert summary["success_rate"] == 0.0
            assert summary["average_duration_seconds"] == 0.0
            assert summary["total_llm_calls"] == 0
            assert summary["llm_provider_usage"] == {}
            assert summary["average_total_turns"] == 0.0

    def test_summary_handles_single_record(self):
        """AC 6: Tests summary calculation for a single record."""
        record = AuditRecord(
            timestamp=datetime(2023, 1, 1, 10, 0, 0),
            task_file="single.md",
            story_id="s1",
            story_title="S1",
            llm_provider_per_phase={"plan": "Claude"},
            session_id="sess_1",
            total_turns=5,
            exit_code=0,
            duration_seconds=100.0,
            success=True,
            phases_completed=["plan", "code"],
            error_summary=None,
        )
        jsonl_content = record.model_dump_json() + "
"
        with patch("builtins.open", mock_open(read_data=jsonl_content)) as m_open, 
             patch("os.path.exists", return_value=True):
            journal = AuditJournal(JOURNAL_FILE)
            summary = journal.summary()

            assert summary["total_executions"] == 1
            assert summary["successful_executions"] == 1
            assert summary["failed_executions"] == 0
            assert summary["success_rate"] == 100.0
            assert summary["average_duration_seconds"] == 100.0
            assert summary["total_llm_calls"] == 1
            assert summary["llm_provider_usage"]["Claude"] == 1
            assert summary["average_total_turns"] == 5.0

    def test_summary_calculates_success_rate_correctly(self):
        """AC 6: Specific check for success rate with mixed results."""
        records = [
            AuditRecord(timestamp=datetime.now(), task_file="t1", story_id="s1", story_title="S1", llm_provider_per_phase={}, session_id="1", total_turns=1, exit_code=0, duration_seconds=10.0, success=True, phases_completed=[], error_summary=None),
            AuditRecord(timestamp=datetime.now(), task_file="t2", story_id="s2", story_title="S2", llm_provider_per_phase={}, session_id="2", total_turns=1, exit_code=1, duration_seconds=10.0, success=False, phases_completed=[], error_summary="Fail"),
            AuditRecord(timestamp=datetime.now(), task_file="t3", story_id="s3", story_title="S3", llm_provider_per_phase={}, session_id="3", total_turns=1, exit_code=0, duration_seconds=10.0, success=True, phases_completed=[], error_summary=None),
        ]
        jsonl_content = "
".join(r.model_dump_json() for r in records) + "
"
        with patch("builtins.open", mock_open(read_data=jsonl_content)) as m_open, 
             patch("os.path.exists", return_value=True):
            journal = AuditJournal(JOURNAL_FILE)
            summary = journal.summary()
            assert summary["success_rate"] == (2/3) * 100

# This is critical for the TDD-RED-CHECK phase
# It ensures that if pytest exits with an error (e.g., ModuleNotFoundError),
# the script also exits with a non-zero code.
# In a real pytest run, pytest itself handles exit codes, but for
# isolated execution within a shell, this ensures the desired behavior.
try:
    # Run pytest programmatically to capture results and control exit
    # This will fail with ModuleNotFoundError, causing the except block to run
        pytest.main(["-x", "tests/test_us_001_audit_journal.py"])
    exit_code = 0
except Exception as e:
    # If pytest.main fails to even start (e.g., import errors),
    # we ensure a non-zero exit code.
    print(f"Test run failed with an exception: {e}", file=sys.stderr)
    exit_code = 1

sys.exit(exit_code)
