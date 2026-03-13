"""Tests for src.workflows.content_validators — semantic wrong-data detection."""

import os
import tempfile

from src.workflows.content_validators import ContentValidator

# ------------------------------------------------------------------
# Sample CLAUDE.md content for tests
# ------------------------------------------------------------------

SAMPLE_CLAUDE_MD = """\
# Project Config

## Contact Info
- phone: 801-555-9876
- address: 123 Innovation Way, Sandy, UT 84070
- email: info@logicalfront.com

## Statistics
- penetration rate: 63.4%
- penetration rate wrong labels: win rate, close rate
- active customers: 186
- annual revenue: $6.4M

## Blocked
- 555-000-1234
- 999 Fake Blvd, Nowhere, TX 00000
"""


def _write_claude_md(content: str = SAMPLE_CLAUDE_MD) -> str:
    """Write a temporary CLAUDE.md and return its path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return tmp.name


class TestContentValidatorParsing:
    """CLAUDE.md parsing extracts canonical data correctly."""

    def test_parses_phone(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            assert v.canonical_phone == "801-555-9876"
        finally:
            os.unlink(path)

    def test_parses_address(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            assert v.canonical_address == "123 Innovation Way, Sandy, UT 84070"
        finally:
            os.unlink(path)

    def test_parses_email(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            assert v.canonical_email == "info@logicalfront.com"
        finally:
            os.unlink(path)

    def test_parses_statistics(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            assert "penetration rate" in v.canonical_stats
            assert v.canonical_stats["penetration rate"] == "63.4%"
            assert v.canonical_stats["active customers"] == "186"
        finally:
            os.unlink(path)

    def test_parses_blocked_fragments(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            assert "555-000-1234" in v.blocked_fragments
            assert "999 Fake Blvd, Nowhere, TX 00000" in v.blocked_fragments
        finally:
            os.unlink(path)

    def test_is_loaded_true(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            assert v.is_loaded is True
        finally:
            os.unlink(path)


class TestContentValidatorCorrectData:
    """Content with correct contact info produces no issues."""

    def test_correct_phone_no_issues(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "Call us at 801-555-9876 for more information."
            issues = v.validate_contact_info(content)
            assert issues == []
        finally:
            os.unlink(path)

    def test_correct_address_no_issues(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "Visit us at 123 Innovation Way, Sandy, UT 84070."
            issues = v.validate_contact_info(content)
            assert issues == []
        finally:
            os.unlink(path)

    def test_no_contact_info_no_issues(self):
        """Content with no phone/address at all should produce no issues."""
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "This is a technical document about API design patterns."
            issues = v.validate_all(content)
            assert issues == []
        finally:
            os.unlink(path)


class TestContentValidatorWrongPhone:
    """Content with wrong phone number reports an issue."""

    def test_wrong_phone_detected(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "Call us at 801-999-0000 for sales inquiries."
            issues = v.validate_contact_info(content)
            assert len(issues) >= 1
            assert any("phone" in i.lower() and "801-999-0000" in i for i in issues)
        finally:
            os.unlink(path)

    def test_blocked_phone_detected(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "Old number was 555-000-1234, don't use it."
            issues = v.validate_contact_info(content)
            assert any("blocked" in i.lower() for i in issues)
        finally:
            os.unlink(path)


class TestContentValidatorWrongAddress:
    """Content with wrong address reports an issue."""

    def test_wrong_address_detected(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "Our office is at 456 Wrong Street, Sandy, UT 84070."
            issues = v.validate_contact_info(content)
            assert len(issues) >= 1
            assert any("address" in i.lower() for i in issues)
        finally:
            os.unlink(path)

    def test_blocked_address_fragment_detected(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "Ship to 999 Fake Blvd, Nowhere, TX 00000 immediately."
            issues = v.validate_contact_info(content)
            assert any("blocked" in i.lower() for i in issues)
        finally:
            os.unlink(path)


class TestContentValidatorStatistics:
    """Statistics misattribution is caught."""

    def test_penetration_rate_called_win_rate(self):
        """63.4% is the penetration rate, not the win rate."""
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "Our impressive 63.4% win rate demonstrates market leadership."
            issues = v.validate_statistics(content)
            assert len(issues) >= 1
            assert any("penetration rate" in i.lower() and "win rate" in i.lower() for i in issues)
        finally:
            os.unlink(path)

    def test_penetration_rate_called_close_rate(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "With a close rate of 63.4%, we lead the industry."
            issues = v.validate_statistics(content)
            assert len(issues) >= 1
            assert any("penetration rate" in i.lower() and "close rate" in i.lower() for i in issues)
        finally:
            os.unlink(path)

    def test_correct_stat_label_no_issues(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "Our 63.4% penetration rate shows deep market coverage."
            issues = v.validate_statistics(content)
            assert issues == []
        finally:
            os.unlink(path)

    def test_unrelated_number_no_issues(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "The project achieved 95% completion ahead of schedule."
            issues = v.validate_statistics(content)
            assert issues == []
        finally:
            os.unlink(path)


class TestContentValidatorGracefulDegradation:
    """No CLAUDE.md or invalid path produces no errors and no issues."""

    def test_none_path_skips(self):
        v = ContentValidator(None)
        assert v.is_loaded is False
        issues = v.validate_all("Any content at all with 555-000-1234.")
        assert issues == []

    def test_nonexistent_path_skips(self):
        v = ContentValidator("/nonexistent/path/CLAUDE.md")
        assert v.is_loaded is False
        issues = v.validate_all("Call us at 801-999-0000.")
        assert issues == []

    def test_empty_claude_md_no_crash(self):
        path = _write_claude_md("")
        try:
            v = ContentValidator(path)
            assert v.is_loaded is True
            issues = v.validate_all("Some content here.")
            assert issues == []
        finally:
            os.unlink(path)

    def test_claude_md_no_contact_section(self):
        path = _write_claude_md("# Project\n\nJust a project description.\n")
        try:
            v = ContentValidator(path)
            assert v.is_loaded is True
            assert v.canonical_phone is None
            assert v.canonical_address is None
            issues = v.validate_all("Call 555-123-4567 for info.")
            assert issues == []
        finally:
            os.unlink(path)


class TestValidateAll:
    """Integration: validate_all runs all checks together."""

    def test_multiple_issues_combined(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = "Call 801-999-0000 for our 63.4% win rate stats. Also check 555-000-1234."
            issues = v.validate_all(content)
            # Should have: wrong phone, blocked fragment, stat misattribution
            assert len(issues) >= 2
        finally:
            os.unlink(path)

    def test_clean_content_no_issues(self):
        path = _write_claude_md()
        try:
            v = ContentValidator(path)
            content = (
                "Logical Front provides enterprise infrastructure services. "
                "With 186 active customers and a 63.4% penetration rate, "
                "we deliver reliable solutions. "
                "Contact us at 801-555-9876 or visit "
                "123 Innovation Way, Sandy, UT 84070."
            )
            issues = v.validate_all(content)
            assert issues == []
        finally:
            os.unlink(path)
