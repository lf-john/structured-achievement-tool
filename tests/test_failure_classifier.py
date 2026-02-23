"""Tests for src.agents.failure_classifier — Pattern-based failure classification."""

import pytest

from src.agents.failure_classifier import (
    classify_failure,
    FailureType,
    FailureSeverity,
    FailureClassification,
)


class TestTransientFailures:
    def test_timeout(self):
        result = classify_failure(1, "Error: timeout waiting for response")
        assert result.failure_type == FailureType.TIMEOUT
        assert result.severity == FailureSeverity.TRANSIENT
        assert result.should_retry

    def test_timed_out(self):
        result = classify_failure(1, "Connection timed out after 30 seconds")
        assert result.failure_type == FailureType.TIMEOUT

    def test_rate_limit_429(self):
        result = classify_failure(1, "Error: 429 Too Many Requests")
        assert result.failure_type == FailureType.RATE_LIMIT
        assert result.severity == FailureSeverity.TRANSIENT

    def test_rate_limit_text(self):
        result = classify_failure(1, "Rate limit exceeded, please retry")
        assert result.failure_type == FailureType.RATE_LIMIT

    def test_network_econnrefused(self):
        result = classify_failure(1, "ECONNREFUSED 127.0.0.1:11434")
        assert result.failure_type == FailureType.NETWORK
        assert result.severity == FailureSeverity.TRANSIENT

    def test_network_connection_refused(self):
        result = classify_failure(1, "Connection refused to API server")
        assert result.failure_type == FailureType.NETWORK

    def test_oom(self):
        result = classify_failure(1, "MemoryError: Cannot allocate 4GB")
        assert result.failure_type == FailureType.OOM
        assert result.severity == FailureSeverity.TRANSIENT

    def test_disk_full(self):
        result = classify_failure(1, "No space left on device")
        assert result.failure_type == FailureType.DISK_FULL
        assert result.severity == FailureSeverity.TRANSIENT

    def test_lock_contention(self):
        result = classify_failure(1, "resource busy or locked")
        assert result.failure_type == FailureType.LOCK_CONTENTION

    def test_api_500(self):
        result = classify_failure(1, "API Error: 500 Internal Server Error")
        assert result.failure_type == FailureType.API_ERROR
        assert result.severity == FailureSeverity.TRANSIENT


class TestPersistentFailures:
    def test_import_error(self):
        result = classify_failure(1, "ImportError: No module named 'missing'")
        assert result.failure_type == FailureType.IMPORT_ERROR
        assert result.severity == FailureSeverity.PERSISTENT
        assert result.create_debug_story

    def test_module_not_found(self):
        result = classify_failure(1, "ModuleNotFoundError: No module named 'x'")
        assert result.failure_type == FailureType.IMPORT_ERROR

    def test_syntax_error(self):
        result = classify_failure(1, "SyntaxError: unexpected EOF while parsing")
        assert result.failure_type == FailureType.SYNTAX_ERROR
        assert result.severity == FailureSeverity.PERSISTENT

    def test_indentation_error(self):
        result = classify_failure(1, "IndentationError: unexpected indent")
        assert result.failure_type == FailureType.SYNTAX_ERROR

    def test_test_failure(self):
        result = classify_failure(1, "FAILED tests/test_foo.py::test_bar")
        assert result.failure_type == FailureType.TEST_FAILURE
        assert result.severity == FailureSeverity.PERSISTENT

    def test_assertion_error(self):
        result = classify_failure(1, "AssertionError: expected 5 but got 3")
        assert result.failure_type == FailureType.TEST_FAILURE


class TestFatalFailures:
    def test_permission_error(self):
        result = classify_failure(1, "PermissionError: [Errno 13] Permission denied")
        assert result.failure_type == FailureType.PERMISSION_ERROR
        assert result.severity == FailureSeverity.FATAL
        assert not result.should_retry

    def test_blocked(self):
        result = classify_failure(1, "<promise>BLOCKED</promise>")
        assert result.failure_type == FailureType.BLOCKED
        assert result.severity == FailureSeverity.FATAL


class TestExitCodeClassification:
    def test_sigkill_137(self):
        result = classify_failure(137, "")
        assert result.failure_type == FailureType.OOM
        assert result.severity == FailureSeverity.TRANSIENT

    def test_minus_one_process_failed(self):
        result = classify_failure(-1, "")
        assert result.failure_type == FailureType.UNKNOWN
        assert result.severity == FailureSeverity.TRANSIENT

    def test_unknown_exit_code_defaults_to_code_bug(self):
        result = classify_failure(42, "some random output")
        assert result.failure_type == FailureType.CODE_BUG
        assert result.severity == FailureSeverity.PERSISTENT


class TestStderrHandling:
    def test_error_in_stderr(self):
        result = classify_failure(1, "", stderr="ECONNREFUSED localhost:5000")
        assert result.failure_type == FailureType.NETWORK
        assert result.severity == FailureSeverity.TRANSIENT
