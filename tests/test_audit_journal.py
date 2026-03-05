"""
Tests for AuditJournal — audit journaling module (Phase 2 item 2.10).

Uses tmp_path fixtures instead of mock_open for reliable JSONL line iteration.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.execution.audit_journal import AuditJournal, AuditRecord


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
def journal_path(tmp_path):
    """Provide a temporary journal file path."""
    return str(tmp_path / "audit_journal.jsonl")


@pytest.fixture
def populated_journal(journal_path, mock_audit_records):
    """Create a journal pre-populated with test records."""
    journal = AuditJournal(journal_path)
    for record in mock_audit_records:
        journal.log(record)
    return journal


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

    def test_audit_journal_initialization_creates_directory_if_not_exists(self, tmp_path):
        """AC 3: Ensures AuditJournal creates the journal directory if it doesn't exist."""
        nested_path = str(tmp_path / "nested" / "dir" / "journal.jsonl")
        AuditJournal(nested_path)
        assert os.path.isdir(os.path.dirname(nested_path))

    def test_audit_journal_initialization_sets_correct_file_path(self, journal_path):
        """AC 3: Ensures AuditJournal sets the correct file path."""
        journal = AuditJournal(journal_path)
        assert journal.journal_file_path == Path(journal_path)

    def test_log_appends_single_record_as_json_line(self, journal_path):
        """AC 4: Verifies a single record is written as a correct JSON line."""
        journal = AuditJournal(journal_path)
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

        with open(journal_path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["story_id"] == "single_story"

    def test_log_appends_multiple_records_as_json_lines(self, journal_path, mock_audit_records):
        """AC 4: Verifies multiple records are written correctly."""
        journal = AuditJournal(journal_path)
        for record in mock_audit_records:
            journal.log(record)

        with open(journal_path) as f:
            lines = f.readlines()
        assert len(lines) == len(mock_audit_records)
        for i, line in enumerate(lines):
            parsed = json.loads(line)
            assert parsed["story_id"] == mock_audit_records[i].story_id

    def test_log_creates_journal_file_if_not_exists(self, tmp_path):
        """AC 4: Ensures journal file is created if it does not exist."""
        path = str(tmp_path / "new_journal.jsonl")
        assert not os.path.exists(path)
        journal = AuditJournal(path)
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
        assert os.path.exists(path)

    def test_query_returns_all_records_no_filter(self, populated_journal, mock_audit_records):
        """AC 5: Tests query returns all records when no filters are applied."""
        results = populated_journal.query()
        assert len(results) == len(mock_audit_records)
        assert all(isinstance(r, AuditRecord) for r in results)
        assert [r.story_id for r in results] == [r.story_id for r in mock_audit_records]

    def test_query_filters_by_success_true(self, populated_journal):
        """AC 5: Tests query filters records based on success=True status."""
        results = populated_journal.query(success=True)
        expected_story_ids = ["story_1", "story_3", "story_4"]
        assert [r.story_id for r in results] == expected_story_ids

    def test_query_filters_by_success_false(self, populated_journal):
        """AC 5: Tests query filters records based on success=False status."""
        results = populated_journal.query(success=False)
        assert [r.story_id for r in results] == ["story_2"]

    def test_query_returns_empty_list_no_matches(self, populated_journal):
        """AC 5: Tests query returns an empty list if no records match the filters."""
        results = populated_journal.query(success=False, task_file="non_existent.md")
        assert len(results) == 0

    def test_query_handles_empty_journal_file(self, journal_path):
        """AC 5: Tests query on an empty journal file."""
        journal = AuditJournal(journal_path)
        results = journal.query()
        assert len(results) == 0

    def test_query_skips_malformed_json_lines(self, journal_path):
        """AC 5: Tests that query gracefully handles and skips malformed JSON lines."""
        record1 = AuditRecord(
            timestamp=datetime(2023, 1, 1, 10, 0, 0).isoformat(),
            task_file="task_A.md", story_id="story_1", success=True,
            duration_seconds=120.5, exit_code=0, error_summary=None,
        )
        record2 = AuditRecord(
            timestamp=datetime(2023, 1, 1, 11, 0, 0).isoformat(),
            task_file="task_B.md", story_id="story_2", success=False,
            duration_seconds=60.0, exit_code=1, error_summary="Design phase failed",
        )
        with open(journal_path, "w") as f:
            f.write(record1.model_dump_json() + "\n")
            f.write('{"invalid_json": "missing_brace"\n')
            f.write(record2.model_dump_json() + "\n")

        journal = AuditJournal(journal_path)
        results = journal.query()
        assert len(results) == 2
        assert results[0].story_id == "story_1"
        assert results[1].story_id == "story_2"

    def test_summary_calculates_correct_statistics_multiple_records(self, populated_journal):
        """AC 6: Verifies all aggregate statistics are correct."""
        summary = populated_journal.summary()
        assert summary["total_count"] == 4
        assert summary["successful_count"] == 3
        assert summary["failed_count"] == 1
        assert summary["success_rate"] == 75.0
        assert pytest.approx(summary["average_duration_seconds"], 0.01) == (120.5 + 60.0 + 180.0 + 90.0) / 4

    def test_summary_handles_empty_journal_file(self, journal_path):
        """AC 6: Tests summary on an empty journal file."""
        journal = AuditJournal(journal_path)
        summary = journal.summary()
        assert summary["total_count"] == 0
        assert summary["successful_count"] == 0
        assert summary["failed_count"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["average_duration_seconds"] == 0.0

    def test_summary_handles_single_record(self, journal_path):
        """AC 6: Tests summary calculation for a single record."""
        journal = AuditJournal(journal_path)
        record = AuditRecord(
            timestamp=datetime(2023, 1, 1, 10, 0, 0).isoformat(),
            task_file="single.md", story_id="s1", success=True,
            duration_seconds=100.0, exit_code=0, error_summary=None,
        )
        journal.log(record)
        summary = journal.summary()
        assert summary["total_count"] == 1
        assert summary["successful_count"] == 1
        assert summary["failed_count"] == 0
        assert summary["success_rate"] == 100.0
        assert summary["average_duration_seconds"] == 100.0

    def test_summary_calculates_success_rate_correctly_mixed_results(self, journal_path):
        """AC 6: Specific check for success rate with mixed results."""
        journal = AuditJournal(journal_path)
        records = [
            AuditRecord(timestamp=datetime.now().isoformat(), task_file="t1", story_id="s1", success=True, duration_seconds=10.0, exit_code=0, error_summary=None),
            AuditRecord(timestamp=datetime.now().isoformat(), task_file="t2", story_id="s2", success=False, duration_seconds=10.0, exit_code=1, error_summary="Fail"),
            AuditRecord(timestamp=datetime.now().isoformat(), task_file="t3", story_id="s3", success=True, duration_seconds=10.0, exit_code=0, error_summary=None),
        ]
        for r in records:
            journal.log(r)
        summary = journal.summary()
        assert pytest.approx(summary["success_rate"], 0.01) == (2/3) * 100
