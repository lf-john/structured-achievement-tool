"""Tests for src/execution/failure_monitor.py — Layer 1 failure detection."""

import os
import time
from unittest.mock import patch, mock_open

import pytest

from src.execution.failure_monitor import (
    FailureContext,
    FailureMonitor,
    DEFAULT_FAILURE_PATTERNS,
    _truncate,
    _parse_meminfo,
)


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------


@pytest.fixture
def monitor(tmp_path):
    """FailureMonitor writing debug stories to tmp_path."""
    return FailureMonitor(output_dir=str(tmp_path), rate_limit_seconds=600)


@pytest.fixture
def context():
    """A minimal FailureContext."""
    return FailureContext(
        task_file="/tasks/sat-enhancements/004_proactive_agency.md",
        task_name="004_proactive_agency",
        exit_code=1,
        stderr="Traceback (most recent call last):\n  File ...\nKeyError: 'missing_key'\n",
        stdout="Starting task...\nStep 1 complete\n",
        log_tail="2026-02-25 12:00:00 - ERROR - task crashed\n",
        timestamp=1740000000.0,
    )


# ---------------------------------------------------------------
# Failure detection
# ---------------------------------------------------------------


class TestDetectFailure:
    def test_nonzero_exit_code(self, monitor):
        assert monitor.detect_failure(1, "", "") is True
        assert monitor.detect_failure(137, "", "") is True

    def test_zero_exit_code_clean_output(self, monitor):
        assert monitor.detect_failure(0, "all good", "") is False

    def test_zero_exit_code_with_error_in_stderr(self, monitor):
        assert monitor.detect_failure(0, "", "Error: something broke") is True

    def test_zero_exit_code_with_traceback(self, monitor):
        assert monitor.detect_failure(0, "Traceback (most recent call last):", "") is True

    def test_zero_exit_code_with_exception(self, monitor):
        assert monitor.detect_failure(0, "", "RuntimeException thrown") is True

    def test_zero_exit_code_with_exit_code_pattern(self, monitor):
        assert monitor.detect_failure(0, "exit code: 2", "") is True

    def test_zero_exit_code_with_failed(self, monitor):
        assert monitor.detect_failure(0, "Task failed", "") is True

    def test_zero_exit_code_with_timeout(self, monitor):
        assert monitor.detect_failure(0, "", "timeout waiting for response") is True

    def test_zero_exit_code_with_sigkill(self, monitor):
        assert monitor.detect_failure(0, "process received SIGKILL", "") is True

    def test_no_false_positive_on_innocuous_text(self, monitor):
        # Words that could look like errors but aren't matched by patterns
        assert monitor.detect_failure(0, "everything is fine", "no issues") is False

    def test_no_false_positive_on_empty(self, monitor):
        assert monitor.detect_failure(0, "", "") is False


# ---------------------------------------------------------------
# Custom patterns
# ---------------------------------------------------------------


class TestCustomPatterns:
    def test_custom_pattern_matches(self, tmp_path):
        mon = FailureMonitor(
            output_dir=str(tmp_path),
            patterns=[r"CUSTOM_FAIL_\d+"],
        )
        assert mon.detect_failure(0, "CUSTOM_FAIL_42 happened", "") is True

    def test_custom_pattern_no_match(self, tmp_path):
        mon = FailureMonitor(
            output_dir=str(tmp_path),
            patterns=[r"CUSTOM_FAIL_\d+"],
        )
        # Default patterns are NOT used when custom patterns are supplied
        assert mon.detect_failure(0, "Traceback ...", "") is False

    def test_custom_pattern_exit_code_still_works(self, tmp_path):
        mon = FailureMonitor(
            output_dir=str(tmp_path),
            patterns=[r"CUSTOM_FAIL_\d+"],
        )
        # Non-zero exit code always triggers, regardless of patterns
        assert mon.detect_failure(1, "everything fine", "") is True


# ---------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------


class TestRateLimiting:
    def test_not_rate_limited_initially(self, monitor):
        assert monitor.is_rate_limited("some_task") is False

    def test_rate_limited_after_debug_story(self, monitor, context, tmp_path):
        monitor.create_debug_story(context)
        assert monitor.is_rate_limited(context.task_name) is True

    def test_not_rate_limited_after_expiry(self, monitor, context, tmp_path):
        monitor.create_debug_story(context)
        # Pretend the last story was created 11 minutes ago
        monitor._last_debug_story[context.task_name] = time.time() - 700
        assert monitor.is_rate_limited(context.task_name) is False

    def test_create_returns_none_when_rate_limited(self, monitor, context):
        monitor.create_debug_story(context)
        result = monitor.create_debug_story(context)
        assert result is None

    def test_different_tasks_not_rate_limited(self, monitor, context):
        monitor.create_debug_story(context)
        other = FailureContext(
            task_file="/tasks/other.md",
            task_name="other_task",
            exit_code=1,
            stderr="boom",
            stdout="",
            log_tail="",
        )
        result = monitor.create_debug_story(other)
        assert result is not None


# ---------------------------------------------------------------
# Debug story creation
# ---------------------------------------------------------------


class TestDebugStoryCreation:
    def test_file_created(self, monitor, context, tmp_path):
        path = monitor.create_debug_story(context)
        assert path is not None
        assert os.path.isfile(path)

    def test_file_in_output_dir(self, monitor, context, tmp_path):
        path = monitor.create_debug_story(context)
        assert path.startswith(str(tmp_path))

    def test_filename_contains_task_name(self, monitor, context):
        path = monitor.create_debug_story(context)
        assert context.task_name in os.path.basename(path)

    def test_filename_starts_with_debug(self, monitor, context):
        path = monitor.create_debug_story(context)
        assert os.path.basename(path).startswith("debug_")

    def test_content_includes_task_file(self, monitor, context):
        path = monitor.create_debug_story(context)
        content = open(path).read()
        assert context.task_file in content

    def test_content_includes_exit_code(self, monitor, context):
        path = monitor.create_debug_story(context)
        content = open(path).read()
        assert str(context.exit_code) in content

    def test_content_includes_stderr(self, monitor, context):
        path = monitor.create_debug_story(context)
        content = open(path).read()
        assert "KeyError" in content

    def test_content_includes_stdout(self, monitor, context):
        path = monitor.create_debug_story(context)
        content = open(path).read()
        assert "Step 1 complete" in content

    def test_content_includes_log_tail(self, monitor, context):
        path = monitor.create_debug_story(context)
        content = open(path).read()
        assert "task crashed" in content

    def test_content_ends_with_pending(self, monitor, context):
        path = monitor.create_debug_story(context)
        content = open(path).read()
        assert "<Pending>" in content

    def test_content_has_markdown_structure(self, monitor, context):
        path = monitor.create_debug_story(context)
        content = open(path).read()
        assert content.startswith("# Debug:")
        assert "## Failure Summary" in content
        assert "## Stderr" in content
        assert "## Stdout" in content
        assert "## Log Tail" in content
        assert "## Environment" in content
        assert "## Instructions" in content

    def test_creates_output_dir_if_missing(self, tmp_path):
        nested = str(tmp_path / "a" / "b" / "c")
        mon = FailureMonitor(output_dir=nested)
        ctx = FailureContext(
            task_file="t.md",
            task_name="t",
            exit_code=1,
            stderr="",
            stdout="",
            log_tail="",
        )
        path = mon.create_debug_story(ctx)
        assert os.path.isfile(path)


# ---------------------------------------------------------------
# Log tail capture
# ---------------------------------------------------------------


class TestLogTailCapture:
    def test_capture_existing_log(self, monitor, tmp_path):
        log = tmp_path / "test.log"
        lines = [f"line {i}\n" for i in range(100)]
        log.write_text("".join(lines))
        tail = monitor.capture_log_tail(str(log), lines=10)
        assert "line 90" in tail
        assert "line 99" in tail
        # First lines should NOT be in the tail
        assert "line 0\n" not in tail

    def test_capture_short_log(self, monitor, tmp_path):
        log = tmp_path / "short.log"
        log.write_text("only one line\n")
        tail = monitor.capture_log_tail(str(log), lines=50)
        assert "only one line" in tail

    def test_capture_missing_log(self, monitor):
        tail = monitor.capture_log_tail("/nonexistent/path/sat.log")
        assert "not found" in tail

    def test_capture_default_lines(self, monitor, tmp_path):
        log = tmp_path / "big.log"
        lines = [f"entry {i}\n" for i in range(200)]
        log.write_text("".join(lines))
        tail = monitor.capture_log_tail(str(log))
        # Default is 50 lines — last entry should be present
        assert "entry 199" in tail
        # First entry should not
        assert "entry 0\n" not in tail


# ---------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------


class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("a\nb\nc", 10) == "a\nb\nc"

    def test_long_text_truncated(self):
        text = "\n".join(f"line{i}" for i in range(20))
        result = _truncate(text, 5)
        assert "line0" in result
        assert "line4" in result
        assert "line5" not in result
        assert "15 more lines omitted" in result

    def test_empty_text(self):
        assert _truncate("", 10) == ""

    def test_none_handled(self):
        # None should not crash — returns empty
        assert _truncate(None, 10) == ""


class TestParseMeminfo:
    def test_parse_valid(self):
        meminfo = "MemTotal:       16384000 kB\nMemAvailable:    8192000 kB\n"
        assert _parse_meminfo(meminfo, "MemTotal") == 16384000
        assert _parse_meminfo(meminfo, "MemAvailable") == 8192000

    def test_parse_missing_key(self):
        assert _parse_meminfo("MemTotal: 100 kB\n", "MemFree") is None

    def test_parse_empty(self):
        assert _parse_meminfo("", "MemTotal") is None


# ---------------------------------------------------------------
# Environment capture
# ---------------------------------------------------------------


class TestEnvContext:
    def test_capture_returns_string(self, monitor):
        result = monitor.capture_env_context()
        assert isinstance(result, str)
        assert "Disk:" in result

    @patch("shutil.disk_usage", side_effect=OSError("no disk"))
    def test_disk_error_handled(self, _mock, monitor):
        result = monitor.capture_env_context()
        assert "unavailable" in result
