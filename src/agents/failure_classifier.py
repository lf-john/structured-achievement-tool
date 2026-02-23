"""
Failure Classifier — Classify failures as transient or persistent.

Transient failures (timeout, rate limit, network, OOM) → auto-retry.
Persistent failures (code bugs, test failures, import errors) → create Debug story.

Complexity 1-2: pure Python pattern matching, no LLM needed.
"""

import re
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class FailureType(str, Enum):
    # Transient — auto-retry with backoff
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    OOM = "oom"
    DISK_FULL = "disk_full"
    LOCK_CONTENTION = "lock_contention"
    API_ERROR = "api_error"

    # Persistent — needs intervention or Debug story
    CODE_BUG = "code_bug"
    TEST_FAILURE = "test_failure"
    IMPORT_ERROR = "import_error"
    SYNTAX_ERROR = "syntax_error"
    BLOCKED = "blocked"
    PERMISSION_ERROR = "permission_error"

    # Unknown — default
    UNKNOWN = "unknown"


class FailureSeverity(str, Enum):
    TRANSIENT = "transient"    # Auto-retry
    PERSISTENT = "persistent"  # Needs Debug story
    FATAL = "fatal"            # Stop execution


@dataclass
class FailureClassification:
    failure_type: FailureType
    severity: FailureSeverity
    message: str
    should_retry: bool
    retry_delay_seconds: int = 5
    create_debug_story: bool = False


# Pattern matchers for transient failures
TRANSIENT_PATTERNS: list[tuple[re.Pattern, FailureType, int]] = [
    # (pattern, type, retry_delay_seconds)
    (re.compile(r'timeout|timed?\s*out|ETIMEDOUT', re.I), FailureType.TIMEOUT, 30),
    (re.compile(r'rate.?limit|429|too many requests|quota', re.I), FailureType.RATE_LIMIT, 60),
    (re.compile(r'ECONNREFUSED|ECONNRESET|ENETUNREACH|network|connection.*refused|socket', re.I), FailureType.NETWORK, 15),
    (re.compile(r'out of memory|OOM|Cannot allocate|MemoryError|ENOMEM', re.I), FailureType.OOM, 30),
    (re.compile(r'No space left|ENOSPC|disk full', re.I), FailureType.DISK_FULL, 60),
    (re.compile(r'\block\b|EBUSY|resource busy|already locked', re.I), FailureType.LOCK_CONTENTION, 10),
    (re.compile(r'API Error:\s*5\d{2}|500 Internal|502 Bad Gateway|503 Service', re.I), FailureType.API_ERROR, 30),
]

# Pattern matchers for persistent failures
PERSISTENT_PATTERNS: list[tuple[re.Pattern, FailureType]] = [
    (re.compile(r'ImportError|ModuleNotFoundError|No module named', re.I), FailureType.IMPORT_ERROR),
    (re.compile(r'SyntaxError|IndentationError|TabError', re.I), FailureType.SYNTAX_ERROR),
    (re.compile(r'PermissionError|EACCES|Permission denied', re.I), FailureType.PERMISSION_ERROR),
    (re.compile(r'FAILED|AssertionError|assert.*failed', re.I), FailureType.TEST_FAILURE),
    (re.compile(r'<promise>BLOCKED</promise>', re.I), FailureType.BLOCKED),
]


def classify_failure(
    exit_code: int,
    output: str,
    stderr: str = "",
    phase: str = "",
) -> FailureClassification:
    """Classify a failure based on exit code and output patterns.

    This is a pure Python function (complexity 1-2, no LLM).

    Args:
        exit_code: Process exit code
        output: stdout from the failed process
        stderr: stderr from the failed process
        phase: Phase name where failure occurred

    Returns:
        FailureClassification with type, severity, and retry guidance
    """
    combined = f"{output}\n{stderr}"

    # Check transient patterns first (auto-retry)
    for pattern, failure_type, delay in TRANSIENT_PATTERNS:
        if pattern.search(combined):
            return FailureClassification(
                failure_type=failure_type,
                severity=FailureSeverity.TRANSIENT,
                message=f"Transient failure: {failure_type.value}",
                should_retry=True,
                retry_delay_seconds=delay,
            )

    # Check persistent patterns (needs Debug story)
    for pattern, failure_type in PERSISTENT_PATTERNS:
        if pattern.search(combined):
            is_fatal = failure_type in (FailureType.BLOCKED, FailureType.PERMISSION_ERROR)
            return FailureClassification(
                failure_type=failure_type,
                severity=FailureSeverity.FATAL if is_fatal else FailureSeverity.PERSISTENT,
                message=f"Persistent failure: {failure_type.value}",
                should_retry=not is_fatal,
                create_debug_story=True,
            )

    # Exit code based classification
    if exit_code == -1:
        # Process didn't start or was killed
        return FailureClassification(
            failure_type=FailureType.UNKNOWN,
            severity=FailureSeverity.TRANSIENT,
            message="Process failed to execute or was killed",
            should_retry=True,
            retry_delay_seconds=10,
        )

    if exit_code == 137:
        # SIGKILL (OOM killer)
        return FailureClassification(
            failure_type=FailureType.OOM,
            severity=FailureSeverity.TRANSIENT,
            message="Process killed (likely OOM)",
            should_retry=True,
            retry_delay_seconds=30,
        )

    # Default: assume code bug (persistent)
    return FailureClassification(
        failure_type=FailureType.CODE_BUG,
        severity=FailureSeverity.PERSISTENT,
        message=f"Unknown failure (exit_code={exit_code})",
        should_retry=True,
        create_debug_story=True,
    )
