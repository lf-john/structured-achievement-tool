import os
import re
import subprocess
import logging
import time
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MAX_CONTINUATIONS = 3

# Patterns that indicate max turns was hit
MAX_TURNS_PATTERNS = [
    r"(?i)maximum.*turns?.*reached",
    r"(?i)max.*turns?.*limit",
    r"(?i)conversation.*turn.*limit",
    r"(?i)reached.*maximum.*messages",
]

# Pattern to extract session ID
SESSION_ID_PATTERN = r"session[_\s]?id[:\s]+([a-zA-Z0-9_-]+)"


@dataclass
class ContinuationResult:
    success: bool
    session_id: Optional[str] = None
    continuation_count: int = 0
    output: str = ""
    error: str = ""


class SessionContinuator:
    def __init__(self, max_continuations: int = MAX_CONTINUATIONS):
        self.max_continuations = max_continuations
        self._patterns = [re.compile(p) for p in MAX_TURNS_PATTERNS]
        self._session_pattern = re.compile(SESSION_ID_PATTERN, re.IGNORECASE)
        self._continuation_counts: dict[str, int] = {}  # task_id -> count

    def detect_max_turns(self, output: str, exit_code: int = 0) -> bool:
        """Check if the output indicates max turns was hit."""
        return any(p.search(output) for p in self._patterns)

    def extract_session_id(self, output: str) -> Optional[str]:
        """Extract session ID from Claude CLI output."""
        match = self._session_pattern.search(output)
        return match.group(1) if match else None

    def can_continue(self, task_id: str) -> bool:
        """Check if more continuations are allowed."""
        return self._continuation_counts.get(task_id, 0) < self.max_continuations

    def continue_session(self, session_id: str, task_id: str, working_dir: str) -> ContinuationResult:
        """Resume a Claude session. Returns ContinuationResult."""
        count = self._continuation_counts.get(task_id, 0) + 1
        self._continuation_counts[task_id] = count

        logger.info(f"Continuing session {session_id} for {task_id} (attempt {count}/{self.max_continuations})")

        try:
            result = subprocess.run(
                ["claude", "--resume", session_id],
                capture_output=True, text=True,
                cwd=working_dir,
                timeout=600,  # 10 minute timeout
            )
            return ContinuationResult(
                success=result.returncode == 0,
                session_id=session_id,
                continuation_count=count,
                output=result.stdout,
                error=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return ContinuationResult(
                success=False, session_id=session_id,
                continuation_count=count, error="Continuation timed out",
            )
        except Exception as e:
            return ContinuationResult(
                success=False, session_id=session_id,
                continuation_count=count, error=str(e),
            )

    def reset_count(self, task_id: str):
        """Reset continuation count for a task."""
        self._continuation_counts.pop(task_id, None)

    def get_count(self, task_id: str) -> int:
        """Get current continuation count."""
        return self._continuation_counts.get(task_id, 0)
