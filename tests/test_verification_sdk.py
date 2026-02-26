"""
Tests for the Verification SDK.

Covers all 12 check methods across FileChecker, PortChecker, ServiceChecker,
and ConfigValidator, plus the run_checks utility function.
"""

import json
import os
import socket
import subprocess
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

import pytest

from src.execution.verification_sdk import (
    VerifyResult,
    FileChecker,
    PortChecker,
    ServiceChecker,
    ConfigValidator,
    run_checks,
)


# ---------------------------------------------------------------------------
# VerifyResult basics
# ---------------------------------------------------------------------------

class TestVerifyResult:
    def test_str_pass(self):
        r = VerifyResult(passed=True, checker="file", target="/tmp/x", message="ok")
        assert "[PASS]" in str(r)
        assert "file:/tmp/x" in str(r)

    def test_str_fail(self):
        r = VerifyResult(passed=False, checker="port", target="localhost:80", message="refused")
        assert "[FAIL]" in str(r)

    def test_default_details(self):
        r = VerifyResult(passed=True, checker="c", target="t", message="m")
        assert r.details == {}


# ---------------------------------------------------------------------------
# FileChecker
# ---------------------------------------------------------------------------

class TestFileCheckerExists:
    def test_file_exists(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("content")
        r = FileChecker().check_exists(str(f))
        assert r.passed is True
        assert r.checker == "file"
        assert "exists" in r.message

    def test_dir_exists(self, tmp_path):
        r = FileChecker().check_exists(str(tmp_path))
        assert r.passed is True
        assert r.details["is_directory"] is True

    def test_not_exists(self, tmp_path):
        r = FileChecker().check_exists(str(tmp_path / "nope"))
        assert r.passed is False
        assert "does not exist" in r.message


class TestFileCheckerPermissions:
    def test_correct_permissions(self, tmp_path):
        f = tmp_path / "secret"
        f.write_text("s3cr3t")
        os.chmod(str(f), 0o600)
        r = FileChecker().check_permissions(str(f), 0o600)
        assert r.passed is True

    def test_wrong_permissions(self, tmp_path):
        f = tmp_path / "open"
        f.write_text("public")
        os.chmod(str(f), 0o644)
        r = FileChecker().check_permissions(str(f), 0o600)
        assert r.passed is False
        assert "0o644" in r.message

    def test_missing_file(self, tmp_path):
        r = FileChecker().check_permissions(str(tmp_path / "gone"), 0o600)
        assert r.passed is False
        assert "does not exist" in r.message


class TestFileCheckerContains:
    def test_pattern_found(self, tmp_path):
        f = tmp_path / "cfg"
        f.write_text("server_port=8080\nhost=localhost\n")
        r = FileChecker().check_contains(str(f), r"server_port=\d+")
        assert r.passed is True
        assert r.details["matched"] == "server_port=8080"

    def test_pattern_not_found(self, tmp_path):
        f = tmp_path / "cfg"
        f.write_text("host=localhost\n")
        r = FileChecker().check_contains(str(f), r"password=")
        assert r.passed is False

    def test_missing_file(self, tmp_path):
        r = FileChecker().check_contains(str(tmp_path / "x"), "foo")
        assert r.passed is False


class TestFileCheckerNotContains:
    def test_absent_pattern(self, tmp_path):
        f = tmp_path / "clean.conf"
        f.write_text("host=localhost\n")
        r = FileChecker().check_not_contains(str(f), r"SECRET_KEY=")
        assert r.passed is True
        assert "correctly absent" in r.message

    def test_present_pattern(self, tmp_path):
        f = tmp_path / "dirty.conf"
        f.write_text("SECRET_KEY=abc123\n")
        r = FileChecker().check_not_contains(str(f), r"SECRET_KEY=")
        assert r.passed is False
        assert "unexpectedly found" in r.message

    def test_missing_file(self, tmp_path):
        r = FileChecker().check_not_contains(str(tmp_path / "nope"), "x")
        assert r.passed is False


# ---------------------------------------------------------------------------
# PortChecker
# ---------------------------------------------------------------------------

class TestPortCheckerListening:
    def test_port_open(self):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        with patch("src.execution.verification_sdk.socket.socket", return_value=mock_sock):
            r = PortChecker().check_listening("localhost", 8080)
        assert r.passed is True
        assert "listening" in r.message

    def test_port_closed(self):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111  # connection refused
        with patch("src.execution.verification_sdk.socket.socket", return_value=mock_sock):
            r = PortChecker().check_listening("localhost", 9999)
        assert r.passed is False

    def test_timeout(self):
        mock_sock = MagicMock()
        mock_sock.connect_ex.side_effect = socket.timeout("timed out")
        with patch("src.execution.verification_sdk.socket.socket", return_value=mock_sock):
            r = PortChecker().check_listening("10.0.0.1", 22, timeout=1)
        assert r.passed is False
        assert "timed out" in r.message

    def test_socket_error(self):
        with patch("src.execution.verification_sdk.socket.socket", side_effect=OSError("no route")):
            r = PortChecker().check_listening("bad.host", 80)
        assert r.passed is False
        assert "error" in r.message


class TestPortCheckerHTTP:
    def test_200_ok(self):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        with patch("src.execution.verification_sdk.urlopen", return_value=mock_resp):
            r = PortChecker().check_http("http://example.com")
        assert r.passed is True
        assert "200" in r.message

    def test_expected_404(self):
        err = HTTPError("http://x", 404, "Not Found", {}, None)
        with patch("src.execution.verification_sdk.urlopen", side_effect=err):
            r = PortChecker().check_http("http://x/missing", expected_status=404)
        assert r.passed is True

    def test_unexpected_500(self):
        err = HTTPError("http://x", 500, "Server Error", {}, None)
        with patch("src.execution.verification_sdk.urlopen", side_effect=err):
            r = PortChecker().check_http("http://x/broken")
        assert r.passed is False
        assert "500" in r.message

    def test_connection_refused(self):
        err = URLError("Connection refused")
        with patch("src.execution.verification_sdk.urlopen", side_effect=err):
            r = PortChecker().check_http("http://localhost:1")
        assert r.passed is False
        assert "URL error" in r.message


# ---------------------------------------------------------------------------
# ServiceChecker
# ---------------------------------------------------------------------------

class TestServiceCheckerSystemd:
    def test_active_user_service(self):
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="active\n", stderr=""
        )
        with patch("src.execution.verification_sdk.subprocess.run", return_value=result) as mock_run:
            r = ServiceChecker().check_systemd("sat.service", user=True)
        assert r.passed is True
        assert "active" in r.message
        # verify --user flag was passed
        call_args = mock_run.call_args[0][0]
        assert "--user" in call_args

    def test_inactive_system_service(self):
        result = subprocess.CompletedProcess(
            args=[], returncode=3, stdout="inactive\n", stderr=""
        )
        with patch("src.execution.verification_sdk.subprocess.run", return_value=result):
            r = ServiceChecker().check_systemd("nginx.service", user=False)
        assert r.passed is False
        assert "inactive" in r.message

    def test_failed_service(self):
        result = subprocess.CompletedProcess(
            args=[], returncode=3, stdout="failed\n", stderr=""
        )
        with patch("src.execution.verification_sdk.subprocess.run", return_value=result):
            r = ServiceChecker().check_systemd("broken.service")
        assert r.passed is False

    def test_systemctl_timeout(self):
        with patch(
            "src.execution.verification_sdk.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="systemctl", timeout=10),
        ):
            r = ServiceChecker().check_systemd("stuck.service")
        assert r.passed is False
        assert "timed out" in r.message


class TestServiceCheckerProcess:
    def test_process_running(self):
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1234\n5678\n", stderr=""
        )
        with patch("src.execution.verification_sdk.subprocess.run", return_value=result):
            r = ServiceChecker().check_process("python")
        assert r.passed is True
        assert "1234" in r.message
        assert r.details["pids"] == ["1234", "5678"]

    def test_process_not_running(self):
        result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )
        with patch("src.execution.verification_sdk.subprocess.run", return_value=result):
            r = ServiceChecker().check_process("nonexistent_proc")
        assert r.passed is False
        assert "not found" in r.message

    def test_pgrep_timeout(self):
        with patch(
            "src.execution.verification_sdk.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pgrep", timeout=10),
        ):
            r = ServiceChecker().check_process("hung")
        assert r.passed is False
        assert "timed out" in r.message


# ---------------------------------------------------------------------------
# ConfigValidator
# ---------------------------------------------------------------------------

class TestConfigValidatorJSON:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text(json.dumps({"key": "value", "n": 42}))
        r = ConfigValidator().check_json(str(f))
        assert r.passed is True
        assert "valid JSON" in r.message

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not json at all")
        r = ConfigValidator().check_json(str(f))
        assert r.passed is False
        assert "invalid JSON" in r.message

    def test_missing_file(self, tmp_path):
        r = ConfigValidator().check_json(str(tmp_path / "gone.json"))
        assert r.passed is False


class TestConfigValidatorYAML:
    def test_valid_yaml(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("server:\n  host: localhost\n  port: 8080\n")
        r = ConfigValidator().check_yaml(str(f))
        assert r.passed is True
        assert "valid YAML" in r.message

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(":\n  - :\n    bad: [unclosed\n")
        r = ConfigValidator().check_yaml(str(f))
        assert r.passed is False
        assert "invalid YAML" in r.message

    def test_yaml_no_module(self, tmp_path):
        f = tmp_path / "cfg.yaml"
        f.write_text("key: value\n")
        with patch.dict("sys.modules", {"yaml": None}):
            # Force reimport to trigger ImportError
            import importlib
            import src.execution.verification_sdk as mod
            # Directly patch the import inside the method
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

            def mock_import(name, *args, **kwargs):
                if name == "yaml":
                    raise ImportError("No module named 'yaml'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                r = ConfigValidator().check_yaml(str(f))
            assert r.passed is False
            assert "PyYAML not installed" in r.message

    def test_missing_file(self, tmp_path):
        r = ConfigValidator().check_yaml(str(tmp_path / "gone.yaml"))
        assert r.passed is False


class TestConfigValidatorINI:
    def test_valid_ini(self, tmp_path):
        f = tmp_path / "app.ini"
        f.write_text("[database]\nhost = localhost\nport = 5432\n\n[app]\ndebug = true\n")
        r = ConfigValidator().check_ini(str(f))
        assert r.passed is True
        assert "2 section" in r.message

    def test_invalid_ini(self, tmp_path):
        f = tmp_path / "bad.ini"
        # MissingSectionHeaderError: no section header
        f.write_text("key_without_section = value\n")
        r = ConfigValidator().check_ini(str(f))
        assert r.passed is False
        assert "invalid INI" in r.message

    def test_missing_file(self, tmp_path):
        r = ConfigValidator().check_ini(str(tmp_path / "gone.ini"))
        assert r.passed is False


class TestConfigValidatorEnvFile:
    def test_valid_env(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("# comment\nAPI_KEY=abc123\nDATABASE_URL=postgres://localhost/db\n\nDEBUG=1\n")
        r = ConfigValidator().check_env_file(str(f))
        assert r.passed is True
        assert "3 key" in r.message

    def test_missing_equals(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("GOOD_KEY=value\nbad line without equals\n")
        r = ConfigValidator().check_env_file(str(f))
        assert r.passed is False
        assert "missing '='" in r.message

    def test_invalid_key(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("123BAD=value\n")
        r = ConfigValidator().check_env_file(str(f))
        assert r.passed is False
        assert "invalid key" in r.message

    def test_empty_key(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("=value\n")
        r = ConfigValidator().check_env_file(str(f))
        assert r.passed is False
        assert "empty key" in r.message

    def test_comments_and_blanks_ok(self, tmp_path):
        f = tmp_path / "env"
        f.write_text("# full line comment\n\n  \n# another\n")
        r = ConfigValidator().check_env_file(str(f))
        assert r.passed is True
        assert "0 key" in r.message

    def test_missing_file(self, tmp_path):
        r = ConfigValidator().check_env_file(str(tmp_path / "gone"))
        assert r.passed is False


# ---------------------------------------------------------------------------
# run_checks utility
# ---------------------------------------------------------------------------

class TestRunChecks:
    def test_mixed_results(self, tmp_path):
        exists_file = tmp_path / "yes.txt"
        exists_file.write_text("hello")
        fc = FileChecker()
        results = run_checks([
            (fc.check_exists, str(exists_file)),
            (fc.check_exists, str(tmp_path / "nope")),
        ])
        assert len(results) == 2
        assert results[0].passed is True
        assert results[1].passed is False

    def test_empty_list(self):
        results = run_checks([])
        assert results == []

    def test_exception_in_check(self):
        """A broken callable should not crash run_checks; it yields a FAIL result."""
        def bad_check():
            raise RuntimeError("boom")

        results = run_checks([(bad_check,)])
        assert len(results) == 1
        assert results[0].passed is False
        assert "boom" in results[0].message

    def test_multi_checker_types(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"ok": true}')
        fc = FileChecker()
        cv = ConfigValidator()
        results = run_checks([
            (fc.check_exists, str(f)),
            (fc.check_contains, str(f), r'"ok"'),
            (cv.check_json, str(f)),
        ])
        assert all(r.passed for r in results)
        assert len(results) == 3
