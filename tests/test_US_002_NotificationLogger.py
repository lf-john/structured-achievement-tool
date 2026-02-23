"""
IMPLEMENTATION PLAN for US-002:

Comprehensive Tests for NotificationLogger

Components Being Tested:
  - NotificationLog: Dataclass with timestamp, event, level, details fields
  - NotificationLogger: Class managing log storage, filtering, persistence

Test Coverage:
  1. AC1: Tests for logging at each valid level (info, warn, error)
  2. AC2: Tests verify get_logs() returns all logs when no filter given
  3. AC3: Tests verify get_logs(level=...) filters correctly
  4. AC4: Tests verify save/load round-trip preserves all fields including timestamp
  5. AC5: Tests verify invalid level raises an error
  6. AC6: Tests cover empty logger edge cases
  7. AC7: All tests pass with the US-001 implementation

Edge Cases:
  - Empty logger initialization and operations on empty logs
  - Multiple logs with same and different levels
  - Timestamp precision in save/load round-trip
  - JSONL file format validation
  - Invalid level rejection at dataclass creation
  - File I/O edge cases (missing files, empty files, malformed JSON)
"""

import pytest
import json
import tempfile
import os
from datetime import datetime
from pathlib import Path
from src.utils.notification_logger import NotificationLog, NotificationLogger


# ============================================================================
# DATACLASS VALIDATION TESTS (AC1, AC5)
# ============================================================================

class TestNotificationLogDataclass:
    """Test NotificationLog dataclass structure and validation."""

    def test_should_create_notification_log_with_valid_info_level(self):
        """AC1: Should accept info level."""
        now = datetime.utcnow()
        log = NotificationLog(
            timestamp=now,
            event="test_event",
            level="info",
            details="test details"
        )
        assert log.timestamp == now
        assert log.event == "test_event"
        assert log.level == "info"
        assert log.details == "test details"

    def test_should_create_notification_log_with_valid_warn_level(self):
        """AC1: Should accept warn level."""
        now = datetime.utcnow()
        log = NotificationLog(
            timestamp=now,
            event="warning_event",
            level="warn",
            details="warning details"
        )
        assert log.level == "warn"

    def test_should_create_notification_log_with_valid_error_level(self):
        """AC1: Should accept error level."""
        now = datetime.utcnow()
        log = NotificationLog(
            timestamp=now,
            event="error_event",
            level="error",
            details="error details"
        )
        assert log.level == "error"

    def test_should_reject_invalid_level_with_value_error(self):
        """AC5: Should reject invalid level."""
        with pytest.raises(ValueError):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level="invalid",
                details="test details"
            )

    def test_should_reject_debug_level(self):
        """AC5: Should reject 'debug' level."""
        with pytest.raises(ValueError):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level="debug",
                details="test details"
            )

    def test_should_reject_warning_level_spelling(self):
        """AC5: Should reject 'warning' (use 'warn')."""
        with pytest.raises(ValueError):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level="warning",
                details="test details"
            )

    def test_should_reject_none_as_level(self):
        """AC5: Should reject None as level."""
        with pytest.raises((ValueError, TypeError)):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level=None,
                details="test details"
            )

    def test_should_reject_empty_string_as_level(self):
        """AC5: Should reject empty string as level."""
        with pytest.raises(ValueError):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test_event",
                level="",
                details="test details"
            )


# ============================================================================
# LOGGING AND FILTERING TESTS (AC1, AC2, AC3)
# ============================================================================

class TestNotificationLoggerLogging:
    """Test NotificationLogger logging and filtering functionality."""

    def test_should_initialize_empty_logger(self):
        """AC6: Logger should initialize with no logs."""
        logger = NotificationLogger()
        logs = logger.get_logs()
        assert logs == []

    def test_should_log_single_event_at_info_level(self):
        """AC1: Should log event at info level."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0].event == "event1"
        assert logs[0].level == "info"

    def test_should_log_single_event_at_warn_level(self):
        """AC1: Should log event at warn level."""
        logger = NotificationLogger()
        logger.log("event1", "warn", "details1")
        logs = logger.get_logs()
        assert logs[0].level == "warn"

    def test_should_log_single_event_at_error_level(self):
        """AC1: Should log event at error level."""
        logger = NotificationLogger()
        logger.log("event1", "error", "details1")
        logs = logger.get_logs()
        assert logs[0].level == "error"

    def test_should_auto_generate_current_timestamp_on_log(self):
        """AC1, AC4: Should auto-generate UTC timestamp."""
        logger = NotificationLogger()
        before = datetime.utcnow()
        logger.log("event1", "info", "details1")
        after = datetime.utcnow()

        logs = logger.get_logs()
        logged_time = logs[0].timestamp
        assert before <= logged_time <= after

    def test_should_log_multiple_events(self):
        """AC1: Should store multiple log entries."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")

        logs = logger.get_logs()
        assert len(logs) == 3

    def test_should_get_all_logs_without_filter(self):
        """AC2: get_logs() should return all logs when no filter given."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")

        logs = logger.get_logs()
        assert len(logs) == 3
        assert logs[0].event == "event1"
        assert logs[1].event == "event2"
        assert logs[2].event == "event3"

    def test_should_return_empty_list_when_getting_logs_from_empty_logger(self):
        """AC2, AC6: get_logs() should return empty list when logger is empty."""
        logger = NotificationLogger()
        logs = logger.get_logs()
        assert logs == []
        assert isinstance(logs, list)

    def test_should_filter_logs_by_info_level(self):
        """AC3: get_logs(level='info') should filter correctly."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "info", "details3")

        logs = logger.get_logs(level="info")
        assert len(logs) == 2
        assert all(log.level == "info" for log in logs)
        assert logs[0].event == "event1"
        assert logs[1].event == "event3"

    def test_should_filter_logs_by_warn_level(self):
        """AC3: get_logs(level='warn') should filter correctly."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "warn", "details3")

        logs = logger.get_logs(level="warn")
        assert len(logs) == 2
        assert all(log.level == "warn" for log in logs)

    def test_should_filter_logs_by_error_level(self):
        """AC3: get_logs(level='error') should filter correctly."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "error", "details2")
        logger.log("event3", "error", "details3")

        logs = logger.get_logs(level="error")
        assert len(logs) == 2
        assert all(log.level == "error" for log in logs)

    def test_should_return_empty_list_when_filtering_with_no_matches(self):
        """AC3, AC6: Should return empty list when filter matches no logs."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "info", "details2")

        logs = logger.get_logs(level="error")
        assert logs == []

    def test_should_return_empty_list_when_filtering_empty_logger(self):
        """AC3, AC6: Should return empty list when filtering empty logger."""
        logger = NotificationLogger()
        logs = logger.get_logs(level="info")
        assert logs == []

    def test_should_preserve_log_order(self):
        """Should preserve the order logs were added."""
        logger = NotificationLogger()
        logger.log("first", "info", "d1")
        logger.log("second", "info", "d2")
        logger.log("third", "info", "d3")

        logs = logger.get_logs()
        assert [log.event for log in logs] == ["first", "second", "third"]


# ============================================================================
# SAVE/LOAD TESTS (AC4)
# ============================================================================

class TestNotificationLoggerPersistence:
    """Test NotificationLogger save and load functionality."""

    def test_should_save_single_log_to_jsonl(self):
        """AC4: Should save log to JSONL format."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            logger.save(filepath)

            with open(filepath, 'r') as f:
                content = f.read()

            assert content.strip()  # Not empty
            data = json.loads(content.strip())
            assert data['event'] == "event1"
            assert data['level'] == "info"
            assert data['details'] == "details1"
        finally:
            os.unlink(filepath)

    def test_should_save_multiple_logs_to_jsonl(self):
        """AC4: Should save multiple logs, one per line."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            logger.save(filepath)

            with open(filepath, 'r') as f:
                lines = f.readlines()

            assert len(lines) == 3

            data1 = json.loads(lines[0])
            data2 = json.loads(lines[1])
            data3 = json.loads(lines[2])

            assert data1['event'] == "event1"
            assert data2['event'] == "event2"
            assert data3['event'] == "event3"
        finally:
            os.unlink(filepath)

    def test_should_save_all_fields_in_jsonl(self):
        """AC4: Should save timestamp, event, level, details in JSONL."""
        logger = NotificationLogger()
        now = datetime.utcnow()

        # Log and then read back the logged entry to get its timestamp
        logger.log("test_event", "info", "test_details")
        logged_timestamp = logger.get_logs()[0].timestamp

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            logger.save(filepath)

            with open(filepath, 'r') as f:
                data = json.loads(f.read().strip())

            assert 'timestamp' in data
            assert 'event' in data
            assert 'level' in data
            assert 'details' in data
            assert data['event'] == "test_event"
            assert data['level'] == "info"
            assert data['details'] == "test_details"
        finally:
            os.unlink(filepath)

    def test_should_load_single_log_from_jsonl(self):
        """AC4: Should load log from JSONL file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name
            now = datetime.utcnow().isoformat()
            json.dump({
                'timestamp': now,
                'event': 'test_event',
                'level': 'info',
                'details': 'test_details'
            }, f)
            f.write('\n')

        try:
            logger = NotificationLogger()
            logger.load(filepath)

            logs = logger.get_logs()
            assert len(logs) == 1
            assert logs[0].event == 'test_event'
            assert logs[0].level == 'info'
            assert logs[0].details == 'test_details'
        finally:
            os.unlink(filepath)

    def test_should_load_multiple_logs_from_jsonl(self):
        """AC4: Should load multiple logs from JSONL."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name
            now = datetime.utcnow().isoformat()

            json.dump({'timestamp': now, 'event': 'e1', 'level': 'info', 'details': 'd1'}, f)
            f.write('\n')
            json.dump({'timestamp': now, 'event': 'e2', 'level': 'warn', 'details': 'd2'}, f)
            f.write('\n')
            json.dump({'timestamp': now, 'event': 'e3', 'level': 'error', 'details': 'd3'}, f)
            f.write('\n')

        try:
            logger = NotificationLogger()
            logger.load(filepath)

            logs = logger.get_logs()
            assert len(logs) == 3
            assert logs[0].event == 'e1'
            assert logs[1].event == 'e2'
            assert logs[2].event == 'e3'
        finally:
            os.unlink(filepath)

    def test_should_preserve_timestamp_in_save_load_roundtrip(self):
        """AC4: Timestamp should be preserved in save/load round-trip."""
        logger1 = NotificationLogger()
        logger1.log("event1", "info", "details1")
        original_timestamp = logger1.get_logs()[0].timestamp

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            logger1.save(filepath)

            logger2 = NotificationLogger()
            logger2.load(filepath)

            loaded_timestamp = logger2.get_logs()[0].timestamp
            # Compare as strings since datetime precision might vary slightly
            assert loaded_timestamp.isoformat() == original_timestamp.isoformat()
        finally:
            os.unlink(filepath)

    def test_should_preserve_all_fields_in_save_load_roundtrip(self):
        """AC4: All fields should be preserved in save/load round-trip."""
        logger1 = NotificationLogger()
        logger1.log("my_event", "warn", "my_details")
        original_log = logger1.get_logs()[0]

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            logger1.save(filepath)

            logger2 = NotificationLogger()
            logger2.load(filepath)
            loaded_log = logger2.get_logs()[0]

            assert loaded_log.event == original_log.event
            assert loaded_log.level == original_log.level
            assert loaded_log.details == original_log.details
            assert loaded_log.timestamp.isoformat() == original_log.timestamp.isoformat()
        finally:
            os.unlink(filepath)

    def test_should_replace_logs_when_loading(self):
        """AC4: Loading should replace existing logs in memory."""
        logger = NotificationLogger()
        logger.log("old_event", "info", "old_details")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name
            now = datetime.utcnow().isoformat()
            json.dump({
                'timestamp': now,
                'event': 'new_event',
                'level': 'warn',
                'details': 'new_details'
            }, f)
            f.write('\n')

        try:
            logger.load(filepath)

            logs = logger.get_logs()
            assert len(logs) == 1
            assert logs[0].event == 'new_event'
        finally:
            os.unlink(filepath)

    def test_should_load_empty_file(self):
        """AC6: Should handle loading empty file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            logger = NotificationLogger()
            logger.load(filepath)

            logs = logger.get_logs()
            assert logs == []
        finally:
            os.unlink(filepath)

    def test_should_load_file_with_blank_lines(self):
        """AC6: Should handle file with blank lines."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name
            now = datetime.utcnow().isoformat()
            json.dump({'timestamp': now, 'event': 'e1', 'level': 'info', 'details': 'd1'}, f)
            f.write('\n\n\n')
            json.dump({'timestamp': now, 'event': 'e2', 'level': 'warn', 'details': 'd2'}, f)
            f.write('\n')

        try:
            logger = NotificationLogger()
            logger.load(filepath)

            logs = logger.get_logs()
            assert len(logs) == 2
            assert logs[0].event == 'e1'
            assert logs[1].event == 'e2'
        finally:
            os.unlink(filepath)

    def test_should_save_empty_logger(self):
        """AC6: Should handle saving empty logger."""
        logger = NotificationLogger()

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            logger.save(filepath)

            with open(filepath, 'r') as f:
                content = f.read()

            assert content == "" or content.isspace()
        finally:
            os.unlink(filepath)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestNotificationLoggerIntegration:
    """Integration tests covering full workflows."""

    def test_should_complete_full_workflow(self):
        """Full workflow: log, save, load, filter."""
        # Create logger and add various logs
        logger1 = NotificationLogger()
        logger1.log("startup", "info", "app starting")
        logger1.log("config_loaded", "info", "config loaded")
        logger1.log("warning_event", "warn", "potential issue")
        logger1.log("error_event", "error", "critical error")
        logger1.log("recovery", "info", "recovered from error")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            # Save logs
            logger1.save(filepath)

            # Load into new logger
            logger2 = NotificationLogger()
            logger2.load(filepath)

            # Verify all logs loaded
            all_logs = logger2.get_logs()
            assert len(all_logs) == 5

            # Verify filtering works
            info_logs = logger2.get_logs(level="info")
            assert len(info_logs) == 3

            warn_logs = logger2.get_logs(level="warn")
            assert len(warn_logs) == 1

            error_logs = logger2.get_logs(level="error")
            assert len(error_logs) == 1
        finally:
            os.unlink(filepath)

    def test_should_maintain_level_integrity_after_save_load(self):
        """Levels should be preserved through save/load cycle."""
        logger1 = NotificationLogger()
        logger1.log("e1", "info", "d1")
        logger1.log("e2", "warn", "d2")
        logger1.log("e3", "error", "d3")
        logger1.log("e4", "info", "d4")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            logger1.save(filepath)
            logger2 = NotificationLogger()
            logger2.load(filepath)

            # All filtering should work correctly after load
            info_logs = logger2.get_logs(level="info")
            warn_logs = logger2.get_logs(level="warn")
            error_logs = logger2.get_logs(level="error")

            assert len(info_logs) == 2
            assert len(warn_logs) == 1
            assert len(error_logs) == 1
            assert [log.event for log in info_logs] == ["e1", "e4"]
        finally:
            os.unlink(filepath)

    def test_should_reject_invalid_level_in_save_load_workflow(self):
        """Invalid levels should still be rejected even in complex workflows."""
        logger = NotificationLogger()
        logger.log("valid", "info", "details")

        with pytest.raises(ValueError):
            logger.log("invalid", "invalid_level", "details")

    def test_should_handle_special_characters_in_details(self):
        """Should preserve special characters in details field."""
        logger = NotificationLogger()
        details = 'special chars: "quotes", \n newlines, \t tabs, 特殊文字'
        logger.log("event", "info", details)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            filepath = f.name

        try:
            logger.save(filepath)
            logger2 = NotificationLogger()
            logger2.load(filepath)

            loaded_details = logger2.get_logs()[0].details
            assert loaded_details == details
        finally:
            os.unlink(filepath)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
