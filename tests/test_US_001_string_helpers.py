"""
IMPLEMENTATION PLAN for US-001: Implement slugify utility function

Components:
  - src/utils/__init__.py: Package initialization
  - src/utils/string_helpers.py: Contains slugify(text: str) -> str function

Test Cases (mapped to acceptance criteria):
  1. AC1: slugify('Hello World') returns 'hello-world'
  2. AC2: slugify('Hello, World!') returns 'hello-world'
  3. AC3: slugify('  leading and trailing  ') returns 'leading-and-trailing'
  4. AC4: slugify('multiple---hyphens') returns 'multiple-hyphens'
  5. AC5: slugify('special @#$ chars') returns 'special-chars'
  6. AC6: slugify('') returns ''
  7. AC7: Function is importable from src.utils.string_helpers

Edge Cases:
  - Only whitespace returns ''
  - Only special characters returns ''
  - Mixed case with numbers is lowercased but numbers preserved
  - Multiple consecutive spaces collapse to single hyphen
"""

import pytest
import sys


class TestSlugifyAcceptanceCriteria:
    """Test suite for slugify function - acceptance criteria."""

    def test_should_lowercase_and_replace_spaces_with_hyphens(self):
        """AC1: slugify('Hello World') returns 'hello-world'"""
        from src.utils.string_helpers import slugify
        assert slugify('Hello World') == 'hello-world'

    def test_should_remove_punctuation_when_input_has_special_chars(self):
        """AC2: slugify('Hello, World!') returns 'hello-world'"""
        from src.utils.string_helpers import slugify
        assert slugify('Hello, World!') == 'hello-world'

    def test_should_strip_leading_and_trailing_whitespace(self):
        """AC3: slugify('  leading and trailing  ') returns 'leading-and-trailing'"""
        from src.utils.string_helpers import slugify
        assert slugify('  leading and trailing  ') == 'leading-and-trailing'

    def test_should_collapse_multiple_consecutive_hyphens(self):
        """AC4: slugify('multiple---hyphens') returns 'multiple-hyphens'"""
        from src.utils.string_helpers import slugify
        assert slugify('multiple---hyphens') == 'multiple-hyphens'

    def test_should_strip_special_at_hash_dollar_chars(self):
        """AC5: slugify('special @#$ chars') returns 'special-chars'"""
        from src.utils.string_helpers import slugify
        assert slugify('special @#$ chars') == 'special-chars'

    def test_should_return_empty_string_for_empty_input(self):
        """AC6: slugify('') returns ''"""
        from src.utils.string_helpers import slugify
        assert slugify('') == ''

    def test_should_be_importable_from_utils_module(self):
        """AC7: Function is importable from src.utils.string_helpers"""
        from src.utils.string_helpers import slugify
        assert callable(slugify)


class TestSlugifyEdgeCases:
    """Test suite for slugify function - edge cases."""

    def test_should_return_empty_for_whitespace_only(self):
        """Only whitespace should return empty string."""
        from src.utils.string_helpers import slugify
        assert slugify('   ') == ''

    def test_should_return_empty_for_special_chars_only(self):
        """Only special characters should return empty string."""
        from src.utils.string_helpers import slugify
        assert slugify('!!!@@@###$$$') == ''

    def test_should_preserve_numbers_in_slug(self):
        """Numbers in input should be preserved in output."""
        from src.utils.string_helpers import slugify
        assert slugify('Hello 123 World') == 'hello-123-world'

    def test_should_lowercase_mixed_case_with_numbers(self):
        """Mixed case with numbers should be lowercased but numbers preserved."""
        from src.utils.string_helpers import slugify
        assert slugify('CamelCase123Test') == 'camelcase123test'

    def test_should_handle_multiple_consecutive_spaces(self):
        """Multiple consecutive spaces should collapse to single hyphen."""
        from src.utils.string_helpers import slugify
        assert slugify('hello     world') == 'hello-world'

    def test_should_handle_tabs_and_newlines_as_whitespace(self):
        """Tabs and newlines should be treated as whitespace."""
        from src.utils.string_helpers import slugify
        assert slugify('hello\tworld\ntest') == 'hello-world-test'

    def test_should_strip_leading_and_trailing_hyphens(self):
        """Leading and trailing hyphens should be stripped."""
        from src.utils.string_helpers import slugify
        result = slugify('-hello-world-')
        assert not result.startswith('-')
        assert not result.endswith('-')

    def test_should_handle_dots_as_special_characters(self):
        """Dots should be stripped or converted to spaces/hyphens."""
        from src.utils.string_helpers import slugify
        result = slugify('hello.world')
        # Should be a valid slug: lowercase, no leading/trailing hyphens, no invalid chars
        assert result.islower()
        assert not result.startswith('-')
        assert not result.endswith('-')
        assert all(c.isalnum() or c == '-' for c in result)

    def test_should_handle_underscores_appropriately(self):
        """Underscores should be converted to hyphens or spaces."""
        from src.utils.string_helpers import slugify
        result = slugify('hello_world_test')
        assert result.islower()
        assert not result.startswith('-')
        assert not result.endswith('-')
        assert all(c.isalnum() or c == '-' for c in result)

    def test_should_return_string_type(self):
        """Function should always return a string."""
        from src.utils.string_helpers import slugify
        result = slugify('test')
        assert isinstance(result, str)

    def test_should_return_lowercase_result(self):
        """Result should always be lowercase."""
        from src.utils.string_helpers import slugify
        result = slugify('HELLO WORLD')
        assert result == result.lower()

    def test_should_handle_single_character_input(self):
        """Single character input should be handled correctly."""
        from src.utils.string_helpers import slugify
        assert slugify('a') == 'a'
        assert slugify('A') == 'a'
        assert slugify('-') == ''
        assert slugify('@') == ''

    def test_should_handle_all_alphanumeric_input(self):
        """Alphanumeric input without spaces or special chars should remain unchanged (but lowercased)."""
        from src.utils.string_helpers import slugify
        assert slugify('helloworld123') == 'helloworld123'
        assert slugify('HELLOWORLD123') == 'helloworld123'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
