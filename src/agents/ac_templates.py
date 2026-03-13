"""
AC Templates — Default acceptance criteria for each workflow type.

Provides get_default_acs() to retrieve defaults and merge_acs() to combine
story-specific ACs with defaults without duplication.
"""

# Default acceptance criteria per workflow type
_DEFAULT_ACS: dict[str, list[str]] = {
    "development": [
        "Code compiles/runs without errors",
        "All tests pass",
        "No security vulnerabilities introduced",
        "Code follows project conventions",
        "Changes are scoped to the task requirements",
    ],
    "content": [
        "Document is well-structured with clear headings",
        "Content addresses all requirements from the task description",
        "Writing is clear, professional, and free of errors",
        "Document meets specified length and format requirements",
        "No placeholder text or incomplete sections remain",
    ],
    "research": [
        "Research covers the requested topic comprehensively",
        "Sources and findings are clearly attributed",
        "Analysis is logical and well-supported",
        "Synthesis provides actionable insights or conclusions",
        "Output is well-organized and easy to navigate",
    ],
    "config": [
        "Configuration changes are applied correctly",
        "System functions as expected after changes",
        "No regressions in existing functionality",
        "Changes are documented and reversible",
        "Security best practices are followed",
    ],
    "maintenance": [
        "Maintenance task completed successfully",
        "System stability maintained or improved",
        "No regressions in existing functionality",
        "Changes are documented and reversible",
        "Monitoring confirms expected behavior",
    ],
    "review": [
        "Review covers all relevant aspects",
        "Findings are clearly documented",
        "Recommendations are actionable",
        "Assessment is objective and evidence-based",
    ],
    "debug": [
        "Root cause identified and documented",
        "Fix addresses the root cause, not just symptoms",
        "Original failure no longer reproduces",
        "No regressions introduced",
    ],
}


def get_default_acs(workflow_type: str) -> list[str]:
    """Get default acceptance criteria for a workflow type.

    Returns an empty list if the workflow type is not recognized.
    """
    return list(_DEFAULT_ACS.get(workflow_type, []))


def merge_acs(story_acs: list[str], default_acs: list[str]) -> list[str]:
    """Merge story-specific ACs with defaults, avoiding duplicates.

    Story ACs take priority and appear first. Default ACs are appended
    only if they don't substantially overlap with story ACs.
    """
    if not story_acs:
        return default_acs
    if not default_acs:
        return story_acs

    # Use story ACs as base
    merged = list(story_acs)

    # Add defaults that aren't already covered
    existing_lower = {ac.lower().strip() for ac in merged}
    for default_ac in default_acs:
        if default_ac.lower().strip() not in existing_lower:
            merged.append(default_ac)

    return merged
