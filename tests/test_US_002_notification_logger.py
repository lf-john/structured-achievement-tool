"""
Comprehensive test suite for NotificationLogger utility — US-002 TDD-RED Phase

IMPLEMENTATION PLAN for US-002:

Components:
  - NotificationLog: Dataclass with timestamp (datetime), event (str), level (str), details (str)
    - Validates level is one of: 'info', 'warn', 'error'
  - NotificationLogger: Class managing notification log collection
    - log(event, level, details): Creates new NotificationLog with current UTC timestamp
    - get_logs(level=None): Returns all logs or filters by level if provided
    - save(filepath): Writes logs as JSONL (one JSON object per line)
    - load(filepath): Reads logs from JSONL file and replaces in-memory logs

Test Cases:
  1. AC1: Test logging at info level
  2. AC2: Test logging at warn level
  3. AC3: Test logging at error level
  4. AC4: Test get_logs() with no filter returns all entries
  5. AC5: Test get_logs(level='error') returns only error entries
  6. AC6: Test get_logs(level='warn') returns empty list when no warn entries exist
  7. AC7: Test save/load round-trip preserves all fields including timestamp
  8. AC8: Test empty logger returns empty list from get_logs()
  9. AC9: Test save on empty logger does not raise
  10. AC10: Test load from empty JSONL file results in empty log list

Edge Cases:
  - Multiple level types in same logger
  - Empty strings in event/details
  - Timestamp serialization/deserialization
  - File operations (create, read, write)
  - Case sensitivity on level filtering
  - Invalid level values
"""

import pytest
import json
import tempfile
from datetime import datetime
from pathlib import Path

from src.utils.notification_logger import NotificationLog, NotificationLogger


class TestNotificationLoggerLogging:
    """Test logging at different levels."""

    def test_should_log_info_level_event(self):
        """AC1: Test logging at info level."""
        logger = NotificationLogger()
        logger.log("test_event", "info", "test details")
        logs = logger.get_logs()

        assert len(logs) == 1
        assert logs[0].event == "test_event"
        assert logs[0].level == "info"
        assert logs[0].details == "test details"
        assert isinstance(logs[0].timestamp, datetime)

    def test_should_log_warn_level_event(self):
        """AC2: Test logging at warn level."""
        logger = NotificationLogger()
        logger.log("warning_event", "warn", "warning details")
        logs = logger.get_logs()

        assert len(logs) == 1
        assert logs[0].event == "warning_event"
        assert logs[0].level == "warn"
        assert logs[0].details == "warning details"

    def test_should_log_error_level_event(self):
        """AC3: Test logging at error level."""
        logger = NotificationLogger()
        logger.log("error_event", "error", "error details")
        logs = logger.get_logs()

        assert len(logs) == 1
        assert logs[0].event == "error_event"
        assert logs[0].level == "error"
        assert logs[0].details == "error details"

    def test_should_log_multiple_events_at_different_levels(self):
        """Test logging multiple events at different levels."""
        logger = NotificationLogger()
        logger.log("info_event", "info", "info details")
        logger.log("warn_event", "warn", "warn details")
        logger.log("error_event", "error", "error details")

        logs = logger.get_logs()
        assert len(logs) == 3

    def test_should_auto_generate_current_utc_timestamp(self):
        """Test that log() auto-generates current UTC timestamp."""
        logger = NotificationLogger()
        before = datetime.utcnow()
        logger.log("test", "info", "details")
        after = datetime.utcnow()

        logs = logger.get_logs()
        assert before <= logs[0].timestamp <= after

    def test_should_log_event_with_empty_details_string(self):
        """Test logging with empty details string."""
        logger = NotificationLogger()
        logger.log("event", "info", "")
        logs = logger.get_logs()

        assert len(logs) == 1
        assert logs[0].details == ""

    def test_should_log_event_with_empty_event_string(self):
        """Test logging with empty event string."""
        logger = NotificationLogger()
        logger.log("", "info", "details")
        logs = logger.get_logs()

        assert len(logs) == 1
        assert logs[0].event == ""


class TestGetLogsFiltering:
    """Test get_logs() filtering functionality."""

    def test_should_return_all_logs_when_no_filter_provided(self):
        """AC4: Test get_logs() with no filter returns all entries."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")

        logs = logger.get_logs()
        assert len(logs) == 3

    def test_should_return_only_error_entries_when_filtering_by_error(self):
        """AC5: Test get_logs(level='error') returns only error entries."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")
        logger.log("event4", "error", "details4")

        logs = logger.get_logs(level="error")
        assert len(logs) == 2
        assert all(log.level == "error" for log in logs)

    def test_should_return_only_info_entries_when_filtering_by_info(self):
        """Test get_logs(level='info') returns only info entries."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "info", "details3")

        logs = logger.get_logs(level="info")
        assert len(logs) == 2
        assert all(log.level == "info" for log in logs)

    def test_should_return_only_warn_entries_when_filtering_by_warn(self):
        """Test get_logs(level='warn') returns only warn entries."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "warn", "details3")

        logs = logger.get_logs(level="warn")
        assert len(logs) == 2
        assert all(log.level == "warn" for log in logs)

    def test_should_return_empty_list_when_filtering_by_warn_with_no_warn_entries(self):
        """AC6: Test get_logs(level='warn') returns empty list when no warn entries exist."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "error", "details2")

        logs = logger.get_logs(level="warn")
        assert logs == []
        assert len(logs) == 0

    def test_should_return_empty_list_when_filtering_by_error_with_no_error_entries(self):
        """Test get_logs(level='error') returns empty list when no error entries exist."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")

        logs = logger.get_logs(level="error")
        assert logs == []

    def test_should_return_empty_list_when_filtering_by_info_with_no_info_entries(self):
        """Test get_logs(level='info') returns empty list when no info entries exist."""
        logger = NotificationLogger()
        logger.log("event1", "warn", "details1")
        logger.log("event2", "error", "details2")

        logs = logger.get_logs(level="info")
        assert logs == []


class TestEmptyLogger:
    """Test behavior with empty logger."""

    def test_should_return_empty_list_from_get_logs_on_empty_logger(self):
        """AC8: Test empty logger returns empty list from get_logs()."""
        logger = NotificationLogger()
        logs = logger.get_logs()

        assert logs == []
        assert len(logs) == 0

    def test_should_return_empty_list_when_filtering_empty_logger_by_level(self):
        """Test filtering empty logger by level returns empty list."""
        logger = NotificationLogger()

        assert logger.get_logs(level="info") == []
        assert logger.get_logs(level="warn") == []
        assert logger.get_logs(level="error") == []


class TestSaveAndLoad:
    """Test save/load round-trip functionality."""

    def test_should_save_logs_to_jsonl_file(self):
        """Test save creates valid JSONL file."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            logger.save(temp_path)

            # Verify file contents are valid JSONL
            with open(temp_path, 'r') as f:
                lines = f.readlines()

            assert len(lines) == 2

            # Each line should be valid JSON
            obj1 = json.loads(lines[0])
            obj2 = json.loads(lines[1])

            assert obj1['event'] == "event1"
            assert obj2['event'] == "event2"
        finally:
            Path(temp_path).unlink()

    def test_should_load_logs_from_jsonl_file(self):
        """Test load reads JSONL file and restores logs."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            logger.save(temp_path)

            # Create new logger and load from file
            logger2 = NotificationLogger()
            logger2.load(temp_path)

            logs = logger2.get_logs()
            assert len(logs) == 2
            assert logs[0].event == "event1"
            assert logs[1].event == "event2"
        finally:
            Path(temp_path).unlink()

    def test_should_preserve_all_fields_in_save_load_roundtrip(self):
        """AC7: Test save/load round-trip preserves all fields including timestamp."""
        logger = NotificationLogger()
        logger.log("test_event", "warn", "test_details")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            logger.save(temp_path)

            logger2 = NotificationLogger()
            logger2.load(temp_path)

            logs = logger2.get_logs()
            assert len(logs) == 1

            loaded_log = logs[0]
            assert loaded_log.event == "test_event"
            assert loaded_log.level == "warn"
            assert loaded_log.details == "test_details"
            assert isinstance(loaded_log.timestamp, datetime)
        finally:
            Path(temp_path).unlink()

    def test_should_preserve_timestamp_format_across_roundtrip(self):
        """Test timestamp is correctly serialized and deserialized."""
        logger = NotificationLogger()
        original_log = logger.get_logs()

        logger.log("event", "info", "details")
        original_timestamp = logger.get_logs()[0].timestamp

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            logger.save(temp_path)

            logger2 = NotificationLogger()
            logger2.load(temp_path)

            loaded_timestamp = logger2.get_logs()[0].timestamp

            # Timestamps should be equal (within microsecond precision)
            assert original_timestamp == loaded_timestamp
            assert isinstance(loaded_timestamp, datetime)
        finally:
            Path(temp_path).unlink()

    def test_should_preserve_all_log_entries_on_roundtrip(self):
        """Test all log entries survive save/load cycle."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")
        logger.log("event2", "warn", "details2")
        logger.log("event3", "error", "details3")
        logger.log("event4", "info", "details4")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            logger.save(temp_path)

            logger2 = NotificationLogger()
            logger2.load(temp_path)

            loaded_logs = logger2.get_logs()
            assert len(loaded_logs) == 4

            assert loaded_logs[0].event == "event1"
            assert loaded_logs[1].event == "event2"
            assert loaded_logs[2].event == "event3"
            assert loaded_logs[3].event == "event4"
        finally:
            Path(temp_path).unlink()

    def test_should_not_raise_error_when_saving_empty_logger(self):
        """AC9: Test save on empty logger does not raise."""
        logger = NotificationLogger()

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            # Should not raise
            logger.save(temp_path)

            # File should exist and be empty
            with open(temp_path, 'r') as f:
                content = f.read()
            assert content == ""
        finally:
            Path(temp_path).unlink()

    def test_should_load_empty_jsonl_file_without_error(self):
        """AC10: Test load from empty JSONL file results in empty log list."""
        logger = NotificationLogger()

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            # File is empty

            # Should not raise
            logger.load(temp_path)

            logs = logger.get_logs()
            assert logs == []
        finally:
            Path(temp_path).unlink()

    def test_should_handle_load_replacing_existing_logs(self):
        """Test that load replaces existing logs."""
        logger = NotificationLogger()
        logger.log("event1", "info", "details1")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            # Create logger with different logs and save
            logger2 = NotificationLogger()
            logger2.log("event2", "warn", "details2")
            logger2.log("event3", "error", "details3")
            logger2.save(temp_path)

            # Load should replace logs
            logger.load(temp_path)

            logs = logger.get_logs()
            assert len(logs) == 2
            assert logs[0].event == "event2"
            assert logs[1].event == "event3"
        finally:
            Path(temp_path).unlink()


class TestNotificationLogDataclassValidation:
    """Test NotificationLog dataclass validation."""

    def test_should_accept_valid_info_level(self):
        """Test NotificationLog accepts 'info' level."""
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test",
            level="info",
            details="details"
        )
        assert log.level == "info"

    def test_should_accept_valid_warn_level(self):
        """Test NotificationLog accepts 'warn' level."""
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test",
            level="warn",
            details="details"
        )
        assert log.level == "warn"

    def test_should_accept_valid_error_level(self):
        """Test NotificationLog accepts 'error' level."""
        log = NotificationLog(
            timestamp=datetime.utcnow(),
            event="test",
            level="error",
            details="details"
        )
        assert log.level == "error"

    def test_should_reject_invalid_level(self):
        """Test NotificationLog rejects invalid level."""
        with pytest.raises(ValueError):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test",
                level="invalid",
                details="details"
            )

    def test_should_reject_uppercase_level(self):
        """Test NotificationLog rejects uppercase level."""
        with pytest.raises(ValueError):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test",
                level="INFO",
                details="details"
            )

    def test_should_reject_empty_level_string(self):
        """Test NotificationLog rejects empty level string."""
        with pytest.raises(ValueError):
            NotificationLog(
                timestamp=datetime.utcnow(),
                event="test",
                level="",
                details="details"
            )


class TestNotificationLoggerEdgeCases:
    """Test edge cases and special scenarios."""

    def test_should_handle_special_characters_in_event(self):
        """Test logging with special characters in event."""
        logger = NotificationLogger()
        logger.log("event!@#$%^&*()", "info", "details")
        logs = logger.get_logs()

        assert logs[0].event == "event!@#$%^&*()"

    def test_should_handle_special_characters_in_details(self):
        """Test logging with special characters in details."""
        logger = NotificationLogger()
        logger.log("event", "info", "details!@#$%^&*()")
        logs = logger.get_logs()

        assert logs[0].details == "details!@#$%^&*()"

    def test_should_handle_unicode_in_event(self):
        """Test logging with unicode in event."""
        logger = NotificationLogger()
        logger.log("событие", "info", "details")
        logs = logger.get_logs()

        assert logs[0].event == "событие"

    def test_should_handle_unicode_in_details(self):
        """Test logging with unicode in details."""
        logger = NotificationLogger()
        logger.log("event", "info", "деталі")
        logs = logger.get_logs()

        assert logs[0].details == "деталі"

    def test_should_handle_very_long_event_string(self):
        """Test logging with very long event string."""
        logger = NotificationLogger()
        long_event = "x" * 10000
        logger.log(long_event, "info", "details")
        logs = logger.get_logs()

        assert logs[0].event == long_event

    def test_should_handle_very_long_details_string(self):
        """Test logging with very long details string."""
        logger = NotificationLogger()
        long_details = "y" * 10000
        logger.log("event", "info", long_details)
        logs = logger.get_logs()

        assert logs[0].details == long_details

    def test_should_preserve_multiline_strings_in_save_load(self):
        """Test that multiline strings survive save/load."""
        logger = NotificationLogger()
        multiline_event = "event\nwith\nmultiple\nlines"
        multiline_details = "details\nwith\nmultiple\nlines"
        logger.log(multiline_event, "info", multiline_details)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            logger.save(temp_path)

            logger2 = NotificationLogger()
            logger2.load(temp_path)

            logs = logger2.get_logs()
            assert logs[0].event == multiline_event
            assert logs[0].details == multiline_details
        finally:
            Path(temp_path).unlink()

    def test_should_preserve_json_special_characters_in_save_load(self):
        """Test JSON special characters survive save/load."""
        logger = NotificationLogger()
        logger.log('event with "quotes"', "info", 'details with \\ backslash')

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            logger.save(temp_path)

            logger2 = NotificationLogger()
            logger2.load(temp_path)

            logs = logger2.get_logs()
            assert logs[0].event == 'event with "quotes"'
            assert logs[0].details == 'details with \\ backslash'
        finally:
            Path(temp_path).unlink()


class TestNotificationLoggerIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow_create_filter_save_load(self):
        """Test complete workflow: create, filter, save, load."""
        logger = NotificationLogger()
        logger.log("info1", "info", "info details 1")
        logger.log("warn1", "warn", "warn details 1")
        logger.log("error1", "error", "error details 1")
        logger.log("info2", "info", "info details 2")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            logger.save(temp_path)

            logger2 = NotificationLogger()
            logger2.load(temp_path)

            # Verify all logs loaded
            all_logs = logger2.get_logs()
            assert len(all_logs) == 4

            # Verify filtering works after load
            info_logs = logger2.get_logs(level="info")
            assert len(info_logs) == 2

            warn_logs = logger2.get_logs(level="warn")
            assert len(warn_logs) == 1

            error_logs = logger2.get_logs(level="error")
            assert len(error_logs) == 1
        finally:
            Path(temp_path).unlink()

    def test_multiple_save_load_cycles(self):
        """Test that logger can be saved and loaded multiple times."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = f.name

        try:
            # First cycle
            logger1 = NotificationLogger()
            logger1.log("event1", "info", "details1")
            logger1.save(temp_path)

            # Second cycle
            logger2 = NotificationLogger()
            logger2.load(temp_path)
            logger2.log("event2", "warn", "details2")
            logger2.save(temp_path)

            # Third cycle
            logger3 = NotificationLogger()
            logger3.load(temp_path)

            logs = logger3.get_logs()
            assert len(logs) == 2
            assert logs[0].event == "event1"
            assert logs[1].event == "event2"
        finally:
            Path(temp_path).unlink()
