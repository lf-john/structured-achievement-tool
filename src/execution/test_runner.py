"""
Test Runner — Execute tests and verification commands.

Ported from Ralph Pro runTests/executeVerifications (lines 1290-1380, 1770-1810).
Supports 5 verification types: command, file_exists, manual, test, tdd_test.
"""

import os
import subprocess
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TEST_TIMEOUT = 120  # 2 minutes


@dataclass
class TestResult:
    """Result of a test execution."""
    passed: bool
    output: str = ""
    exit_code: int = 0
    total: int = 0
    failures: int = 0
    framework: str = ""


@dataclass
class VerificationResult:
    """Result of all verification checks for a story."""
    all_passed: bool
    results: list = field(default_factory=list)


def run_tests(
    working_directory: str,
    test_command: str = "pytest",
    timeout: int = DEFAULT_TEST_TIMEOUT,
) -> TestResult:
    """Run a test command and capture results.

    Args:
        working_directory: Directory to run tests in
        test_command: Shell command to execute
        timeout: Timeout in seconds

    Returns:
        TestResult with pass/fail status and output
    """
    try:
        result = subprocess.run(
            test_command,
            shell=True,
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = result.stdout + ("\n" + result.stderr if result.stderr else "")
        passed = result.returncode == 0

        # Try to parse test counts from output
        total, failures = _parse_test_counts(output)

        return TestResult(
            passed=passed,
            output=output,
            exit_code=result.returncode,
            total=total,
            failures=failures,
            framework=_detect_framework(test_command),
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            passed=False,
            output=f"Test execution timed out after {timeout}s",
            exit_code=-1,
        )
    except Exception as e:
        return TestResult(
            passed=False,
            output=f"Test execution error: {e}",
            exit_code=-1,
        )


def _parse_test_counts(output: str) -> tuple[int, int]:
    """Extract test counts from output. Returns (total, failures)."""
    # pytest format: "5 passed, 2 failed"
    pytest_match = re.search(r'(\d+) passed', output)
    pytest_fail = re.search(r'(\d+) failed', output)
    if pytest_match:
        passed = int(pytest_match.group(1))
        failed = int(pytest_fail.group(1)) if pytest_fail else 0
        return passed + failed, failed

    # npm/jest format: "Tests: 2 failed, 5 passed, 7 total"
    jest_match = re.search(r'Tests:\s*(?:(\d+) failed,\s*)?(\d+) passed,\s*(\d+) total', output)
    if jest_match:
        total = int(jest_match.group(3))
        failed = int(jest_match.group(1)) if jest_match.group(1) else 0
        return total, failed

    return 0, 0


def _detect_framework(command: str) -> str:
    """Detect the test framework from the command."""
    if "pytest" in command:
        return "pytest"
    elif "npm test" in command or "jest" in command:
        return "jest"
    elif "php" in command:
        return "phpunit"
    elif "node" in command:
        return "node"
    return "unknown"


def get_test_command(
    story: dict,
    working_directory: str,
    project_test_command: Optional[str] = None,
) -> str:
    """Determine the best test command for a story.

    Priority:
    1. Explicit command in story.verification[].command
    2. Story-specific test file (US-001_*.test.py or similar)
    3. Project-level test command
    4. Default: pytest
    """
    story_id = story.get("id", "")

    # Check verification entries for explicit commands
    for v in story.get("verification", []):
        if v.get("type") in ("command", "test", "tdd_test") and v.get("command"):
            return v["command"]

    # Search for story-specific test files
    test_dirs = ["tests", "test", "custom/tests"]
    for test_dir in test_dirs:
        full_dir = os.path.join(working_directory, test_dir)
        if not os.path.isdir(full_dir):
            continue

        for f in os.listdir(full_dir):
            if story_id.replace("-", "_") in f or story_id in f:
                if f.endswith(".test.py") or f.endswith("_test.py"):
                    return f"pytest {os.path.join(test_dir, f)} -v"
                elif f.endswith(".test.js"):
                    return f"node {os.path.join(test_dir, f)}"
                elif f.endswith(".test.php"):
                    return f"php {os.path.join(test_dir, f)}"

    # Project-level command
    if project_test_command:
        return project_test_command

    return "pytest tests/ -v"


def execute_verifications(
    story: dict,
    working_directory: str,
    project_test_command: Optional[str] = None,
) -> VerificationResult:
    """Execute all verification checks for a story.

    Supports 5 types:
    - command/test/tdd_test: Run shell command, check exit code
    - file_exists: Check if files exist
    - manual: Skip (handled by VERIFY phase LLM audit)
    """
    verifications = story.get("verification", [])
    if not verifications:
        # Default: run tests
        test_cmd = get_test_command(story, working_directory, project_test_command)
        result = run_tests(working_directory, test_cmd)
        return VerificationResult(
            all_passed=result.passed,
            results=[{"type": "test", "command": test_cmd, "passed": result.passed, "output": result.output}],
        )

    results = []
    all_passed = True

    for v in verifications:
        v_type = v.get("type", "manual")

        if v_type in ("command", "test", "tdd_test"):
            cmd = v.get("command", get_test_command(story, working_directory, project_test_command))
            result = run_tests(working_directory, cmd)
            results.append({
                "type": v_type,
                "command": cmd,
                "passed": result.passed,
                "output": result.output[:2000],
            })
            if not result.passed:
                all_passed = False

        elif v_type == "file_exists":
            files = v.get("files", [])
            for f in files:
                exists = os.path.exists(os.path.join(working_directory, f))
                results.append({
                    "type": "file_exists",
                    "file": f,
                    "passed": exists,
                })
                if not exists:
                    all_passed = False

        elif v_type == "manual":
            results.append({
                "type": "manual",
                "description": v.get("description", "Manual verification"),
                "passed": True,  # Delegated to VERIFY phase
            })

        else:
            logger.debug(f"Unknown verification type: {v_type}, skipping")
            results.append({
                "type": v_type,
                "passed": True,
                "note": "Skipped: unknown type",
            })

    return VerificationResult(all_passed=all_passed, results=results)
