"""
Content Workflow Models — Document types, Group 1 rules, and Group 2 qualities.

Defines the verification framework for content stories:
- Group 1: Mechanical rules (automated Python test checks)
- Group 2: Agentic qualities (LLM-evaluated)
- Document type taxonomy with per-type defaults
"""

from dataclasses import dataclass, field
from enum import Enum


class DocType(str, Enum):
    """Document type taxonomy."""
    TECHNICAL = "technical"       # API docs, architecture docs, READMEs
    MARKETING = "marketing"       # Email sequences, landing pages, battlecards
    REFERENCE = "reference"       # Guides, how-tos, runbooks, checklists
    SEO = "seo"                   # Blog posts, web content optimized for search
    POLICY = "policy"             # SOPs, compliance docs, governance
    LEGAL = "legal"               # Contracts, terms of service, compliance, legal notices
    INSTRUCTIONAL = "instructional"  # Tutorials, training materials, onboarding


@dataclass
class Group1Rule:
    """A mechanical verification rule (Group 1).

    These produce deterministic pass/fail via Python test code.
    Value of None means the rule is not applicable for this document.
    """
    name: str
    description: str
    value: str | None = None      # Target value (e.g., "500-1000", ">=3", "markdown")
    enabled: bool = True             # False means skip this rule entirely


@dataclass
class Group2Quality:
    """An agentic verification quality (Group 2).

    These are evaluated by LLM review — pass/fail with reasoning.
    """
    name: str
    description: str
    guidance: str = ""               # Specific guidance for the reviewer
    enabled: bool = True             # False means skip (optional for this doc type)


@dataclass
class ContentPlan:
    """Plan produced by the PLAN phase for content stories.

    Contains both the document outline and the verification criteria
    that the TEST and VERIFY phases will use.
    """
    doc_type: str = "technical"
    output_path: str = ""
    output_format: str = "markdown"
    outline: str = ""                      # Document structure/outline
    group1_rules: list = field(default_factory=list)   # List of Group1Rule dicts
    group2_qualities: list = field(default_factory=list)  # List of Group2Quality dicts


# ============================================================
# Default Group 1 Rules
# ============================================================

DEFAULT_GROUP1_RULES = [
    Group1Rule("word_count",       "Total word count range",          "500-2000"),
    Group1Rule("heading_count",    "Number of top-level headings",    ">=2"),
    Group1Rule("sub_heading_count","Number of sub-headings",          ">=3"),
    Group1Rule("outline_format",   "Document follows planned outline", "true"),
    Group1Rule("bullet_points",    "Uses bullet points for lists",    "optional"),
    Group1Rule("emojis",           "Emoji usage policy",              "none"),
    Group1Rule("file_format",      "Output file format",              "markdown"),
    Group1Rule("file_path",        "Output file exists at path",      "required"),
    Group1Rule("sections",         "Required section names",          None),   # Set by plan
    Group1Rule("code_blocks",      "Contains code blocks",            "optional"),
    Group1Rule("links",            "Contains hyperlinks",             "optional"),
    Group1Rule("tables",           "Contains tables",                 "optional"),
    Group1Rule("images",           "References images",               "none"),
    Group1Rule("placeholders",     "No unreplaced placeholders",      "none"),
    Group1Rule("merge_tokens",     "No merge conflict markers",       "none"),
]


# ============================================================
# Default Group 2 Qualities
# ============================================================

DEFAULT_GROUP2_QUALITIES = [
    Group2Quality("tone",            "Writing tone matches target audience",
                  "Professional, clear, appropriate for the audience"),
    Group2Quality("theme",           "Content stays on theme throughout",
                  "No tangential sections, consistent focus"),
    Group2Quality("purpose",         "Document achieves its stated purpose",
                  "Reader can accomplish the goal after reading"),
    Group2Quality("goal",            "Acceptance criteria are addressed",
                  "Each criterion is directly covered in the content"),
    Group2Quality("audience",        "Content is appropriate for target audience",
                  "Vocabulary and depth match audience expertise level"),
    Group2Quality("brand_voice",     "Consistent with brand/org voice",
                  "Matches established tone and terminology", enabled=False),  # Optional
    Group2Quality("data_accuracy",   "Facts and data are accurate",
                  "No fabricated statistics, all claims verifiable"),
    Group2Quality("persuasiveness",  "Content is persuasive where needed",
                  "CTAs are clear, value propositions are compelling", enabled=False),  # Optional
    Group2Quality("completeness",    "Content is complete, no gaps",
                  "All sections from outline are present and substantive"),
    Group2Quality("readability",     "Content is readable and well-structured",
                  "Good flow, clear paragraphs, scannable format"),
]


# ============================================================
# Per-Document-Type Overrides
# ============================================================

# Which Group 1 rules change per doc type
# Keys are rule names, values override the default
DOC_TYPE_GROUP1_OVERRIDES: dict[str, dict[str, dict]] = {
    "technical": {
        "code_blocks": {"value": ">=1"},
        "emojis": {"value": "none"},
        "word_count": {"value": "300-5000"},
    },
    "marketing": {
        "emojis": {"value": "optional"},
        "bullet_points": {"value": ">=3"},
        "word_count": {"value": "200-8000"},
    },
    "reference": {
        "heading_count": {"value": ">=3"},
        "code_blocks": {"value": "optional"},
        "word_count": {"value": "500-3000"},
    },
    "seo": {
        "heading_count": {"value": ">=3"},
        "word_count": {"value": "800-2500"},
        "links": {"value": ">=2"},
    },
    "policy": {
        "emojis": {"value": "none"},
        "code_blocks": {"value": "none"},
        "word_count": {"value": "500-5000"},
    },
    "legal": {
        "emojis": {"value": "none"},
        "code_blocks": {"value": "none"},
        "bullet_points": {"value": "optional"},
        "word_count": {"value": "500-10000"},
        "heading_count": {"value": ">=3"},
    },
    "instructional": {
        "code_blocks": {"value": "optional"},
        "heading_count": {"value": ">=4"},
        "word_count": {"value": "500-3000"},
    },
}

# Which Group 2 qualities are enabled per doc type
DOC_TYPE_GROUP2_OVERRIDES: dict[str, dict[str, dict]] = {
    "technical": {
        "brand_voice": {"enabled": False},
        "persuasiveness": {"enabled": False},
    },
    "marketing": {
        "brand_voice": {"enabled": True},
        "persuasiveness": {"enabled": True},
    },
    "reference": {
        "brand_voice": {"enabled": False},
        "persuasiveness": {"enabled": False},
    },
    "seo": {
        "brand_voice": {"enabled": True},
        "persuasiveness": {"enabled": True},
    },
    "policy": {
        "brand_voice": {"enabled": False},
        "persuasiveness": {"enabled": False},
        "data_accuracy": {"guidance": "All policy references must cite source documents"},
    },
    "legal": {
        "brand_voice": {"enabled": False},
        "persuasiveness": {"enabled": False},
        "data_accuracy": {"guidance": "All legal references must cite source statutes, regulations, or contracts"},
    },
    "instructional": {
        "brand_voice": {"enabled": False},
        "persuasiveness": {"enabled": False},
    },
}


def get_rules_for_doc_type(doc_type: str) -> list[Group1Rule]:
    """Get Group 1 rules with doc-type overrides applied."""
    rules = []
    overrides = DOC_TYPE_GROUP1_OVERRIDES.get(doc_type, {})

    for default_rule in DEFAULT_GROUP1_RULES:
        rule = Group1Rule(
            name=default_rule.name,
            description=default_rule.description,
            value=default_rule.value,
            enabled=default_rule.enabled,
        )
        if rule.name in overrides:
            for key, val in overrides[rule.name].items():
                setattr(rule, key, val)
        rules.append(rule)

    return rules


def get_qualities_for_doc_type(doc_type: str) -> list[Group2Quality]:
    """Get Group 2 qualities with doc-type overrides applied."""
    qualities = []
    overrides = DOC_TYPE_GROUP2_OVERRIDES.get(doc_type, {})

    for default_q in DEFAULT_GROUP2_QUALITIES:
        quality = Group2Quality(
            name=default_q.name,
            description=default_q.description,
            guidance=default_q.guidance,
            enabled=default_q.enabled,
        )
        if quality.name in overrides:
            for key, val in overrides[quality.name].items():
                setattr(quality, key, val)
        qualities.append(quality)

    return qualities


def format_group1_for_prompt(rules: list[Group1Rule]) -> str:
    """Format Group 1 rules for inclusion in LLM prompts."""
    lines = []
    for rule in rules:
        if not rule.enabled:
            continue
        value_str = rule.value if rule.value else "not specified"
        lines.append(f"- **{rule.name}**: {rule.description} → `{value_str}`")
    return "\n".join(lines) if lines else "No mechanical rules specified."


def format_group2_for_prompt(qualities: list[Group2Quality]) -> str:
    """Format Group 2 qualities for inclusion in LLM prompts."""
    lines = []
    for q in qualities:
        if not q.enabled:
            continue
        guidance_str = f" ({q.guidance})" if q.guidance else ""
        lines.append(f"- **{q.name}**: {q.description}{guidance_str}")
    return "\n".join(lines) if lines else "No quality criteria specified."
