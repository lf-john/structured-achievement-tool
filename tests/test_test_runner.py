"""Tests for src.execution.test_runner — Test execution and verification."""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import subprocess

from src.execution.test_runner import (
    run_tests,
    TestResult,
    get_test_command,
    execute_verifications,
    VerificationResult,
    _parse_test_counts,
    _detect_framework,
)


class TestRunTests:
    def test_passing_test(self, tmp_path):
        result = run_tests(str(tmp_path), "echo 'All tests passed'")
        assert result.passed
        assert result.exit_code == 0

    def test_failing_test(self, tmp_path):
        result = run_tests(str(tmp_path), "exit 1")
        assert not result.passed
        assert result.exit_code == 1

    def test_timeout_handling(self, tmp_path):
        result = run_tests(str(tmp_path), "sleep 10", timeout=1)
        assert not result.passed
        assert "timed out" in result.output

    def test_captures_output(self, tmp_path):
        result = run_tests(str(tmp_path), "echo 'test output'")
        assert "test output" in result.output


class TestParseTestCounts:
    def test_pytest_format(self):
        output = "5 passed, 2 failed in 1.5s"
        total, failures = _parse_test_counts(output)
        assert total == 7
        assert failures == 2

    def test_pytest_all_passed(self):
        output = "10 passed in 2.3s"
        total, failures = _parse_test_counts(output)
        assert total == 10
        assert failures == 0

    def test_jest_format(self):
        output = "Tests: 2 failed, 5 passed, 7 total"
        total, failures = _parse_test_counts(output)
        assert total == 7
        assert failures == 2

    def test_no_match_returns_zeros(self):
        total, failures = _parse_test_counts("no test output here")
        assert total == 0
        assert failures == 0


class TestDetectFramework:
    def test_pytest(self):
        assert _detect_framework("pytest tests/ -v") == "pytest"

    def test_jest(self):
        assert _detect_framework("npm test") == "jest"

    def test_phpunit(self):
        assert _detect_framework("php vendor/bin/phpunit") == "phpunit"

    def test_unknown(self):
        assert _detect_framework("make test") == "unknown"


class TestGetTestCommand:
    def test_explicit_verification_command(self):
        story = {
            "id": "US-001",
            "verification": [{"type": "command", "command": "pytest -x"}],
        }
        cmd = get_test_command(story, "/tmp")
        assert cmd == "pytest -x"

    def test_default_command(self):
        story = {"id": "US-001"}
        cmd = get_test_command(story, "/tmp")
        assert "pytest" in cmd

    def test_project_level_override(self):
        story = {"id": "US-001"}
        cmd = get_test_command(story, "/tmp", project_test_command="npm test")
        assert cmd == "npm test"

    def test_story_specific_test_file(self, tmp_path):
        story = {"id": "US-001", "title": "Implement slugify function"}
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_US_001_slugify.py").write_text("")
        cmd = get_test_command(story, str(tmp_path))
        assert "slugify" in cmd


class TestExecuteVerifications:
    def test_no_verifications_runs_default(self, tmp_path):
        story = {"id": "US-001"}
        result = execute_verifications(story, str(tmp_path), project_test_command="echo 'ok'")
        assert result.all_passed
        assert len(result.results) == 1

    def test_file_exists_check(self, tmp_path):
        (tmp_path / "expected.txt").write_text("content")
        story = {
            "id": "US-001",
            "verification": [
                {"type": "file_exists", "files": ["expected.txt", "missing.txt"]},
            ],
        }
        result = execute_verifications(story, str(tmp_path))
        assert not result.all_passed
        assert result.results[0]["passed"]  # expected.txt exists
        assert not result.results[1]["passed"]  # missing.txt doesn't

    def test_manual_always_passes(self):
        story = {
            "id": "US-001",
            "verification": [
                {"type": "manual", "description": "Check it visually"},
            ],
        }
        result = execute_verifications(story, "/tmp")
        assert result.all_passed
        assert result.results[0]["type"] == "manual"

    def test_command_verification(self, tmp_path):
        story = {
            "id": "US-001",
            "verification": [
                {"type": "command", "command": "echo 'pass'"},
            ],
        }
        result = execute_verifications(story, str(tmp_path))
        assert result.all_passed
