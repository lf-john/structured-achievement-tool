"""
Semantic Content Validators — Catch wrong-data patterns in generated content.

Reads canonical data from a project's CLAUDE.md (contact info, statistics,
key facts) and validates content against it. Designed to prevent the kind of
bugs where wrong phone numbers, addresses, or misattributed statistics
propagate across many files.

Usage:
    validator = ContentValidator("/path/to/project/CLAUDE.md")
    issues = validator.validate_all(content_string)
    # issues is a list of human-readable warning strings (empty = clean)

If no CLAUDE.md is available or it contains no canonical data, all checks
are skipped gracefully (returns empty list).
"""

import logging
import os
import re

logger = logging.getLogger(__name__)


class ContentValidator:
    """Semantic validator that checks content against canonical project data."""

    def __init__(self, project_claude_md_path: str | None = None):
        """Load validation rules from the project's CLAUDE.md.

        Args:
            project_claude_md_path: Absolute path to the project CLAUDE.md.
                If None or file doesn't exist, semantic checks are skipped.
        """
        self.canonical_phone: str | None = None
        self.canonical_address: str | None = None
        self.canonical_email: str | None = None
        self.canonical_stats: dict[str, str] = {}  # label -> correct value
        self.blocked_fragments: list[str] = []
        self._loaded = False

        if project_claude_md_path and os.path.isfile(project_claude_md_path):
            try:
                self._parse_claude_md(project_claude_md_path)
                self._loaded = True
            except Exception as e:
                logger.warning(f"ContentValidator: failed to parse {project_claude_md_path}: {e}")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_claude_md(self, path: str) -> None:
        """Extract canonical data from CLAUDE.md.

        Looks for sections or key-value patterns:
        - Phone: patterns like `phone: 801-555-1234` or `Phone: (801) 555-1234`
        - Address: patterns like `address: 123 Main St, Sandy, UT 84070`
        - Email: patterns like `email: info@example.com`
        - Statistics: lines like `stat_name: value` inside a stats/facts section
        - Blocked fragments: lines under a `## Blocked` or `## Wrong Data` heading
        """
        with open(path, encoding="utf-8") as f:
            content = f.read()

        # Extract phone
        phone_match = re.search(
            r"(?:phone|tel(?:ephone)?)\s*[:=]\s*([^\n]+)",
            content,
            re.IGNORECASE,
        )
        if phone_match:
            self.canonical_phone = phone_match.group(1).strip().strip("`")

        # Extract address
        addr_match = re.search(
            r"(?:address|headquarters|hq)\s*[:=]\s*([^\n]+)",
            content,
            re.IGNORECASE,
        )
        if addr_match:
            self.canonical_address = addr_match.group(1).strip().strip("`")

        # Extract email
        email_match = re.search(
            r"(?:contact\s+email|email)\s*[:=]\s*([^\n]+)",
            content,
            re.IGNORECASE,
        )
        if email_match:
            self.canonical_email = email_match.group(1).strip().strip("`")

        # Extract statistics block
        # Look for a section like "## Statistics" or "## Key Facts" or "## Canonical Data"
        stats_section = re.search(
            r"(?:^##\s+(?:Statistics|Key Facts|Canonical Data|Facts)[^\n]*\n)(.*?)(?=^##\s|\Z)",
            content,
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        if stats_section:
            for line in stats_section.group(1).splitlines():
                # Match "- stat_name: value" or "stat_name: value"
                stat_match = re.match(r"[-*]?\s*([^:]+):\s+(.+)", line.strip())
                if stat_match:
                    label = stat_match.group(1).strip().lower()
                    value = stat_match.group(2).strip()
                    self.canonical_stats[label] = value

        # Extract blocked/wrong-data fragments
        blocked_section = re.search(
            r"(?:^##\s+(?:Blocked|Wrong Data|Known Wrong)[^\n]*\n)(.*?)(?=^##\s|\Z)",
            content,
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        if blocked_section:
            for line in blocked_section.group(1).splitlines():
                line = line.strip().lstrip("-*").strip().strip("`")
                if line:
                    self.blocked_fragments.append(line)

    # ------------------------------------------------------------------
    # Phone number helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Strip a phone string to digits only for comparison."""
        return re.sub(r"\D", "", phone)

    @staticmethod
    def _extract_phone_numbers(content: str) -> list[str]:
        """Find all phone-number-like strings in content."""
        # Match common US phone formats: (801) 555-1234, 801-555-1234,
        # 801.555.1234, 8015551234, +1-801-555-1234, 1-800-555-1234
        pattern = r"""
            (?<!\d)                          # not preceded by digit
            (?:\+?1[-.\s]?)?                 # optional country code
            (?:\(?\d{3}\)?[-.\s]?)           # area code
            \d{3}[-.\s]?\d{4}               # 7-digit number
            (?!\d)                           # not followed by digit
        """
        matches = re.findall(pattern, content, re.VERBOSE)
        return [m.strip() for m in matches if m.strip()]

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    def validate_contact_info(self, content: str) -> list[str]:
        """Check for wrong contact patterns and verify correct ones.

        Returns a list of issue descriptions (empty = no issues).
        """
        issues: list[str] = []

        # Check blocked fragments
        for fragment in self.blocked_fragments:
            if fragment.lower() in content.lower():
                issues.append(f"Semantic: blocked/known-wrong data fragment found: '{fragment}'")

        # Validate phone numbers against canonical
        if self.canonical_phone:
            canonical_digits = self._normalize_phone(self.canonical_phone)
            found_phones = self._extract_phone_numbers(content)
            for phone in found_phones:
                phone_digits = self._normalize_phone(phone)
                # Only flag if it looks like a real phone (7+ digits) and
                # doesn't match the canonical number
                if len(phone_digits) >= 7 and phone_digits != canonical_digits:
                    # Also check if canonical digits end with or contain
                    # the found digits (partial match is OK for local numbers)
                    if not canonical_digits.endswith(phone_digits) and not phone_digits.endswith(canonical_digits):
                        issues.append(
                            f"Semantic: phone number '{phone}' does not match canonical phone '{self.canonical_phone}'"
                        )

        # Validate address
        if self.canonical_address:
            # Look for address-like patterns in content that differ from canonical.
            # Require: street number, street name with at least one alpha word,
            # comma, city, state abbreviation, zip.  The negative lookbehind
            # prevents matching phone-number trailing digits as a street number.
            addr_pattern = r"(?<![0-9\-])(\d{1,6}\s+[A-Z][a-z][\w\s]{2,40},\s*[A-Za-z][\w\s]*,?\s*[A-Z]{2}\s+\d{5})"
            found_addresses = re.findall(addr_pattern, content)
            canonical_lower = self.canonical_address.lower()
            for addr in found_addresses:
                # Normalize for comparison: lowercase, collapse whitespace
                addr_normalized = " ".join(addr.lower().split())
                canonical_normalized = " ".join(canonical_lower.split())
                if addr_normalized != canonical_normalized:
                    issues.append(
                        f"Semantic: address '{addr}' does not match canonical address '{self.canonical_address}'"
                    )

        return issues

    def validate_statistics(self, content: str) -> list[str]:
        """Check that statistics in content match canonical values.

        Catches misattribution (e.g., calling a penetration rate a "win rate")
        and wrong values.

        Returns a list of issue descriptions (empty = no issues).
        """
        issues: list[str] = []

        # Check for known misattribution patterns.
        # These are wrong-label pairings loaded from CLAUDE.md stats section,
        # e.g. "penetration rate wrong labels: win rate, close rate"
        for label, canonical_value in self.canonical_stats.items():
            num_match = re.search(r"[\d,.]+%?", canonical_value)
            if not num_match:
                continue
            canonical_num = num_match.group(0)
            escaped_num = re.escape(canonical_num)

            # Check: is the canonical number mentioned near a wrong label?
            # "wrong_labels" entry format in stats: "penetration rate wrong labels: win rate, close rate"
            wrong_labels_key = f"{label} wrong labels"
            wrong_labels_str = self.canonical_stats.get(wrong_labels_key, "")
            if wrong_labels_str:
                wrong_labels = [wl.strip().lower() for wl in wrong_labels_str.split(",")]
                for wl in wrong_labels:
                    if not wl:
                        continue
                    # Check if content has the number near the wrong label
                    # Pattern: "63.4% win rate" or "win rate of 63.4%"
                    pattern_a = rf"{escaped_num}\s*%?\s*{re.escape(wl)}"
                    pattern_b = rf"{re.escape(wl)}\s*(?:of\s+)?{escaped_num}"
                    if re.search(pattern_a, content, re.IGNORECASE) or re.search(pattern_b, content, re.IGNORECASE):
                        issues.append(
                            f"Semantic: '{canonical_num}' is the {label}, not the '{wl}' — possible misattribution"
                        )

        return issues

    def validate_all(self, content: str) -> list[str]:
        """Run all semantic checks. Returns list of issues found.

        If no CLAUDE.md was loaded, returns empty list (graceful skip).
        """
        if not self._loaded:
            return []

        issues: list[str] = []
        issues.extend(self.validate_contact_info(content))
        issues.extend(self.validate_statistics(content))
        return issues
