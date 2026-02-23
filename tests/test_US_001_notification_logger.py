"""
Tests for src.utils.notification_logger — NotificationLogger utility for logging notifications.

IMPLEMENTATION PLAN for US-001:

Components:
  - NotificationLog: A dataclass with timestamp (datetime), event (str), level (str), details (str)
    - level must be constrained to 'info', 'warn', or 'error' values
  - NotificationLogger: A class that manages a collection of notification logs
    - log(event, level, details) - appends a new NotificationLog with current UTC timestamp
    - get_logs(level=None) - returns all logs, or filters by level if provided
    - save(filepath) - writes logs as JSONL (one JSON object per line)
    - load(filepath) - reads logs from JSONL file and replaces in-memory logs

Test Cases:
  1. AC1: NotificationLog dataclass exists with timestamp, event, level, details fields
  2. AC2: level field is restricted to info/warn/error values
  3. AC3: NotificationLogger.log() creates entries with current UTC timestamp
  4. AC4: NotificationLogger.get_logs() returns all logs when no filter given
  5. AC5: NotificationLogger.get_logs(level='warn') returns only warn-level logs
  6. AC6: NotificationLogger.save(filepath) writes valid JSONL where each line is a JSON object
  7. AC7: NotificationLogger.load(filepath) restores logs from a JSONL file
  8. AC8: Module is importable from src.utils.notification_logger

Edge Cases:
  - get_logs() on empty logger returns empty list
  - Invalid level values raise ValueError or similar
  - Filtering by multiple level types
  - Loading non-existent file (should raise error)
  - Saving to path (creates if needed)
"""

import pytest
import json
import tempfile
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.utils.notification_logger import NotificationLog, NotificationLogger


class TestNotificationLogDataclass:
    """Tests for NotificationLog dataclass."""

    def test_notification_log_exists_and_is_dataclass(self):
        """AC1: NotificationLog dataclass exists with required fields."""
        # Create a log entry to verify it exists
        timestamp = datetime.utcnow()
        log = NotificationLog(
            timestamp=timestamp,
            event="test_event",
            level="info",
            details="test details"
        )
        assert log.timestamp == timestamp
        assert log.event == "test_event"
        assert log.level == "info"
        assert log.details == "test details"

    def test_notification_log_has_timestamp_field(self):
        """AC1: NotificationLog has timestamp field as datetime."""
        timestamp = datetime.utcnow()
        log = NotificationLog(
            timestamp=timestamp,
            event="test",
            level="info",
            details="details"
        )
        assert isinstance(log.timestamp, datetime)
        assert log.timestamp == timestamp

    def test_notification_log_has_event_field(self):
        """AC1: NotificationLog has event field as string."""
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test_event_name",
            level="info",
            details="details"
        )
        assert log.event == "test_event_name"
        assert isinstance(log.event, str)

    def test_notification_log_has_level_field(self):
        """AC1: NotificationLog has level field as string."""
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test",
            level="warn",
            details="details"
        )
        assert log.level == "warn"
        assert isinstance(log.level, str)

    def test_notification_log_has_details_field(self):
        """AC1: NotificationLog has details field as string."""
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test",
            level="info",
            details="detailed information"
        )
        assert log.details == "detailed information"
        assert isinstance(log.details, str)

    def test_level_field_accepts_info(self):
        """AC2: level field accepts 'info' value."""
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test",
            level="info",
            details="details"
        )
        assert log.level == "info"

    def test_level_field_accepts_warn(self):
        """AC2: level field accepts 'warn' value."""
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test",
            level="warn",
            details="details"
        )
        assert log.level == "warn"

    def test_level_field_accepts_error(self):
        """AC2: level field accepts 'error' value."""
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test",
            level="error",
            details="details"
        )
        assert log.level == "error"

    def test_level_field_rejects_invalid_value(self):
        """AC2: level field rejects values other than info/warn/error."""
        with pytest.raises((ValueError, TypeError)):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test",
                level="debug",
                details="details"
            )

    def test_level_field_rejects_uppercase_value(self):
        """AC2: level field rejects uppercase values like 'INFO'."""
        with pytest.raises((ValueError, TypeError)):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test",
                level="INFO",
                details="details"
            )

    def test_level_field_rejects_invalid_case_variants(self):
        """AC2: level field rejects invalid case variants."""
        with pytest.raises((ValueError, TypeError)):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test",
                level="Warn",
                details="details"
            )


class TestNotificationLogger:
    """Tests for NotificationLogger class."""

    @pytest.fixture
    def logger(self):
        """Create a fresh NotificationLogger instance for each test."""
        return NotificationLogger()

    def test_notification_logger_class_exists(self, logger):
        """Verify NotificationLogger class can be instantiated."""
        assert logger is not None
        assert isinstance(logger, NotificationLogger)

    def test_log_method_exists(self, logger):
        """Verify NotificationLogger has log method."""
        assert hasattr(logger, 'log')
        assert callable(logger.log)

    def test_get_logs_method_exists(self, logger):
        """Verify NotificationLogger has get_logs method."""
        assert hasattr(logger, 'get_logs')
        assert callable(logger.get_logs)

    def test_save_method_exists(self, logger):
        """Verify NotificationLogger has save method."""
        assert hasattr(logger, 'save')
        assert callable(logger.save)

    def test_load_method_exists(self, logger):
        """Verify NotificationLogger has load method."""
        assert hasattr(logger, 'load')
        assert callable(logger.load)

    # AC3: NotificationLogger.log() creates entries with current UTC timestamp
    def test_log_creates_notification_with_timestamp(self, logger):
        """AC3: log() creates entries with current UTC timestamp."""
        before = datetime.utcnow()
        logger.log("test_event", "info", "test details")
        after = datetime.utcnow()

        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0].timestamp >= before
        assert logs[0].timestamp <= after

    def test_log_stores_event(self, logger):
        """AC3: log() stores the event message."""
        logger.log("my_event", "info", "details")
        logs = logger.get_logs()
        assert logs[0].event == "my_event"

    def test_log_stores_level(self, logger):
        """AC3: log() stores the level."""
        logger.log("event", "warn", "details")
        logs = logger.get_logs()
        assert logs[0].level == "warn"

    def test_log_stores_details(self, logger):
        """AC3: log() stores the details."""
        logger.log("event", "info", "detailed message")
        logs = logger.get_logs()
        assert logs[0].details == "detailed message"

    def test_log_creates_multiple_entries(self, logger):
        """AC3: log() can be called multiple times to create multiple entries."""
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")
        logs = logger.get_logs()
        assert len(logs) == 3

    def test_log_timestamps_are_sequential(self, logger):
        """AC3: Multiple log entries have sequential or equal timestamps."""
        logger.log("event1", "info", "details1")
        log1_time = logger.get_logs()[0].timestamp

        logger.log("event2", "warn", "details2")
        log2_time = logger.get_logs()[1].timestamp

        assert log2_time >= log1_time

    # AC4: NotificationLogger.get_logs() returns all logs when no filter given
    def test_get_logs_returns_empty_list_when_no_logs(self, logger):
        """AC4: get_logs() returns empty list when no logs have been added."""
        logs = logger.get_logs()
        assert isinstance(logs, list)
        assert len(logs) == 0

    def test_get_logs_returns_all_logs_without_filter(self, logger):
        """AC4: get_logs() returns all logs when no filter given."""
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")

        logs = logger.get_logs()
        assert len(logs) == 3
        assert logs[0].event == "event1"
        assert logs[1].event == "event2"
        assert logs[2].event == "event3"

    def test_get_logs_returns_notification_log_objects(self, logger):
        """AC4: get_logs() returns NotificationLog objects."""
        logger.log("event", "info", "details")
        logs = logger.get_logs()
        assert len(logs) == 1
        assert isinstance(logs[0], NotificationLog)

    # AC5: NotificationLogger.get_logs(level='warn') returns only warn-level logs
    def test_get_logs_filters_by_info_level(self, logger):
        """AC5: get_logs(level='info') returns only info-level logs."""
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "info", "details3")

        logs = logger.get_logs(level="info")
        assert len(logs) == 2
        assert all(log.level == "info" for log in logs)

    def test_get_logs_filters_by_warn_level(self, logger):
        """AC5: get_logs(level='warn') returns only warn-level logs."""
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "warn", "details3")

        logs = logger.get_logs(level="warn")
        assert len(logs) == 2
        assert all(log.level == "warn" for log in logs)
        assert logs[0].event == "event2"
        assert logs[1].event == "event3"

    def test_get_logs_filters_by_error_level(self, logger):
        """AC5: get_logs(level='error') returns only error-level logs."""
        logger.log("event1", "info", "details1")
        logger.log("event2", "error", "details2")
        logger.log("event3", "error", "details3")

        logs = logger.get_logs(level="error")
        assert len(logs) == 2
        assert all(log.level == "error" for log in logs)

    def test_get_logs_filter_returns_empty_when_no_matching_level(self, logger):
        """AC5: get_logs(level=...) returns empty list when no logs match the level."""
        logger.log("event1", "info", "details1")
        logger.log("event2", "info", "details2")

        logs = logger.get_logs(level="error")
        assert isinstance(logs, list)
        assert len(logs) == 0

    # AC6: NotificationLogger.save(filepath) writes valid JSONL
    def test_save_creates_file(self, logger):
        """AC6: save() creates a file at the specified filepath."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "logs.jsonl")
            logger.log("event", "info", "details")
            logger.save(filepath)

            assert os.path.exists(filepath)
            assert os.path.isfile(filepath)

    def test_save_writes_valid_json_lines(self, logger):
        """AC6: save() writes each log as a valid JSON line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "logs.jsonl")
            logger.log("event1", "info", "details1")
            logger.log("event2", "warn", "details2")
            logger.save(filepath)

            with open(filepath, 'r') as f:
                lines = f.readlines()

            assert len(lines) == 2
            # Each line should be valid JSON
            for line in lines:
                obj = json.loads(line.strip())
                assert "timestamp" in obj
                assert "event" in obj
                assert "level" in obj
                assert "details" in obj

    def test_save_preserves_data(self, logger):
        """AC6: save() preserves all log data in the JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "logs.jsonl")
            logger.log("test_event", "warn", "test_details")
            logger.save(filepath)

            with open(filepath, 'r') as f:
                data = json.loads(f.readline())

            assert data["event"] == "test_event"
            assert data["level"] == "warn"
            assert data["details"] == "test_details"

    def test_save_empty_logger_creates_empty_file(self, logger):
        """AC6: save() with empty logger creates a file with no content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "logs.jsonl")
            logger.save(filepath)

            assert os.path.exists(filepath)
            with open(filepath, 'r') as f:
                content = f.read()
            assert content == "" or content.isspace()

    def test_save_multiple_logs_as_separate_lines(self, logger):
        """AC6: save() writes each log on a separate line (valid JSONL format)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "logs.jsonl")
            logger.log("event1", "info", "details1")
            logger.log("event2", "warn", "details2")
            logger.log("event3", "error", "details3")
            logger.save(filepath)

            with open(filepath, 'r') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]

            assert len(lines) == 3
            for line in lines:
                json.loads(line)  # Should not raise

    # AC7: NotificationLogger.load(filepath) restores logs from JSONL file
    def test_load_restores_logs_from_file(self, logger):
        """AC7: load() restores logs from a JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "logs.jsonl")

            # Create and save logs
            logger.log("event1", "info", "details1")
            logger.log("event2", "warn", "details2")
            logger.save(filepath)

            # Create a new logger and load the file
            new_logger = NotificationLogger()
            new_logger.load(filepath)

            logs = new_logger.get_logs()
            assert len(logs) == 2
            assert logs[0].event == "event1"
            assert logs[1].event == "event2"

    def test_load_restores_all_fields(self, logger):
        """AC7: load() restores all fields from the JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "logs.jsonl")

            logger.log("my_event", "error", "my_details")
            logger.save(filepath)

            new_logger = NotificationLogger()
            new_logger.load(filepath)

            logs = new_logger.get_logs()
            assert logs[0].event == "my_event"
            assert logs[0].level == "error"
            assert logs[0].details == "my_details"
            assert isinstance(logs[0].timestamp, datetime)

    def test_load_replaces_existing_logs(self, logger):
        """AC7: load() replaces in-memory logs with logs from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "logs.jsonl")

            # Create file with one log
            logger1 = NotificationLogger()
            logger1.log("file_event", "info", "file_details")
            logger1.save(filepath)

            # Create second logger with different logs
            logger2 = NotificationLogger()
            logger2.log("memory_event", "warn", "memory_details")
            assert len(logger2.get_logs()) == 1

            # Load should replace memory logs
            logger2.load(filepath)
            logs = logger2.get_logs()
            assert len(logs) == 1
            assert logs[0].event == "file_event"

    def test_load_empty_file_results_in_empty_logs(self, logger):
        """AC7: load() on empty JSONL file results in empty logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "empty.jsonl")
            Path(filepath).write_text("")

            new_logger = NotificationLogger()
            new_logger.load(filepath)

            logs = new_logger.get_logs()
            assert len(logs) == 0

    def test_load_nonexistent_file_raises_error(self, logger):
        """AC7: load() with nonexistent file raises appropriate error."""
        with pytest.raises((FileNotFoundError, IOError)):
            logger.load("/nonexistent/path/to/file.jsonl")

    def test_load_restores_multiple_logs_with_different_levels(self, logger):
        """AC7: load() correctly restores logs with different levels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "mixed.jsonl")

            logger.log("info_event", "info", "info_details")
            logger.log("warn_event", "warn", "warn_details")
            logger.log("error_event", "error", "error_details")
            logger.save(filepath)

            new_logger = NotificationLogger()
            new_logger.load(filepath)

            all_logs = new_logger.get_logs()
            assert len(all_logs) == 3

            info_logs = new_logger.get_logs(level="info")
            warn_logs = new_logger.get_logs(level="warn")
            error_logs = new_logger.get_logs(level="error")

            assert len(info_logs) == 1
            assert len(warn_logs) == 1
            assert len(error_logs) == 1


class TestNotificationLoggerIntegration:
    """Integration tests for NotificationLogger."""

    def test_full_workflow_log_save_load(self):
        """AC3,6,7: Full workflow of logging, saving, and loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "workflow.jsonl")

            # Create and populate logger
            logger1 = NotificationLogger()
            logger1.log("event1", "info", "details1")
            logger1.log("event2", "warn", "details2")
            logger1.log("event3", "error", "details3")

            # Save to file
            logger1.save(filepath)

            # Load into new logger
            logger2 = NotificationLogger()
            logger2.load(filepath)

            # Verify all data is preserved
            logs = logger2.get_logs()
            assert len(logs) == 3
            assert logs[0].level == "info"
            assert logs[1].level == "warn"
            assert logs[2].level == "error"

    def test_filtering_after_load(self):
        """AC4,5,7: Filtering works correctly on loaded logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "filter_test.jsonl")

            logger1 = NotificationLogger()
            logger1.log("event1", "info", "d1")
            logger1.log("event2", "warn", "d2")
            logger1.log("event3", "info", "d3")
            logger1.log("event4", "error", "d4")
            logger1.save(filepath)

            logger2 = NotificationLogger()
            logger2.load(filepath)

            info_logs = logger2.get_logs(level="info")
            warn_logs = logger2.get_logs(level="warn")
            error_logs = logger2.get_logs(level="error")

            assert len(info_logs) == 2
            assert len(warn_logs) == 1
            assert len(error_logs) == 1


class TestNotificationLoggerModuleImport:
    """Tests for module import and accessibility."""

    def test_module_is_importable(self):
        """AC8: Module is importable from src.utils.notification_logger."""
        # This test will pass if the import at the top of the file succeeds
        from src.utils.notification_logger import NotificationLog, NotificationLogger
        assert NotificationLog is not None
        assert NotificationLogger is not None

    def test_notification_log_is_accessible(self):
        """AC8: NotificationLog is accessible from src.utils.notification_logger."""
        from src.utils.notification_logger import NotificationLog
        assert callable(NotificationLog)

    def test_notification_logger_is_accessible(self):
        """AC8: NotificationLogger is accessible from src.utils.notification_logger."""
        from src.utils.notification_logger import NotificationLogger
        assert callable(NotificationLogger)
