"""
Root Cause Analysis Agent — Deep failure analysis after repeated failures.

Triggers after 3+ consecutive failures on the same story/phase. Analyzes
failure patterns, generates diagnostic reports, and creates escalation stories
for human intervention.

Complexity: 7-8 (deep reasoning). Routes to commercial models (Sonnet/Opus)
with DeepSeek R1 as backup.
"""

import logging
from dataclasses import dataclass, field

from src.agents.failure_classifier import (
    FailureSeverity,
    classify_failure,
)
from src.execution.audit_journal import AuditJournal, AuditRecord

logger = logging.getLogger(__name__)


@dataclass
class RCAReport:
    """Root cause analysis report."""

    story_id: str
    task_file: str
    failure_count: int
    root_cause_category: str  # code_bug, env_issue, dependency, design_flaw, resource, unknown
    root_cause_summary: str
    failure_timeline: list[dict] = field(default_factory=list)
    common_patterns: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    escalation_required: bool = False
    suggested_story_type: str = "escalation"  # escalation or debug


# Failure pattern categories with associated keywords
PATTERN_CATEGORIES = {
    "dependency": {
        "keywords": ["import", "module", "package", "dependency", "require", "install"],
        "recommendations": [
            "Verify all dependencies are installed: pip install -r requirements.txt",
            "Check for version conflicts in requirements",
            "Ensure virtual environment is activated",
        ],
    },
    "environment": {
        "keywords": ["permission", "path", "env", "config", "timeout", "connection", "disk"],
        "recommendations": [
            "Check environment variables and configuration files",
            "Verify file/directory permissions",
            "Check network connectivity and service availability",
        ],
    },
    "code_bug": {
        "keywords": ["assertion", "typeerror", "attributeerror", "nameerror", "valueerror", "index"],
        "recommendations": [
            "Review the failing test output for the exact assertion",
            "Check type annotations and function signatures",
            "Verify data structures match expected shapes",
        ],
    },
    "design_flaw": {
        "keywords": ["architecture", "circular", "recursive", "infinite", "deadlock", "race"],
        "recommendations": [
            "Review the architectural approach — may need redesign",
            "Check for circular dependencies in imports or data flow",
            "Consider breaking the component into smaller pieces",
        ],
    },
    "resource": {
        "keywords": ["memory", "oom", "disk", "space", "quota", "limit", "rate"],
        "recommendations": [
            "Check system resource usage (memory, disk, CPU)",
            "Review rate limiting and quota configuration",
            "Consider reducing batch sizes or adding pagination",
        ],
    },
}


def analyze_failure_patterns(
    audit_records: list[AuditRecord],
    story_id: str,
) -> RCAReport:
    """Analyze failure patterns from audit records for a specific story.

    Pure Python analysis (no LLM needed for pattern matching).
    Creates an RCA report with categorized root cause and recommendations.

    Args:
        audit_records: List of audit records for the failing story.
        story_id: The story ID being analyzed.

    Returns:
        RCAReport with analysis results.
    """
    # Filter to failures for this story
    failures = [r for r in audit_records if not r.success and r.story_id == story_id]

    if not failures:
        return RCAReport(
            story_id=story_id,
            task_file=audit_records[0].task_file if audit_records else "",
            failure_count=0,
            root_cause_category="unknown",
            root_cause_summary="No failures found for analysis",
        )

    # Build failure timeline
    timeline = []
    error_texts = []
    for record in failures:
        timeline.append(
            {
                "timestamp": record.timestamp,
                "exit_code": record.exit_code,
                "error_summary": record.error_summary or "",
            }
        )
        if record.error_summary:
            error_texts.append(record.error_summary.lower())

    combined_errors = " ".join(error_texts)

    # Categorize by keyword matching
    category_scores = {}
    for category, info in PATTERN_CATEGORIES.items():
        score = sum(1 for kw in info["keywords"] if kw in combined_errors)
        if score > 0:
            category_scores[category] = score

    # Select highest-scoring category
    if category_scores:
        root_cause_category = max(category_scores, key=category_scores.get)
    else:
        root_cause_category = "unknown"

    # Classify individual failures for pattern detection
    classifications = []
    for record in failures:
        cls = classify_failure(
            exit_code=record.exit_code,
            output=record.error_summary or "",
        )
        classifications.append(cls)

    # Detect common patterns
    common_patterns = []
    failure_types = [c.failure_type.value for c in classifications]
    type_counts = {}
    for ft in failure_types:
        type_counts[ft] = type_counts.get(ft, 0) + 1

    for ft, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = count / len(failure_types) * 100
        common_patterns.append(f"{ft}: {count}/{len(failures)} failures ({pct:.0f}%)")

    # Check if all failures are the same type (strong signal)
    all_same = len(set(failure_types)) == 1
    if all_same and failure_types:
        common_patterns.insert(0, f"All {len(failures)} failures are the same type: {failure_types[0]}")

    # Build recommendations
    recommendations = []
    if root_cause_category in PATTERN_CATEGORIES:
        recommendations.extend(PATTERN_CATEGORIES[root_cause_category]["recommendations"])
    else:
        recommendations.append("Manual investigation recommended — automated analysis inconclusive")
        recommendations.append("Review the full error output in the audit journal")

    # Check if all are transient (might resolve with time)
    all_transient = all(c.severity == FailureSeverity.TRANSIENT for c in classifications)
    if all_transient:
        recommendations.insert(0, "All failures appear transient — may resolve with retry after cooldown")

    # Build summary
    error_samples = list(set(error_texts[:3]))
    summary_parts = [f"{len(failures)} consecutive failures on {story_id}"]
    summary_parts.append(f"Category: {root_cause_category}")
    if error_samples:
        summary_parts.append(f"Sample errors: {'; '.join(e[:100] for e in error_samples)}")

    # Determine if escalation is needed
    escalation_required = (
        len(failures) >= 3
        and not all_transient
        and root_cause_category not in ("dependency",)  # dependency issues are usually self-fixable
    )

    return RCAReport(
        story_id=story_id,
        task_file=failures[0].task_file,
        failure_count=len(failures),
        root_cause_category=root_cause_category,
        root_cause_summary=". ".join(summary_parts),
        failure_timeline=timeline,
        common_patterns=common_patterns,
        recommendations=recommendations,
        escalation_required=escalation_required,
        suggested_story_type="escalation" if escalation_required else "debug",
    )


def should_trigger_rca(
    audit_journal: AuditJournal,
    story_id: str,
    threshold: int = 3,
) -> bool:
    """Check if RCA should be triggered for a story.

    Returns True if the story has >= threshold consecutive failures
    in the audit journal.
    """
    records = audit_journal.query()

    # Filter to this story, in reverse chronological order
    story_records = [r for r in records if r.story_id == story_id]
    story_records.reverse()  # Most recent first

    # Count consecutive failures from the most recent
    consecutive_failures = 0
    for record in story_records:
        if not record.success:
            consecutive_failures += 1
        else:
            break  # Hit a success, stop counting

    return consecutive_failures >= threshold


def generate_escalation_story(report: RCAReport, task_name: str) -> dict:
    """Generate an escalation story dict from an RCA report.

    Returns a story dict suitable for writing to a story file
    or passing to the story executor.
    """
    return {
        "id": f"{report.story_id}-rca",
        "title": f"RCA Escalation: {report.root_cause_category} in {report.story_id}",
        "description": (
            f"Root cause analysis identified {report.failure_count} consecutive failures.\n\n"
            f"**Category:** {report.root_cause_category}\n"
            f"**Summary:** {report.root_cause_summary}\n\n"
            f"**Patterns:**\n" + "\n".join(f"- {p}" for p in report.common_patterns) + "\n\n"
            "**Recommendations:**\n" + "\n".join(f"- {r}" for r in report.recommendations)
        ),
        "type": report.suggested_story_type,
        "status": "pending",
        "dependsOn": [],
        "complexity": 8,
        "acceptanceCriteria": [
            f"Root cause of {report.story_id} failures identified",
            "Fix applied or workaround documented",
            f"{report.story_id} passes on retry after fix",
        ],
    }
