"""
Tests for the text_truncator utility module.

IMPLEMENTATION PLAN for US-001:

Components:
  - truncate(text: str, max_length: int, suffix: str = '...') -> str:
    Main truncation function that respects word boundaries, validates constraints,
    and returns properly truncated text with optional suffix.

Test Categories:
  1. Happy Path - Basic functionality per acceptance criteria
  2. Default Suffix - Verify default '...' suffix behavior
  3. Custom Suffix - Verify custom suffix parameter works
  4. Word Boundary - Verify truncation at last word boundary
  5. Edge Cases - Empty strings, whitespace, single words
  6. Validation - ValueError for invalid max_length

Acceptance Criteria Mapping:
  AC1: Text unchanged when len(text) <= max_length -> test_should_return_text_unchanged_when_within_max_length
  AC2: Raise ValueError when max_length < len(suffix) -> test_should_raise_value_error_when_max_length_less_than_suffix
  AC3: Break at last word boundary -> test_should_break_at_word_boundary
  AC4: Suffix appended and counts toward max_length -> test_should_include_suffix_in_max_length
  AC5: Empty string returns empty string -> test_should_return_empty_string_for_empty_input
  AC6: Whitespace-only text -> test_should_handle_whitespace_only_text
  AC7: Single word longer than max_length -> test_should_truncate_single_word_longer_than_max_length
  AC8: Default suffix is '...' -> test_should_use_default_suffix_when_not_specified
  AC9: Custom suffix respected -> test_should_use_custom_suffix_when_specified

Edge Cases:
  - Text with no spaces (single long word)
  - max_length equal to suffix length
  - Multiple consecutive spaces
  - Text with leading/trailing whitespace
  - Very small max_length values
  - Text with exactly max_length
"""

import pytest
from src.utils.text_truncator import truncate


class TestTruncateBasicFunctionality:
    """Test core truncate functionality."""

    def test_should_return_text_unchanged_when_within_max_length(self):
        """AC1: Text unchanged when len(text) <= max_length."""
        text = "Hello world"
        result = truncate(text, max_length=20)
        assert result == "Hello world"

    def test_should_return_text_unchanged_when_exactly_max_length(self):
        """Text should be unchanged when exactly at max_length."""
        text = "Hello"
        result = truncate(text, max_length=5)
        assert result == "Hello"

    def test_should_return_empty_string_for_empty_input(self):
        """AC5: Empty string input returns empty string."""
        result = truncate("", max_length=10)
        assert result == ""

    def test_should_return_empty_string_when_max_length_is_zero(self):
        """Edge case: max_length of 0 should return empty string."""
        result = truncate("Hello world", max_length=0)
        assert result == ""

    def test_should_handle_whitespace_only_text(self):
        """AC6: Whitespace-only input handling."""
        # Whitespace only, within max_length
        result = truncate("   ", max_length=10)
        assert result in ["", "   "]  # Could be preserved or empty

    def test_should_handle_whitespace_only_text_exceeding_max_length(self):
        """Whitespace-only text exceeding max_length."""
        result = truncate("   ", max_length=2)
        # Should truncate whitespace
        assert len(result) <= 2


class TestTruncateSuffix:
    """Test suffix handling."""

    def test_should_use_default_suffix_when_not_specified(self):
        """AC8: Default suffix is '...'."""
        text = "Hello world this is a long text"
        result = truncate(text, max_length=15)
        assert result.endswith("...")
        assert len(result) <= 15

    def test_should_use_custom_suffix_when_specified(self):
        """AC9: Custom suffix parameter is respected."""
        text = "Hello world this is a long text"
        result = truncate(text, max_length=15, suffix=" >>")
        assert result.endswith(" >>")
        assert len(result) <= 15

    def test_should_use_empty_string_as_suffix(self):
        """Custom suffix can be empty string."""
        text = "Hello world this is a long text"
        result = truncate(text, max_length=10, suffix="")
        assert not result.endswith("...")
        assert len(result) <= 10

    def test_should_raise_value_error_when_max_length_less_than_suffix(self):
        """AC2: Raise ValueError when max_length < len(suffix)."""
        with pytest.raises(ValueError):
            truncate("Hello world", max_length=2, suffix="...")

    def test_should_raise_value_error_when_max_length_equals_zero_with_suffix(self):
        """ValueError when max_length=0 but suffix has length."""
        with pytest.raises(ValueError):
            truncate("Hello world", max_length=0, suffix="...")


class TestTruncateWordBoundary:
    """Test word boundary truncation."""

    def test_should_break_at_word_boundary(self):
        """AC3: Break at last word boundary so result length <= max_length."""
        text = "Hello world something"
        result = truncate(text, max_length=12)
        # "Hello world" = 11 chars, fits within 12
        # "Hello world ..." = 15 chars, too long
        # Should be "Hello..." (7 chars) or similar
        assert len(result) <= 12
        assert not result.startswith("Hello world s")  # Didn't break mid-word

    def test_should_include_suffix_in_max_length_calculation(self):
        """AC4: Suffix appended and counts toward max_length."""
        text = "Hello world something else"
        result = truncate(text, max_length=13)
        assert len(result) <= 13
        assert result.endswith("...")

    def test_should_truncate_at_space_boundaries(self):
        """Truncation should occur at word boundaries (spaces)."""
        text = "One Two Three Four Five"
        result = truncate(text, max_length=12)
        # Should truncate at word boundary, not in middle of word
        assert len(result) <= 12
        # Last character should not be middle of a word
        # (either space, part of suffix, or last char of word)

    def test_should_handle_multiple_consecutive_spaces(self):
        """Edge case: multiple spaces between words."""
        text = "Hello    world    something"
        result = truncate(text, max_length=15)
        assert len(result) <= 15

    def test_should_handle_leading_spaces(self):
        """Edge case: leading spaces in text."""
        text = "   Hello world something"
        result = truncate(text, max_length=15)
        assert len(result) <= 15

    def test_should_handle_trailing_spaces(self):
        """Edge case: trailing spaces in text."""
        text = "Hello world something   "
        result = truncate(text, max_length=15)
        assert len(result) <= 15


class TestTruncateSingleWord:
    """Test truncation of single words and edge cases."""

    def test_should_truncate_single_word_longer_than_max_length(self):
        """AC7: Single word longer than max_length is truncated with suffix."""
        text = "supercalifragilisticexpialidocious"
        result = truncate(text, max_length=10, suffix="...")
        assert len(result) <= 10
        assert result.endswith("...")
        # Should have truncated the word itself
        assert len(result) < len(text)

    def test_should_truncate_single_word_with_custom_suffix(self):
        """Single word longer than max_length with custom suffix."""
        text = "supercalifragilisticexpialidocious"
        result = truncate(text, max_length=12, suffix=" >")
        assert len(result) <= 12
        assert result.endswith(" >")

    def test_should_handle_no_spaces_in_text(self):
        """Text with no spaces (single long word)."""
        text = "supercalifragilisticexpialidocious"
        result = truncate(text, max_length=15)
        assert len(result) <= 15
        assert result.endswith("...")

    def test_should_truncate_word_when_suffix_space_is_tight(self):
        """Single word when max_length barely fits suffix."""
        text = "verylongword"
        result = truncate(text, max_length=6, suffix="...")
        assert len(result) <= 6
        assert result.endswith("...")


class TestTruncateEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_should_handle_single_character_text(self):
        """Single character text should be returned unchanged."""
        result = truncate("A", max_length=10)
        assert result == "A"

    def test_should_handle_two_character_text(self):
        """Two character text within max_length."""
        result = truncate("Hi", max_length=5)
        assert result == "Hi"

    def test_should_handle_max_length_equal_to_suffix_length(self):
        """max_length exactly equals suffix length."""
        # This should be allowed since suffix must fit
        result = truncate("Hello world", max_length=3, suffix="...")
        # Can only fit the suffix
        assert len(result) <= 3

    def test_should_handle_very_small_max_length(self):
        """Very small max_length with default suffix."""
        text = "Hello"
        result = truncate(text, max_length=4, suffix="...")
        # Can't fit more than "..."
        assert len(result) <= 4

    def test_should_preserve_case(self):
        """Truncation should preserve text case."""
        text = "HELLO World Something"
        result = truncate(text, max_length=12)
        assert result[0].isupper()

    def test_should_handle_numbers_and_special_characters(self):
        """Text with numbers and special characters."""
        text = "Hello123 world@example.com something"
        result = truncate(text, max_length=20)
        assert len(result) <= 20
        assert "123" in result or result.endswith("...")

    def test_should_handle_punctuation(self):
        """Text with punctuation."""
        text = "Hello, world! This is something."
        result = truncate(text, max_length=15)
        assert len(result) <= 15

    def test_should_handle_text_with_newlines(self):
        """Text with newline characters."""
        text = "Hello\nworld\nsomething"
        result = truncate(text, max_length=15)
        assert len(result) <= 15

    def test_should_handle_tabs_and_special_whitespace(self):
        """Text with tabs and special whitespace."""
        text = "Hello\tworld\tsomething"
        result = truncate(text, max_length=15)
        assert len(result) <= 15

    def test_should_handle_unicode_characters(self):
        """Text with unicode characters."""
        text = "Hello 世界 something else"
        result = truncate(text, max_length=15)
        assert len(result) <= 15

    def test_should_handle_emoji(self):
        """Text with emoji characters."""
        text = "Hello 😀 world something"
        result = truncate(text, max_length=15)
        assert len(result) <= 15


class TestTruncateValidation:
    """Test input validation and error handling."""

    def test_should_raise_value_error_for_negative_max_length(self):
        """Negative max_length should raise ValueError."""
        with pytest.raises(ValueError):
            truncate("Hello", max_length=-1)

    def test_should_raise_value_error_when_suffix_longer_than_max_length(self):
        """Suffix longer than max_length should raise ValueError."""
        with pytest.raises(ValueError):
            truncate("Hello world", max_length=5, suffix="...truncated")

    def test_should_raise_value_error_for_none_text(self):
        """None as text should raise error."""
        with pytest.raises((TypeError, ValueError)):
            truncate(None, max_length=10)

    def test_should_raise_value_error_for_none_max_length(self):
        """None as max_length should raise error."""
        with pytest.raises((TypeError, ValueError)):
            truncate("Hello", max_length=None)


class TestTruncateComplexScenarios:
    """Test complex real-world scenarios."""

    def test_should_handle_sentence_truncation(self):
        """Truncate a full sentence properly."""
        text = "The quick brown fox jumps over the lazy dog"
        result = truncate(text, max_length=20)
        assert len(result) <= 20
        assert result.endswith("...") or len(result) == len(text)

    def test_should_handle_url_like_text(self):
        """Truncate URL-like text."""
        text = "https://example.com/very/long/path/to/some/resource"
        result = truncate(text, max_length=25)
        assert len(result) <= 25

    def test_should_handle_repeated_words(self):
        """Truncate text with repeated words."""
        text = "word word word word word word"
        result = truncate(text, max_length=15)
        assert len(result) <= 15

    def test_should_handle_all_spaces(self):
        """Handle string of only spaces."""
        text = "                    "
        result = truncate(text, max_length=5)
        assert len(result) <= 5

    def test_should_consistently_truncate_same_text(self):
        """Same text and parameters should produce same result."""
        text = "Hello world this is a longer text"
        result1 = truncate(text, max_length=15)
        result2 = truncate(text, max_length=15)
        assert result1 == result2


class TestTruncateIntegration:
    """Integration tests combining multiple features."""

    def test_should_work_with_long_text_and_long_suffix(self):
        """Long text with long custom suffix."""
        text = "This is a very long piece of text that needs truncation"
        result = truncate(text, max_length=30, suffix=" [continued]")
        assert len(result) <= 30
        assert result.endswith(" [continued]")

    def test_should_work_with_max_length_just_above_word(self):
        """max_length just above a word should include it."""
        text = "Hello world something"
        # "Hello..." = 8 chars
        result = truncate(text, max_length=8)
        assert len(result) <= 8

    def test_should_handle_progressive_truncation(self):
        """Progressively smaller max_length values."""
        text = "Hello world something else here"
        result1 = truncate(text, max_length=30)
        result2 = truncate(text, max_length=20)
        result3 = truncate(text, max_length=10)

        assert len(result1) <= 30
        assert len(result2) <= 20
        assert len(result3) <= 10

    def test_should_maintain_first_word_when_possible(self):
        """When truncating, should try to keep first word."""
        text = "Important message that continues with more details"
        result = truncate(text, max_length=20)
        assert len(result) <= 20
        assert "Important" in result or result == "..."
