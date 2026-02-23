"""
Mediator Agent — Review changes after CODE/VERIFY phases.

Ported from Ralph Pro PowerShell (enhancements.ps1 lines 837-1300).
Smart trigger: file categorization (test vs code), phase-specific rules.
4 verdicts: ACCEPT, REVERT, PARTIAL, RETRY.
Intervention tracking in JSONL format.

Complexity: 6 (Mediator). Routes to mid-tier models.
"""

import json
import os
import re
import logging
from datetime import datetime
from typing import Type, Optional

from pydantic import BaseModel

from src.agents.base_agent import BaseAgent
from src.llm.response_parser import MediatorResponse, MediatorDecision

logger = logging.getLogger(__name__)

# Phases where mediator can fire
TRIGGER_PHASES = {"CODE", "VERIFY", "FIX"}

# File categorization patterns
TEST_FILE_PATTERNS = [
    re.compile(r'\.(test|spec)\.(js|ts|php|py)$'),
    re.compile(r'^tests[/\\]'),
    re.compile(r'^test[/\\]'),
]


def categorize_files(modified_files: list[str]) -> tuple[list[str], list[str]]:
    """Categorize modified files into test files and code files."""
    test_files = []
    code_files = []

    for f in modified_files:
        is_test = any(p.search(f) for p in TEST_FILE_PATTERNS)
        if is_test:
            test_files.append(f)
        else:
            code_files.append(f)

    return test_files, code_files


def should_trigger(phase: str, modified_files: list[str]) -> dict:
    """Determine if the Mediator should fire for this phase.

    Smart trigger rules:
    - TDD_RED: Should ONLY modify test files. Trigger if code files modified.
    - CODE: Should ONLY modify code files. Trigger if test files modified.
    - VERIFY: Always review if any files modified.
    """
    if phase not in TRIGGER_PHASES:
        return {"should_trigger": False, "reason": f"Phase {phase} not in trigger phases"}

    if not modified_files:
        return {"should_trigger": False, "reason": "No files modified"}

    test_files, code_files = categorize_files(modified_files)

    if phase == "TDD_RED":
        if code_files:
            return {
                "should_trigger": True,
                "reason": f"TDD_RED modified code files: {code_files}",
                "violation": "code_in_test_phase",
                "files": code_files,
            }
        return {"should_trigger": False, "reason": "TDD_RED only modified test files (expected)"}

    elif phase in ("CODE", "FIX"):
        if test_files:
            return {
                "should_trigger": True,
                "reason": f"CODE modified test files: {test_files}",
                "violation": "test_in_code_phase",
                "files": test_files,
            }
        return {"should_trigger": False, "reason": "CODE only modified code files (expected)"}

    elif phase == "VERIFY":
        return {
            "should_trigger": True,
            "reason": "VERIFY phase always reviewed",
            "violation": "verify_changes",
            "files": modified_files,
        }

    return {"should_trigger": False, "reason": f"Unknown phase: {phase}"}


class MediatorAgent(BaseAgent):

    @property
    def agent_name(self) -> str:
        return "mediator"

    @property
    def response_model(self) -> Type[BaseModel]:
        return MediatorResponse

    async def review(
        self,
        story: dict,
        phase: str,
        working_directory: str,
        changes_summary: str,
        changes_diff: str,
        test_results_before: Optional[dict] = None,
        test_results_after: Optional[dict] = None,
    ) -> MediatorResponse:
        """Review changes made by an agent and return a verdict.

        Args:
            story: The story being worked on
            phase: Phase that produced the changes (CODE, VERIFY, etc.)
            working_directory: Project directory
            changes_summary: git log -1 --stat output
            changes_diff: git diff output (truncated at 20KB)
            test_results_before: Test state before changes
            test_results_after: Test state after changes
        """
        before = test_results_before or {}
        after = test_results_after or {}

        context = {
            "changes_summary": changes_summary,
            "changes_diff": changes_diff[:20_000],  # Truncate large diffs
            "tests_before_passed": str(before.get("total", 0) - before.get("failures", 0)),
            "tests_before_failed": str(before.get("failures", 0)),
            "tests_before_exit": str(before.get("exit_code", 0)),
            "tests_after_passed": str(after.get("total", 0) - after.get("failures", 0)),
            "tests_after_failed": str(after.get("failures", 0)),
            "tests_after_exit": str(after.get("exit_code", 0)),
        }

        result = await self.execute(
            story=story,
            phase="MEDIATOR",
            working_directory=working_directory,
            context=context,
        )

        return result


def save_intervention(
    task_path: str,
    story_id: str,
    phase: str,
    violation: str,
    decision: str,
    files_involved: list[str],
):
    """Track a Mediator intervention in JSONL format."""
    tracker_file = os.path.join(task_path, "mediator-interventions.jsonl")

    entry = {
        "timestamp": datetime.now().isoformat(),
        "storyId": story_id,
        "phase": phase,
        "violation": violation,
        "decision": decision,
        "filesInvolved": files_involved,
    }

    try:
        with open(tracker_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception as e:
        logger.warning(f"Failed to save mediator intervention: {e}")


def get_intervention_stats(task_path: str) -> dict:
    """Aggregate Mediator intervention statistics."""
    tracker_file = os.path.join(task_path, "mediator-interventions.jsonl")

    if not os.path.exists(tracker_file):
        return {"total": 0, "by_phase": {}, "by_violation": {}, "by_decision": {}}

    by_phase = {}
    by_violation = {}
    by_decision = {}
    total = 0

    with open(tracker_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                total += 1
                p = entry.get("phase", "unknown")
                by_phase[p] = by_phase.get(p, 0) + 1
                v = entry.get("violation", "unknown")
                by_violation[v] = by_violation.get(v, 0) + 1
                d = entry.get("decision", "unknown")
                by_decision[d] = by_decision.get(d, 0) + 1
            except json.JSONDecodeError:
                pass

    return {
        "total": total,
        "by_phase": by_phase,
        "by_violation": by_violation,
        "by_decision": by_decision,
    }
