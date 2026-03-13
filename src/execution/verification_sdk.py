"""
Verification SDK for SAT — standardized verification utilities for VERIFY phases.

Provides FileChecker, PortChecker, ServiceChecker, and ConfigValidator classes
that return uniform VerifyResult objects. Used across all workflow types.
"""

import configparser
import json
import logging
import os
import re
import socket
import stat
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    """Standardized result from any verification check."""

    passed: bool
    checker: str  # "file", "port", "service", "config"
    target: str  # what was checked
    message: str  # human-readable result
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.checker}:{self.target} — {self.message}"


class FileChecker:
    """Verify filesystem state: existence, permissions, content."""

    CHECKER_NAME = "file"

    def check_exists(self, path: str) -> VerifyResult:
        """Verify that a file or directory exists at the given path."""
        exists = os.path.exists(path)
        is_dir = os.path.isdir(path) if exists else False
        kind = "directory" if is_dir else "file"
        return VerifyResult(
            passed=exists,
            checker=self.CHECKER_NAME,
            target=path,
            message=f"{kind} exists" if exists else "path does not exist",
            details={"is_directory": is_dir} if exists else {},
        )

    def check_permissions(self, path: str, expected_mode: int) -> VerifyResult:
        """Check that a file's permission bits match expected_mode (e.g. 0o600)."""
        if not os.path.exists(path):
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message="path does not exist, cannot check permissions",
            )
        actual_mode = stat.S_IMODE(os.stat(path).st_mode)
        passed = actual_mode == expected_mode
        return VerifyResult(
            passed=passed,
            checker=self.CHECKER_NAME,
            target=path,
            message=(
                f"permissions match ({oct(expected_mode)})"
                if passed
                else f"expected {oct(expected_mode)}, got {oct(actual_mode)}"
            ),
            details={"expected": oct(expected_mode), "actual": oct(actual_mode)},
        )

    def check_contains(self, path: str, pattern: str) -> VerifyResult:
        """Verify file content matches the given regex pattern."""
        if not os.path.isfile(path):
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message="file does not exist, cannot check content",
            )
        try:
            with open(path, errors="replace") as f:
                content = f.read()
            match = re.search(pattern, content)
            return VerifyResult(
                passed=match is not None,
                checker=self.CHECKER_NAME,
                target=path,
                message=(f"pattern '{pattern}' found" if match else f"pattern '{pattern}' not found"),
                details={"pattern": pattern, "matched": match.group(0) if match else None},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"error reading file: {e}",
                details={"error": str(e)},
            )

    def check_not_contains(self, path: str, pattern: str) -> VerifyResult:
        """Verify file content does NOT match the given regex pattern."""
        if not os.path.isfile(path):
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message="file does not exist, cannot check content",
            )
        try:
            with open(path, errors="replace") as f:
                content = f.read()
            match = re.search(pattern, content)
            return VerifyResult(
                passed=match is None,
                checker=self.CHECKER_NAME,
                target=path,
                message=(
                    f"pattern '{pattern}' correctly absent"
                    if match is None
                    else f"pattern '{pattern}' unexpectedly found"
                ),
                details={"pattern": pattern, "matched": match.group(0) if match else None},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"error reading file: {e}",
                details={"error": str(e)},
            )


class PortChecker:
    """Verify network connectivity: TCP ports and HTTP endpoints."""

    CHECKER_NAME = "port"

    def check_listening(self, host: str, port: int, timeout: int = 5) -> VerifyResult:
        """Test TCP connectivity to host:port."""
        target = f"{host}:{port}"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            passed = result == 0
            return VerifyResult(
                passed=passed,
                checker=self.CHECKER_NAME,
                target=target,
                message="port is listening" if passed else f"connection refused or timed out (errno {result})",
                details={"host": host, "port": port, "errno": result},
            )
        except TimeoutError:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=target,
                message="connection timed out",
                details={"host": host, "port": port, "timeout": timeout},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=target,
                message=f"error: {e}",
                details={"host": host, "port": port, "error": str(e)},
            )

    def check_http(self, url: str, expected_status: int = 200, timeout: int = 10) -> VerifyResult:
        """Perform an HTTP GET and verify the response status code."""
        try:
            req = Request(url, method="GET")
            resp = urlopen(req, timeout=timeout)
            actual_status = resp.getcode()
            passed = actual_status == expected_status
            return VerifyResult(
                passed=passed,
                checker=self.CHECKER_NAME,
                target=url,
                message=(
                    f"HTTP {actual_status} (expected {expected_status})"
                    if passed
                    else f"HTTP {actual_status}, expected {expected_status}"
                ),
                details={"url": url, "expected_status": expected_status, "actual_status": actual_status},
            )
        except HTTPError as e:
            actual_status = e.code
            passed = actual_status == expected_status
            return VerifyResult(
                passed=passed,
                checker=self.CHECKER_NAME,
                target=url,
                message=(
                    f"HTTP {actual_status} (expected {expected_status})"
                    if passed
                    else f"HTTP {actual_status}, expected {expected_status}"
                ),
                details={"url": url, "expected_status": expected_status, "actual_status": actual_status},
            )
        except URLError as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=url,
                message=f"URL error: {e.reason}",
                details={"url": url, "error": str(e.reason)},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=url,
                message=f"error: {e}",
                details={"url": url, "error": str(e)},
            )


class ServiceChecker:
    """Verify system services and running processes."""

    CHECKER_NAME = "service"

    def check_systemd(self, service_name: str, user: bool = True) -> VerifyResult:
        """Check if a systemd service is active via systemctl is-active."""
        cmd = ["systemctl"]
        if user:
            cmd.append("--user")
        cmd.extend(["is-active", service_name])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            state = result.stdout.strip()
            passed = state == "active"
            return VerifyResult(
                passed=passed,
                checker=self.CHECKER_NAME,
                target=service_name,
                message=f"systemd state: {state}",
                details={
                    "service": service_name,
                    "user": user,
                    "state": state,
                    "returncode": result.returncode,
                },
            )
        except subprocess.TimeoutExpired:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=service_name,
                message="systemctl timed out",
                details={"service": service_name, "user": user},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=service_name,
                message=f"error checking service: {e}",
                details={"service": service_name, "error": str(e)},
            )

    def check_process(self, process_name: str) -> VerifyResult:
        """Verify a process is running via pgrep."""
        try:
            result = subprocess.run(["pgrep", "-f", process_name], capture_output=True, text=True, timeout=10)
            pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            passed = result.returncode == 0 and len(pids) > 0
            return VerifyResult(
                passed=passed,
                checker=self.CHECKER_NAME,
                target=process_name,
                message=(f"process running (PIDs: {', '.join(pids)})" if passed else "process not found"),
                details={
                    "process": process_name,
                    "pids": pids if passed else [],
                    "returncode": result.returncode,
                },
            )
        except subprocess.TimeoutExpired:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=process_name,
                message="pgrep timed out",
                details={"process": process_name},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=process_name,
                message=f"error checking process: {e}",
                details={"process": process_name, "error": str(e)},
            )


class ConfigValidator:
    """Validate configuration file syntax for common formats."""

    CHECKER_NAME = "config"

    def check_json(self, path: str) -> VerifyResult:
        """Validate JSON syntax."""
        if not os.path.isfile(path):
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message="file does not exist",
            )
        try:
            with open(path) as f:
                data = json.load(f)
            return VerifyResult(
                passed=True,
                checker=self.CHECKER_NAME,
                target=path,
                message="valid JSON",
                details={"type": type(data).__name__},
            )
        except json.JSONDecodeError as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"invalid JSON: {e}",
                details={"error": str(e), "line": e.lineno, "col": e.colno},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"error reading file: {e}",
                details={"error": str(e)},
            )

    def check_yaml(self, path: str) -> VerifyResult:
        """Validate YAML syntax. Gracefully handles missing yaml module."""
        if not os.path.isfile(path):
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message="file does not exist",
            )
        try:
            import yaml
        except ImportError:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message="PyYAML not installed, cannot validate YAML",
                details={"error": "ImportError: yaml module not available"},
            )
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            return VerifyResult(
                passed=True,
                checker=self.CHECKER_NAME,
                target=path,
                message="valid YAML",
                details={"type": type(data).__name__ if data is not None else "empty"},
            )
        except yaml.YAMLError as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"invalid YAML: {e}",
                details={"error": str(e)},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"error reading file: {e}",
                details={"error": str(e)},
            )

    def check_ini(self, path: str) -> VerifyResult:
        """Validate INI syntax using configparser."""
        if not os.path.isfile(path):
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message="file does not exist",
            )
        try:
            parser = configparser.ConfigParser()
            with open(path) as f:
                parser.read_file(f)
            sections = parser.sections()
            return VerifyResult(
                passed=True,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"valid INI ({len(sections)} section(s))",
                details={"sections": sections},
            )
        except configparser.Error as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"invalid INI: {e}",
                details={"error": str(e)},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"error reading file: {e}",
                details={"error": str(e)},
            )

    def check_env_file(self, path: str) -> VerifyResult:
        """Validate KEY=VALUE format (systemd-style env file, no 'export' prefix)."""
        if not os.path.isfile(path):
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message="file does not exist",
            )
        try:
            with open(path) as f:
                lines = f.readlines()

            errors = []
            key_count = 0
            for lineno, raw_line in enumerate(lines, start=1):
                line = raw_line.strip()
                # blank lines and comments are fine
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    errors.append(f"line {lineno}: missing '=' separator")
                    continue
                key, _, _value = line.partition("=")
                if not key:
                    errors.append(f"line {lineno}: empty key")
                    continue
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                    errors.append(f"line {lineno}: invalid key '{key}'")
                    continue
                key_count += 1

            passed = len(errors) == 0
            return VerifyResult(
                passed=passed,
                checker=self.CHECKER_NAME,
                target=path,
                message=(
                    f"valid env file ({key_count} key(s))"
                    if passed
                    else f"env file has {len(errors)} error(s): {'; '.join(errors)}"
                ),
                details={"key_count": key_count, "errors": errors},
            )
        except Exception as e:
            return VerifyResult(
                passed=False,
                checker=self.CHECKER_NAME,
                target=path,
                message=f"error reading file: {e}",
                details={"error": str(e)},
            )


class DelayedChecker:
    """Retry/wait loop for delayed verification checks."""

    def check_with_retry(
        self,
        check_fn: Callable,
        wait_seconds: float,
        max_attempts: int,
        description: str,
    ) -> VerifyResult:
        """Run check_fn up to max_attempts times, sleeping wait_seconds between failures."""
        result = None
        for attempt in range(max_attempts):
            result = check_fn()
            if result.passed:
                return result
            if attempt < max_attempts - 1:
                time.sleep(wait_seconds)
        return result


def run_checks(checks: list[tuple]) -> list[VerifyResult]:
    """
    Run multiple verification checks and return all results.

    Each entry in `checks` is a tuple of (method, *args) where method is a bound
    method on one of the checker classes.

    Example:
        fc = FileChecker()
        pc = PortChecker()
        results = run_checks([
            (fc.check_exists, "/etc/hosts"),
            (fc.check_permissions, "/etc/shadow", 0o640),
            (pc.check_listening, "localhost", 8080),
        ])
    """
    results: list[VerifyResult] = []
    for entry in checks:
        method = entry[0]
        args = entry[1:]
        try:
            result = method(*args)
            results.append(result)
        except Exception as e:
            logger.error("Verification check %s failed with exception: %s", method, e)
            results.append(
                VerifyResult(
                    passed=False,
                    checker="unknown",
                    target=str(args),
                    message=f"check raised exception: {e}",
                    details={"error": str(e), "method": str(method)},
                )
            )
    return results
