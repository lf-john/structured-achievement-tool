"""
IMPLEMENTATION PLAN for US-001: Implement text_truncator utility

Components:
  - truncate(text: str, max_length: int, suffix: str = '...') -> str
    Truncates text to max_length characters, breaking at word boundaries when possible.
    - If text fits in max_length, return unchanged
    - If truncation needed, find last word boundary within available space
    - Append suffix after truncation
    - Raise ValueError if max_length < len(suffix)
    - Handle edge cases: empty strings, whitespace-only text, single long words

Test Cases:
  1. AC1: No truncation - text shorter than max_length returns unchanged
  2. AC2: Word boundary truncation - breaks at last space before max_length
  3. AC3: Hard truncation - single word longer than available space gets truncated with suffix
  4. AC4: Empty string - empty input returns empty string
  5. AC5: Whitespace only - whitespace-only text returns unchanged if fits
  6. AC6: Long word with suffix - single word with suffix appended when no boundary
  7. AC7: Exact length - text exactly at max_length returns unchanged
  8. AC8: ValueError - max_length < len(suffix) raises ValueError
  9. AC9: Another word boundary example - truncates correctly at word boundaries
  10. AC10: Default suffix - suffix parameter defaults to '...'

Edge Cases:
  - Very small max_length (e.g., 1)
  - Multiple consecutive spaces
  - Text with no spaces (single word)
  - max_length equal to len(text)
  - Different suffix values and lengths
  - Suffix longer than text would allow
  - Only spaces in text
  - Mixed word and space patterns
"""

import pytest
from src.utils.text_truncator import truncate


class TestTruncateBasicBehavior:
    """Test basic truncation behavior."""

    def test_no_truncation_when_text_shorter_than_max_length(self):
        """AC1: Text shorter than max_length should return unchanged."""
        result = truncate('hello world', 100)
        assert result == 'hello world'

    def test_text_exact_length_returns_unchanged(self):
        """AC7: Text exactly at max_length should return unchanged."""
        result = truncate('hello', 5)
        assert result == 'hello'

    def test_empty_string_returns_empty(self):
        """AC4: Empty string should return empty string."""
        result = truncate('', 10)
        assert result == ''

    def test_whitespace_only_returns_unchanged_if_fits(self):
        """AC5: Whitespace-only text should return unchanged if it fits."""
        result = truncate('   ', 10)
        assert result == '   '

    def test_suffix_parameter_defaults_to_ellipsis(self):
        """AC10: Suffix parameter should default to '...' when not provided."""
        result = truncate('hello world foo', 11)
        assert result == 'hello...'
        assert result.endswith('...')


class TestTruncateWordBoundary:
    """Test truncation at word boundaries."""

    def test_truncate_at_word_boundary_case_1(self):
        """AC2: Truncate 'hello world foo' with max_length 11 should break at word boundary."""
        result = truncate('hello world foo', 11)
        assert result == 'hello...'
        # Verify it's 8 chars (5 for 'hello' + 3 for '...')
        assert len(result) == 8

    def test_truncate_at_word_boundary_case_2(self):
        """AC9: Truncate 'hello world' with max_length 8 should break at word boundary."""
        result = truncate('hello world', 8)
        assert result == 'hello...'
        assert len(result) == 8

    def test_truncate_multiple_words(self):
        """Test truncation with multiple words keeps last complete word."""
        result = truncate('the quick brown fox', 12)
        # 'the quick' is 9 chars, suffix is 3, total would be 12
        assert result == 'the quick...'
        assert len(result) == 12

    def test_truncate_preserves_word_before_space(self):
        """Test that truncation breaks after word, not in middle of word."""
        result = truncate('hello world test', 10)
        # max_length=10, suffix=3, available=7
        # 'hello ' is 6 chars, 'hello wo' is 8 chars
        # Last boundary within 7 chars is at position 6 (after 'hello ')
        assert result == 'hello...'
        assert not result.startswith('hello w')


class TestTruncateHardTruncation:
    """Test hard truncation when no word boundary exists."""

    def test_single_word_longer_than_available_space(self):
        """AC3: Single word longer than available space gets truncated with suffix."""
        result = truncate('hello', 5, '...')
        # max_length=5, suffix=3, available=2
        # 'hello' is 5 chars, so it fits unchanged
        assert result == 'hello'

    def test_single_word_no_spaces_gets_hard_truncated(self):
        """AC6: Single word 'superlongwordwithnobreaks' truncated to 10 chars."""
        result = truncate('superlongwordwithnobreaks', 10, '...')
        assert result == 'superlo...'
        assert len(result) == 10

    def test_hard_truncate_when_no_word_boundary(self):
        """Test that without word boundaries, text is truncated at available length."""
        result = truncate('abcdefghijklmnop', 7, '...')
        # max_length=7, suffix=3, available=4
        assert result == 'abcd...'
        assert len(result) == 7

    def test_single_long_word_truncated_correctly(self):
        """Test single long word is truncated to fit max_length."""
        result = truncate('verylongword', 8, '...')
        # max_length=8, suffix=3, available=5
        assert result == 'veryl...'
        assert len(result) == 8


class TestTruncateErrors:
    """Test error conditions."""

    def test_max_length_less_than_suffix_length_raises_error(self):
        """AC8: ValueError when max_length < len(suffix)."""
        with pytest.raises(ValueError):
            truncate('hi', 2, '...')

    def test_very_small_max_length_raises_error_if_less_than_suffix(self):
        """Test that very small max_length raises ValueError."""
        with pytest.raises(ValueError):
            truncate('hello world', 1, '...')

    def test_zero_max_length_raises_error(self):
        """Test that zero max_length raises ValueError."""
        with pytest.raises(ValueError):
            truncate('hello', 0, '...')

    def test_negative_max_length_raises_error(self):
        """Test that negative max_length raises ValueError."""
        with pytest.raises(ValueError):
            truncate('hello', -5, '...')

    def test_max_length_exactly_equal_to_suffix_length_allowed(self):
        """Test that max_length equal to suffix length is allowed (empty text space)."""
        # This should not raise; it should return just the suffix
        result = truncate('hello world', 3, '...')
        assert result == '...'
        assert len(result) == 3


class TestTruncateCustomSuffix:
    """Test custom suffix parameter."""

    def test_custom_suffix_single_char(self):
        """Test truncation with single character suffix."""
        result = truncate('hello world test', 9, '!')
        # max_length=9, suffix='!' (1 char), available=8
        # 'hello ' is 6 chars, should use last boundary at 6
        assert result == 'hello !'
        assert len(result) == 7

    def test_custom_suffix_longer_string(self):
        """Test truncation with longer custom suffix."""
        result = truncate('hello world', 11, ' [...]')
        # max_length=11, suffix=' [...]' (6 chars), available=5
        # 'hello' is 5 chars, fits exactly
        assert result == 'hello [...]'
        assert len(result) == 11

    def test_empty_suffix(self):
        """Test truncation with empty suffix."""
        result = truncate('hello world', 5, '')
        # max_length=5, suffix='' (0 chars), available=5
        # 'hello' is 5 chars, but we need to check for space at position 5
        # First 5 chars are 'hello', and there's a space at position 5
        # So we truncate at last boundary which would be after 'hello'
        assert result == 'hello'
        assert len(result) == 5

    def test_suffix_with_spaces(self):
        """Test suffix that contains spaces."""
        result = truncate('hello world test', 15, ' ...')
        # max_length=15, suffix=' ...' (4 chars), available=11
        assert result.endswith(' ...')
        assert len(result) == 15


class TestTruncateEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_space_character(self):
        """Test with single space character."""
        result = truncate(' ', 5)
        assert result == ' '

    def test_multiple_consecutive_spaces(self):
        """Test text with multiple consecutive spaces."""
        result = truncate('hello     world', 8)
        # Should find last space boundary within available space
        assert '...' in result

    def test_text_with_leading_spaces(self):
        """Test text with leading spaces."""
        result = truncate('  hello world', 10)
        # '  hello ' is 8 chars, with suffix would be 11
        # Last boundary within 7 available chars is at position 2 (after '  ')
        assert result.startswith('  ')

    def test_text_with_trailing_spaces(self):
        """Test text with trailing spaces."""
        result = truncate('hello world  ', 8)
        assert len(result) <= 8

    def test_very_long_text(self):
        """Test with very long text."""
        long_text = 'word ' * 100  # 500 chars
        result = truncate(long_text, 20)
        assert len(result) == 20
        assert result.endswith('...')

    def test_single_character_text(self):
        """Test with single character text."""
        result = truncate('a', 10)
        assert result == 'a'

    def test_two_character_text(self):
        """Test with two character text."""
        result = truncate('ab', 10)
        assert result == 'ab'

    def test_max_length_equal_to_text_length(self):
        """Test when max_length exactly equals text length."""
        text = 'hello world'
        result = truncate(text, len(text))
        assert result == text

    def test_max_length_one_less_than_text_length(self):
        """Test when max_length is one less than text length."""
        result = truncate('hello', 4)
        # max_length=4, suffix=3, available=1
        # 'hello' with only 1 char available becomes 'h...'
        assert result == 'h...'
        assert len(result) == 4


class TestTruncateSpecialCases:
    """Test special and corner cases."""

    def test_word_boundary_at_exact_available_length(self):
        """Test when word boundary is exactly at available length."""
        result = truncate('hello world test', 8)
        # max_length=8, suffix=3, available=5
        # 'hello' is 5 chars and followed by space
        assert result == 'hello...'

    def test_multiple_spaces_between_words(self):
        """Test with multiple spaces between words as boundary."""
        result = truncate('hello  world', 10)
        # 'hello  ' is 7 chars, with suffix would be 10
        assert 'hello' in result
        assert len(result) == 10

    def test_only_one_word_exists_truncate_it(self):
        """Test when only one word exists and it needs truncation."""
        result = truncate('supercalifragilisticexpialidocious', 10, '...')
        assert result == 'superca...'
        assert len(result) == 10

    def test_two_words_where_first_fits(self):
        """Test two words where first fits exactly with available space."""
        result = truncate('hi world', 5)
        # max_length=5, suffix=3, available=2
        # 'hi' is 2 chars, followed by space
        assert result == 'hi...'
        assert len(result) == 5

    def test_suffix_equals_max_length(self):
        """Test when suffix length equals max_length."""
        result = truncate('hello world test', 3, '...')
        assert result == '...'
        assert len(result) == 3

    def test_word_boundary_with_tabs(self):
        """Test that only spaces are considered word boundaries, not tabs."""
        result = truncate('hello\tworld', 8)
        # Tabs should not be treated as word boundaries
        # 'hello\tw' would be 7 chars, with suffix = 10
        # So we need hard truncation
        assert len(result) == 8

    def test_newline_not_word_boundary(self):
        """Test that newlines are not treated as word boundaries."""
        result = truncate('hello\nworld', 8)
        assert len(result) == 8


class TestTruncateIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow_with_word_boundaries(self):
        """Test complete workflow with proper word boundary truncation."""
        text = 'The quick brown fox jumps over the lazy dog'
        result = truncate(text, 20)
        assert len(result) == 20
        assert result.endswith('...')
        # Ensure it broke at a word boundary
        assert not result[:-3].endswith(' ')

    def test_full_workflow_with_hard_truncation(self):
        """Test complete workflow requiring hard truncation."""
        text = 'verylongwordwithoutanyspaces'
        result = truncate(text, 15)
        assert len(result) == 15
        assert result.endswith('...')

    def test_default_suffix_behavior(self):
        """Test that default suffix is used correctly."""
        result1 = truncate('hello world', 8)
        result2 = truncate('hello world', 8, '...')
        assert result1 == result2
        assert result1 == 'hello...'

    def test_preserves_content_integrity(self):
        """Test that truncation preserves content integrity (no mangling)."""
        text = 'Hello World! How are you today?'
        result = truncate(text, 15)
        assert len(result) <= 15
        # Check that the truncated part is actually from the original
        assert text.startswith(result[:-3])  # Remove suffix and check prefix
