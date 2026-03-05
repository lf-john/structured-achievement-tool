"""
Test Runner — Execute tests and verification commands.

Ported from Ralph Pro runTests/executeVerifications (lines 1290-1380, 1770-1810).
Supports 5 verification types: command, file_exists, manual, test, tdd_test.
"""

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

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
        # Resolve bare 'pytest' to the venv's python -m pytest so it works
        # even when the venv's bin/ directory isn't on PATH
        resolved_command = test_command
        if test_command.startswith("pytest ") or test_command == "pytest":
            venv_pytest = os.path.join(os.path.dirname(sys.executable), "pytest")
            if os.path.isfile(venv_pytest):
                resolved_command = test_command.replace("pytest", venv_pytest, 1)

        result = subprocess.run(
            resolved_command,
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
    project_test_command: str | None = None,
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

    # Build search terms from story title (more specific than story ID)
    story_title = story.get("title", "")
    title_terms = []
    if story_title:
        # Extract meaningful keywords from title (skip common words)
        skip = {"implement", "create", "add", "update", "fix", "write", "test", "build", "make", "the", "for", "and", "with"}
        title_terms = [w.lower() for w in re.split(r'\W+', story_title) if len(w) > 3 and w.lower() not in skip]

    # Also check for recently created test files (within last 5 minutes)
    import time
    recent_cutoff = time.time() - 300  # 5 minutes ago

    candidates = []
    for test_dir in test_dirs:
        full_dir = os.path.join(working_directory, test_dir)
        if not os.path.isdir(full_dir):
            continue

        # Walk subdirectories too (tests may be in tests/utils/, tests/unit/, etc.)
        for dirpath, _dirnames, filenames in os.walk(full_dir):
            for f in filenames:
                if not (f.endswith(".py") and f.startswith("test_")):
                    continue

                filepath = os.path.join(dirpath, f)
                # Relative path from working directory for pytest command
                rel_path = os.path.relpath(filepath, working_directory)
                f_lower = f.lower()

                # Check story ID match (e.g., "US-001" in filename)
                id_match = story_id.lower().replace("-", "_") in f_lower or story_id.lower() in f_lower if story_id else False

                # Check title keyword match
                title_match = any(term in f_lower for term in title_terms) if title_terms else False

                # Check recency
                try:
                    mtime = os.path.getmtime(filepath)
                    is_recent = mtime > recent_cutoff
                except OSError:
                    is_recent = False

                # Priority (lower = better):
                # 0: ID + title + recent — ideal match, definitely our file
                # 1: ID + title (not recent) — strong match from a prior run
                # 2: ID + recent (no title match) — likely our file, just named differently
                # 3: title + recent — newly created file matching topic
                # 4: title only (not recent) — topical but could be from different task
                # 5: recent only — just created but no name correlation
                # Note: ID-only without title or recency is EXCLUDED — story IDs are
                # generic (US-001, US-002) and match unrelated old test files
                if id_match and title_match and is_recent:
                    candidates.append((0, rel_path))
                elif id_match and title_match:
                    candidates.append((1, rel_path))
                elif id_match and is_recent:
                    candidates.append((2, rel_path))
                elif title_match and is_recent:
                    candidates.append((3, rel_path))
                elif title_match:
                    candidates.append((4, rel_path))
                elif is_recent:
                    candidates.append((5, rel_path))

    if candidates:
        candidates.sort()
        _, best_path = candidates[0]
        return f"pytest {best_path} -v"

    # Project-level command (from DB or parameter)
    if project_test_command:
        return project_test_command

    # Try to load from project DB
    try:
        from src.db.database_manager import DatabaseManager
        db = DatabaseManager()
        projects = db.get_all_projects()
        for proj in projects:
            if proj.get("project_dir") and working_directory.startswith(proj["project_dir"]):
                if proj.get("test_command"):
                    return proj["test_command"]
                break
    except Exception:
        pass

    return "pytest tests/ -v"


def execute_verifications(
    story: dict,
    working_directory: str,
    project_test_command: str | None = None,
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
