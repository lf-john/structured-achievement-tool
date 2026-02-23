"""
Tests for src.utils.text_truncator — Truncate text with word boundary awareness.

IMPLEMENTATION PLAN for US-001:

Components:
  - text_truncator.truncate(text, max_length, suffix='...'): Main function
    - Validates max_length >= len(suffix), raises ValueError if not
    - Returns text unchanged if len(text) <= max_length
    - Finds last word boundary before (max_length - len(suffix))
    - If no word boundary found, truncates at hard position
    - Appends suffix and returns result

Test Categories:
  1. Happy Path: Text unchanged, word boundary, custom suffix
  2. Validation: ValueError when max_length < len(suffix)
  3. Edge Cases: Empty string, single long word, whitespace-only, exact length

Acceptance Criteria Mapping:
  AC1: truncate('hello world', 100) -> 'hello world' unchanged
  AC2: truncate('hello world foo', 8) -> 'hello...' (word boundary)
  AC3: truncate('hello world', 5, '...') -> ValueError (max_length == len(suffix))
  AC4: truncate('hello world', 2, '...') -> ValueError (max_length < len(suffix))
  AC5: truncate('', 10) -> ''
  AC6: truncate('superlongword', 8) -> 'super...' (hard cut)
  AC7: truncate('hello world', 11) -> 'hello world' (exact length)
  AC8: truncate('hello world foo', 9, '!') -> 'hello wo!' (custom suffix)
  AC9: truncate('   ', 10) -> graceful handling of whitespace
"""

import pytest
from src.utils.text_truncator import truncate


class TestTruncateHappyPath:
    """Test cases for normal truncate behavior."""

    def test_should_return_text_unchanged_when_length_within_limit(self):
        """AC1: Text shorter than max_length returns unchanged."""
        result = truncate('hello world', 100)
        assert result == 'hello world'

    def test_should_return_text_unchanged_when_length_equals_max_length(self):
        """AC7: Text exactly at max_length returns unchanged."""
        result = truncate('hello world', 11)
        assert result == 'hello world'

    def test_should_break_at_word_boundary_with_default_suffix(self):
        """AC2: Truncates at last word boundary before max_length."""
        result = truncate('hello world foo', 8)
        assert result == 'hello...'

    def test_should_break_at_word_boundary_with_custom_suffix(self):
        """AC8: Custom suffix replaces default ellipsis."""
        result = truncate('hello world foo', 9, '!')
        assert result == 'hello wo!'

    def test_should_truncate_long_word_when_no_boundary_exists(self):
        """AC6: Hard truncate at max_length - len(suffix) for single long words."""
        result = truncate('superlongword', 8)
        assert result == 'super...'

    def test_should_return_empty_string_when_input_empty(self):
        """AC5: Empty string input returns empty string."""
        result = truncate('', 10)
        assert result == ''

    def test_should_handle_multiple_word_boundaries(self):
        """Multiple words should truncate at appropriate boundary."""
        result = truncate('one two three four five', 12)
        assert result == 'one two...'

    def test_should_preserve_whitespace_before_boundary(self):
        """Whitespace handling in word boundary detection."""
        result = truncate('hello world', 8)
        assert result == 'hello...'

    def test_should_handle_single_word_longer_than_limit(self):
        """Single word longer than max_length truncates with hard cut."""
        result = truncate('antidisestablishmentarianism', 10)
        assert result == 'antidis...'


class TestTruncateErrorCases:
    """Test cases for error conditions."""

    def test_should_raise_value_error_when_max_length_equals_suffix_length(self):
        """AC3: ValueError when max_length == len(suffix)."""
        with pytest.raises(ValueError):
            truncate('hello world', 5, '...')  # 5 == len('...')

    def test_should_raise_value_error_when_max_length_less_than_suffix_length(self):
        """AC4: ValueError when max_length < len(suffix)."""
        with pytest.raises(ValueError):
            truncate('hello world', 2, '...')  # 2 < 3

    def test_should_raise_value_error_with_custom_suffix_too_long(self):
        """ValueError when custom suffix is longer than max_length."""
        with pytest.raises(ValueError):
            truncate('hello world', 5, 'suffix!')  # 7 > 5

    def test_should_raise_value_error_with_single_char_max_and_default_suffix(self):
        """ValueError when max_length is 1 and default suffix is 3 chars."""
        with pytest.raises(ValueError):
            truncate('hello', 1)

    def test_should_raise_value_error_with_zero_max_length(self):
        """ValueError when max_length is 0."""
        with pytest.raises(ValueError):
            truncate('hello', 0)


class TestTruncateEdgeCases:
    """Test cases for boundary conditions and edge cases."""

    def test_should_handle_whitespace_only_input(self):
        """AC9: Whitespace-only text handled gracefully."""
        result = truncate('   ', 10)
        # Whitespace-only should be treated as trimmed away or truncated to empty
        assert isinstance(result, str)
        assert len(result) <= 10

    def test_should_handle_tabs_and_newlines(self):
        """Whitespace types (tabs, newlines) handled gracefully."""
        result = truncate('\t\n\t', 10)
        assert isinstance(result, str)
        assert len(result) <= 10

    def test_should_handle_text_with_multiple_spaces_between_words(self):
        """Multiple consecutive spaces between words."""
        result = truncate('hello    world   foo', 10)
        assert result.endswith('...')
        assert len(result) <= 10

    def test_should_handle_very_long_text(self):
        """Very long text truncates correctly."""
        long_text = ' '.join(['word'] * 1000)
        result = truncate(long_text, 20)
        assert len(result) == 20
        assert result.endswith('...')

    def test_should_truncate_exactly_at_max_length(self):
        """Result length must not exceed max_length."""
        result = truncate('hello world foo bar baz', 15)
        assert len(result) <= 15

    def test_should_preserve_special_characters_in_text(self):
        """Special characters preserved before truncation point."""
        result = truncate('hello-world foo_bar', 12)
        assert '-' in result or '_' in result or result == 'hello-world'

    def test_should_handle_unicode_text(self):
        """Unicode characters handled correctly."""
        result = truncate('café résumé naïve', 12)
        assert isinstance(result, str)
        assert len(result) <= 12

    def test_should_truncate_text_with_no_spaces(self):
        """Text with no word boundaries truncates at hard position."""
        result = truncate('abcdefghijklmnop', 8)
        assert result == 'abcde...'

    def test_should_handle_suffix_of_length_one(self):
        """Custom suffix of single character."""
        result = truncate('hello world foo', 8, '.')
        assert len(result) == 8
        assert result.endswith('.')

    def test_should_handle_empty_string_with_custom_suffix(self):
        """Empty string with custom suffix returns empty string."""
        result = truncate('', 10, '>>>')
        assert result == ''

    def test_should_return_suffix_only_when_content_fits_in_suffix_space(self):
        """When only suffix length available, return suffix or empty based on implementation."""
        # max_length = 4, suffix = '...' (3 chars)
        # This should allow 1 char of content
        result = truncate('a', 4, '...')
        assert len(result) <= 4

    def test_should_handle_hyphenated_words_at_boundary(self):
        """Hyphenated words treated as single word or split at hyphen."""
        result = truncate('hello-world foo bar', 10)
        assert '...' in result
        assert len(result) <= 10

    def test_should_preserve_content_when_exactly_one_word_fits(self):
        """When exactly one word fits with suffix."""
        result = truncate('hello world', 8)
        # 'hello' is 5 chars, '...' is 3 chars = 8 total
        assert result == 'hello...'

    def test_should_handle_leading_spaces(self):
        """Text with leading spaces."""
        result = truncate('   hello world', 10)
        assert isinstance(result, str)
        assert len(result) <= 10

    def test_should_handle_trailing_spaces_in_text(self):
        """Text with trailing spaces before truncation point."""
        result = truncate('hello world   ', 8)
        assert len(result) <= 8
        assert '...' in result


class TestTruncateIntegration:
    """Integration tests combining multiple requirements."""

    def test_should_truncate_and_suffix_correctly_combined(self):
        """Truncation and suffix combine to respect max_length."""
        result = truncate('the quick brown fox jumps', 15, '...')
        assert len(result) == 15
        assert result.endswith('...')
        assert 'quick' in result or result == 'the quick br...'

    def test_should_handle_real_world_sentence(self):
        """Real-world example: truncate sentence for display."""
        text = 'The quick brown fox jumps over the lazy dog'
        result = truncate(text, 20)
        assert len(result) <= 20
        assert '...' in result

    def test_should_maintain_readability_with_custom_suffix(self):
        """Custom suffix maintains truncation semantics."""
        result = truncate('hello world foo', 10, ' [more]')
        assert '[more]' in result
        assert len(result) <= 10

    def test_should_work_with_default_suffix_consistently(self):
        """Default suffix '...' works consistently."""
        result1 = truncate('hello world foo', 8, '...')
        result2 = truncate('hello world foo', 8)
        assert result1 == result2
        assert result1 == 'hello...'
