"""
Tests for the NotificationLogger utility (US-001).

IMPLEMENTATION PLAN for US-001:

Components:
  - NotificationLog: A dataclass storing timestamp, event, level, and details
  - NotificationLogger: A class managing a list of NotificationLog objects with
    methods to log events, filter by level, save to JSONL, and load from JSONL

Test Cases:
  1. (AC1) NotificationLog dataclass exists with required fields
  2. (AC2) level field validates and only accepts 'info', 'warn', 'error'
  3. (AC3) NotificationLogger.log() stores a new NotificationLog with UTC timestamp
  4. (AC4) NotificationLogger.get_logs() returns all logs when called with no arguments
  5. (AC5) NotificationLogger.get_logs(level='warn') returns only matching logs
  6. (AC6) NotificationLogger.save(filepath) writes JSONL format
  7. (AC7) NotificationLogger.load(filepath) reads JSONL and replaces in-memory logs
  8. (AC8) Module is importable as required

Edge Cases:
  - Empty level filtering
  - Empty log storage
  - Invalid level values
  - File I/O errors
  - Timestamp generation consistency
  - JSONL parsing with various formats
"""

import pytest
import json
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, mock_open
from pathlib import Path


# ============================================================================
# DATACLASS TESTS (18 tests)
# ============================================================================

class TestNotificationLogDataclass:
    """Test suite for NotificationLog dataclass."""

    def test_notification_log_import(self):
        """Test that NotificationLog can be imported from the module."""
        from src.utils.notification_logger import NotificationLog
        assert NotificationLog is not None

    def test_notification_log_has_timestamp_field(self):
        """Test that NotificationLog has a timestamp field."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test_event",
            level="info",
            details="test details"
        )
        assert hasattr(log, 'timestamp')
        assert isinstance(log.timestamp, datetime)

    def test_notification_log_has_event_field(self):
        """Test that NotificationLog has an event field."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test_event",
            level="info",
            details="test details"
        )
        assert hasattr(log, 'event')
        assert log.event == "test_event"

    def test_notification_log_has_level_field(self):
        """Test that NotificationLog has a level field."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test_event",
            level="info",
            details="test details"
        )
        assert hasattr(log, 'level')
        assert log.level == "info"

    def test_notification_log_has_details_field(self):
        """Test that NotificationLog has a details field."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test_event",
            level="info",
            details="test details"
        )
        assert hasattr(log, 'details')
        assert log.details == "test details"

    def test_notification_log_accepts_info_level(self):
        """Test that NotificationLog accepts 'info' level."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test_event",
            level="info",
            details="test details"
        )
        assert log.level == "info"

    def test_notification_log_accepts_warn_level(self):
        """Test that NotificationLog accepts 'warn' level."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test_event",
            level="warn",
            details="test details"
        )
        assert log.level == "warn"

    def test_notification_log_accepts_error_level(self):
        """Test that NotificationLog accepts 'error' level."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test_event",
            level="error",
            details="test details"
        )
        assert log.level == "error"

    def test_notification_log_rejects_invalid_level(self):
        """Test that NotificationLog rejects invalid levels."""
        from src.utils.notification_logger import NotificationLog
        with pytest.raises((ValueError, TypeError)):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level="invalid",
                details="test details"
            )

    def test_notification_log_rejects_debug_level(self):
        """Test that NotificationLog rejects 'debug' level."""
        from src.utils.notification_logger import NotificationLog
        with pytest.raises((ValueError, TypeError)):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level="debug",
                details="test details"
            )

    def test_notification_log_rejects_critical_level(self):
        """Test that NotificationLog rejects 'critical' level."""
        from src.utils.notification_logger import NotificationLog
        with pytest.raises((ValueError, TypeError)):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level="critical",
                details="test details"
            )

    def test_notification_log_rejects_empty_level(self):
        """Test that NotificationLog rejects empty string as level."""
        from src.utils.notification_logger import NotificationLog
        with pytest.raises((ValueError, TypeError)):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level="",
                details="test details"
            )

    def test_notification_log_rejects_none_level(self):
        """Test that NotificationLog rejects None as level."""
        from src.utils.notification_logger import NotificationLog
        with pytest.raises((ValueError, TypeError, AttributeError)):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level=None,
                details="test details"
            )

    def test_notification_log_is_dataclass(self):
        """Test that NotificationLog is a dataclass."""
        from src.utils.notification_logger import NotificationLog
        from dataclasses import is_dataclass
        assert is_dataclass(NotificationLog)

    def test_notification_log_with_empty_event(self):
        """Test that NotificationLog accepts empty event string."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="",
            level="info",
            details="test details"
        )
        assert log.event == ""

    def test_notification_log_with_empty_details(self):
        """Test that NotificationLog accepts empty details string."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test_event",
            level="info",
            details=""
        )
        assert log.details == ""

    def test_notification_log_with_special_characters(self):
        """Test that NotificationLog handles special characters in strings."""
        from src.utils.notification_logger import NotificationLog
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test\nevent\twith\rspecial",
            level="info",
            details="details with \"quotes\" and 'apostrophes'"
        )
        assert "test" in log.event
        assert "quotes" in log.details

    def test_notification_log_preserves_timestamp_precision(self):
        """Test that NotificationLog preserves timestamp precision."""
        from src.utils.notification_logger import NotificationLog
        now = datetime.utcnow()
        log = NotificationLog(
            timestamp=now,
            event="test_event",
            level="info",
            details="test details"
        )
        assert log.timestamp == now


# ============================================================================
# LOGGER TESTS (42 tests)
# ============================================================================

class TestNotificationLogger:
    """Test suite for NotificationLogger class."""

    def test_notification_logger_import(self):
        """Test that NotificationLogger can be imported from the module."""
        from src.utils.notification_logger import NotificationLogger
        assert NotificationLogger is not None

    def test_logger_initialization(self):
        """Test that NotificationLogger initializes with empty logs."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        assert logger is not None

    def test_logger_log_method_exists(self):
        """Test that NotificationLogger has a log method."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        assert hasattr(logger, 'log')
        assert callable(logger.log)

    def test_logger_get_logs_method_exists(self):
        """Test that NotificationLogger has a get_logs method."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        assert hasattr(logger, 'get_logs')
        assert callable(logger.get_logs)

    def test_logger_save_method_exists(self):
        """Test that NotificationLogger has a save method."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        assert hasattr(logger, 'save')
        assert callable(logger.save)

    def test_logger_load_method_exists(self):
        """Test that NotificationLogger has a load method."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        assert hasattr(logger, 'load')
        assert callable(logger.load)

    def test_logger_log_creates_notification_log(self):
        """Test that log() method creates and stores a NotificationLog."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("test_event", "info", "test details")
        logs = logger.get_logs()
        assert len(logs) == 1

    def test_logger_log_with_info_level(self):
        """Test that log() accepts 'info' level."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("test_event", "info", "test details")
        logs = logger.get_logs()
        assert logs[0].level == "info"

    def test_logger_log_with_warn_level(self):
        """Test that log() accepts 'warn' level."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("test_event", "warn", "test details")
        logs = logger.get_logs()
        assert logs[0].level == "warn"

    def test_logger_log_with_error_level(self):
        """Test that log() accepts 'error' level."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("test_event", "error", "test details")
        logs = logger.get_logs()
        assert logs[0].level == "error"

    def test_logger_log_generates_timestamp(self):
        """Test that log() auto-generates current UTC timestamp."""
        from src.utils.notification_logger import NotificationLogger
        before = datetime.utcnow()
        logger = NotificationLogger()
        logger.log("test_event", "info", "test details")
        after = datetime.utcnow()
        logs = logger.get_logs()
        assert before <= logs[0].timestamp <= after

    def test_logger_log_stores_event(self):
        """Test that log() stores the event string."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("test_event_123", "info", "test details")
        logs = logger.get_logs()
        assert logs[0].event == "test_event_123"

    def test_logger_log_stores_details(self):
        """Test that log() stores the details string."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("test_event", "info", "detailed information here")
        logs = logger.get_logs()
        assert logs[0].details == "detailed information here"

    def test_logger_log_multiple_entries(self):
        """Test that log() can be called multiple times."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")
        logs = logger.get_logs()
        assert len(logs) == 3

    def test_logger_get_logs_returns_list(self):
        """Test that get_logs() returns a list."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logs = logger.get_logs()
        assert isinstance(logs, list)

    def test_logger_get_logs_returns_all_logs(self):
        """Test that get_logs() returns all logs when called with no arguments."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")
        logs = logger.get_logs()
        assert len(logs) == 3

    def test_logger_get_logs_empty_when_no_logs(self):
        """Test that get_logs() returns empty list when no logs exist."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logs = logger.get_logs()
        assert logs == []

    def test_logger_get_logs_filters_by_info_level(self):
        """Test that get_logs(level='info') returns only info logs."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "info", "details3")
        logs = logger.get_logs(level="info")
        assert len(logs) == 2
        assert all(log.level == "info" for log in logs)

    def test_logger_get_logs_filters_by_warn_level(self):
        """Test that get_logs(level='warn') returns only warn logs."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "warn", "details3")
        logs = logger.get_logs(level="warn")
        assert len(logs) == 2
        assert all(log.level == "warn" for log in logs)

    def test_logger_get_logs_filters_by_error_level(self):
        """Test that get_logs(level='error') returns only error logs."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "error", "details2")
        logger.log("event3", "error", "details3")
        logs = logger.get_logs(level="error")
        assert len(logs) == 2
        assert all(log.level == "error" for log in logs)

    def test_logger_get_logs_returns_empty_list_for_nonexistent_level(self):
        """Test that get_logs(level='error') returns empty when no error logs exist."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logs = logger.get_logs(level="error")
        assert logs == []

    def test_logger_get_logs_preserves_order(self):
        """Test that get_logs() preserves insertion order."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "info", "details2")
        logger.log("event3", "info", "details3")
        logs = logger.get_logs(level="info")
        assert logs[0].event == "event1"
        assert logs[1].event == "event2"
        assert logs[2].event == "event3"

    def test_logger_save_writes_file(self):
        """Test that save() creates a file."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")
            logger.save(filepath)
            assert os.path.exists(filepath)

    def test_logger_save_writes_jsonl_format(self):
        """Test that save() writes JSONL format (one JSON per line)."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")
            logger.save(filepath)

            with open(filepath, 'r') as f:
                lines = f.readlines()

            assert len(lines) == 2
            # Each line should be valid JSON
            for line in lines:
                json.loads(line.strip())

    def test_logger_save_includes_timestamp_in_jsonl(self):
        """Test that saved JSONL includes timestamp field."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")
            logger.save(filepath)

            with open(filepath, 'r') as f:
                line = f.readline()
                data = json.loads(line)

            assert 'timestamp' in data

    def test_logger_save_includes_event_in_jsonl(self):
        """Test that saved JSONL includes event field."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")
            logger.save(filepath)

            with open(filepath, 'r') as f:
                line = f.readline()
                data = json.loads(line)

            assert 'event' in data
            assert data['event'] == "event1"

    def test_logger_save_includes_level_in_jsonl(self):
        """Test that saved JSONL includes level field."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")
            logger.save(filepath)

            with open(filepath, 'r') as f:
                line = f.readline()
                data = json.loads(line)

            assert 'level' in data
            assert data['level'] == "info"

    def test_logger_save_includes_details_in_jsonl(self):
        """Test that saved JSONL includes details field."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")
            logger.save(filepath)

            with open(filepath, 'r') as f:
                line = f.readline()
                data = json.loads(line)

            assert 'details' in data
            assert data['details'] == "details1"

    def test_logger_save_with_empty_logs(self):
        """Test that save() handles empty log list."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")
            logger.save(filepath)

            with open(filepath, 'r') as f:
                content = f.read()

            assert content == ""

    def test_logger_load_reads_jsonl_file(self):
        """Test that load() reads a JSONL file."""
        from src.utils.notification_logger import NotificationLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")

            # Create a JSONL file
            with open(filepath, 'w') as f:
                f.write('{"timestamp": "2024-01-01T00:00:00", "event": "event1", "level": "info", "details": "details1"}\n')

            logger = NotificationLogger()
            logger.load(filepath)
            logs = logger.get_logs()

            assert len(logs) == 1

    def test_logger_load_replaces_existing_logs(self):
        """Test that load() replaces in-memory logs."""
        from src.utils.notification_logger import NotificationLogger

        logger = NotificationLogger()
        logger.log("old_event", "info", "old details")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")

            # Create a JSONL file
            with open(filepath, 'w') as f:
                f.write('{"timestamp": "2024-01-01T00:00:00", "event": "new_event", "level": "warn", "details": "new details"}\n')

            logger.load(filepath)
            logs = logger.get_logs()

            assert len(logs) == 1
            assert logs[0].event == "new_event"

    def test_logger_load_multiple_lines(self):
        """Test that load() reads multiple JSONL lines."""
        from src.utils.notification_logger import NotificationLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")

            # Create a JSONL file with multiple lines
            with open(filepath, 'w') as f:
                f.write('{"timestamp": "2024-01-01T00:00:00", "event": "event1", "level": "info", "details": "details1"}\n')
                f.write('{"timestamp": "2024-01-01T00:00:01", "event": "event2", "level": "warn", "details": "details2"}\n')
                f.write('{"timestamp": "2024-01-01T00:00:02", "event": "event3", "level": "error", "details": "details3"}\n')

            logger = NotificationLogger()
            logger.load(filepath)
            logs = logger.get_logs()

            assert len(logs) == 3

    def test_logger_load_with_empty_file(self):
        """Test that load() handles empty file."""
        from src.utils.notification_logger import NotificationLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")

            # Create an empty file
            open(filepath, 'w').close()

            logger = NotificationLogger()
            logger.load(filepath)
            logs = logger.get_logs()

            assert logs == []

    def test_logger_roundtrip_save_load(self):
        """Test that save() and load() roundtrip correctly."""
        from src.utils.notification_logger import NotificationLogger

        logger1 = NotificationLogger()
        logger1.log("event1", "info", "details1")
        logger1.log("event2", "warn", "details2")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")
            logger1.save(filepath)

            logger2 = NotificationLogger()
            logger2.load(filepath)
            logs = logger2.get_logs()

            assert len(logs) == 2
            assert logs[0].event == "event1"
            assert logs[1].event == "event2"

    def test_logger_log_rejects_invalid_level(self):
        """Test that log() rejects invalid levels."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        with pytest.raises((ValueError, TypeError)):
            logger.log("event1", "invalid", "details1")

    def test_logger_get_logs_with_none_level_returns_all(self):
        """Test that get_logs(level=None) returns all logs."""
        from src.utils.notification_logger import NotificationLogger
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logs = logger.get_logs(level=None)
        assert len(logs) == 2


# ============================================================================
# INTEGRATION TESTS (3 tests)
# ============================================================================

class TestNotificationLoggerIntegration:
    """Integration tests for NotificationLogger."""

    def test_full_workflow_save_load_filter(self):
        """Test full workflow: create, log, save, load, filter."""
        from src.utils.notification_logger import NotificationLogger

        # Create logger and add logs
        logger1 = NotificationLogger()
        logger1.log("event1", "info", "details1")
        logger1.log("event2", "warn", "details2")
        logger1.log("event3", "error", "details3")
        logger1.log("event4", "info", "details4")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")
            logger1.save(filepath)

            # Load into new logger
            logger2 = NotificationLogger()
            logger2.load(filepath)

            # Verify all logs are present
            all_logs = logger2.get_logs()
            assert len(all_logs) == 4

            # Verify filtering works
            info_logs = logger2.get_logs(level="info")
            assert len(info_logs) == 2

            warn_logs = logger2.get_logs(level="warn")
            assert len(warn_logs) == 1

            error_logs = logger2.get_logs(level="error")
            assert len(error_logs) == 1

    def test_filtering_after_load(self):
        """Test that filtering works correctly after load()."""
        from src.utils.notification_logger import NotificationLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_logs.jsonl")

            # Create a JSONL file
            with open(filepath, 'w') as f:
                f.write('{"timestamp": "2024-01-01T00:00:00", "event": "event1", "level": "info", "details": "details1"}\n')
                f.write('{"timestamp": "2024-01-01T00:00:01", "event": "event2", "level": "warn", "details": "details2"}\n')
                f.write('{"timestamp": "2024-01-01T00:00:02", "event": "event3", "level": "error", "details": "details3"}\n')

            logger = NotificationLogger()
            logger.load(filepath)

            # Filter by level
            info_logs = logger.get_logs(level="info")
            assert len(info_logs) == 1
            assert info_logs[0].level == "info"

            error_logs = logger.get_logs(level="error")
            assert len(error_logs) == 1
            assert error_logs[0].level == "error"

    def test_save_multiple_times(self):
        """Test that save() can be called multiple times with different states."""
        from src.utils.notification_logger import NotificationLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            logger = NotificationLogger()

            # First save
            logger.log("event1", "info", "details1")
            filepath1 = os.path.join(tmpdir, "test_logs_1.jsonl")
            logger.save(filepath1)

            # Add more logs and save again
            logger.log("event2", "warn", "details2")
            filepath2 = os.path.join(tmpdir, "test_logs_2.jsonl")
            logger.save(filepath2)

            # Verify first file has 1 log
            with open(filepath1, 'r') as f:
                lines1 = f.readlines()
            assert len(lines1) == 1

            # Verify second file has 2 logs
            with open(filepath2, 'r') as f:
                lines2 = f.readlines()
            assert len(lines2) == 2


# ============================================================================
# IMPORT TESTS (3 tests)
# ============================================================================

class TestModuleImports:
    """Test that the module is properly importable."""

    def test_import_notification_logger_from_package(self):
        """Test importing NotificationLogger from src.utils.notification_logger."""
        from src.utils.notification_logger import NotificationLogger
        assert NotificationLogger is not None

    def test_import_notification_log_from_package(self):
        """Test importing NotificationLog from src.utils.notification_logger."""
        from src.utils.notification_logger import NotificationLog
        assert NotificationLog is not None

    def test_import_both_from_package(self):
        """Test importing both NotificationLog and NotificationLogger."""
        from src.utils.notification_logger import NotificationLogger, NotificationLog
        assert NotificationLogger is not None
        assert NotificationLog is not None
