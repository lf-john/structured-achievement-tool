"""
IMPLEMENTATION PLAN for US-001: Implement slugify utility function

Components:
  - src/utils/string_helpers.py: Module containing string utility functions
  - slugify(text: str) -> str: Converts arbitrary text to URL-safe slugs by:
      1. Converting to lowercase
      2. Replacing spaces with hyphens
      3. Stripping all non-alphanumeric and non-hyphen characters
      4. Collapsing multiple consecutive hyphens into one
      5. Stripping leading/trailing hyphens

Test Cases (mapped to acceptance criteria):
  1. AC1: Basic case with spaces → test_should_convert_hello_world_to_hello_hyphen_world
  2. AC2: Case with punctuation → test_should_strip_punctuation_from_text
  3. AC3: Leading/trailing spaces → test_should_strip_leading_trailing_whitespace
  4. AC4: Multiple spaces → test_should_collapse_multiple_spaces_to_single_hyphen
  5. AC5: Special characters → test_should_remove_special_characters
  6. AC6: Already slug format → test_should_return_unchanged_for_valid_slug
  7. AC7: Empty string → test_should_return_empty_for_empty_input
  8. AC8: Importability → test_should_be_importable_from_src_utils_string_helpers

Edge Cases:
  - Only special characters
  - Numbers in text
  - Uppercase letters
  - Multiple consecutive hyphens after processing
  - Mixed whitespace (tabs, newlines)
"""

import pytest
from src.utils.string_helpers import slugify


class TestSlugifyBasicFunctionality:
    """Test suite for the slugify function's basic functionality."""

    def test_should_convert_hello_world_to_hello_hyphen_world(self):
        """AC1: slugify('Hello World') returns 'hello-world'."""
        result = slugify('Hello World')
        assert result == 'hello-world'

    def test_should_strip_punctuation_from_text(self):
        """AC2: slugify('Hello, World!') returns 'hello-world'."""
        result = slugify('Hello, World!')
        assert result == 'hello-world'

    def test_should_strip_leading_trailing_whitespace(self):
        """AC3: slugify('  spaces  ') returns 'spaces'."""
        result = slugify('  spaces  ')
        assert result == 'spaces'

    def test_should_collapse_multiple_spaces_to_single_hyphen(self):
        """AC4: slugify('multiple   spaces') returns 'multiple-spaces'."""
        result = slugify('multiple   spaces')
        assert result == 'multiple-spaces'

    def test_should_remove_special_characters(self):
        """AC5: slugify('Special @#$ Chars') returns 'special-chars'."""
        result = slugify('Special @#$ Chars')
        assert result == 'special-chars'

    def test_should_return_unchanged_for_valid_slug(self):
        """AC6: slugify('already-slug') returns 'already-slug'."""
        result = slugify('already-slug')
        assert result == 'already-slug'

    def test_should_return_empty_for_empty_input(self):
        """AC7: slugify('') returns ''."""
        result = slugify('')
        assert result == ''


class TestSlugifyEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_should_handle_only_special_characters(self):
        """Edge case: Input contains only special characters."""
        result = slugify('@#$%^&*()')
        assert result == ''

    def test_should_preserve_numbers(self):
        """Edge case: Numbers should be preserved in the slug."""
        result = slugify('Hello 123 World')
        assert result == 'hello-123-world'

    def test_should_convert_uppercase_to_lowercase(self):
        """Edge case: All uppercase text should be converted to lowercase."""
        result = slugify('UPPERCASE')
        assert result == 'uppercase'

    def test_should_collapse_consecutive_hyphens(self):
        """Edge case: Multiple consecutive hyphens should become one."""
        result = slugify('hello---world')
        assert result == 'hello-world'

    def test_should_handle_mixed_whitespace(self):
        """Edge case: Tabs and newlines should be treated as spaces."""
        result = slugify('hello\tworld\ntest')
        assert result == 'hello-world-test'

    def test_should_strip_leading_hyphens(self):
        """Edge case: Leading hyphens should be stripped."""
        result = slugify('---hello')
        assert result == 'hello'

    def test_should_strip_trailing_hyphens(self):
        """Edge case: Trailing hyphens should be stripped."""
        result = slugify('hello---')
        assert result == 'hello'

    def test_should_strip_both_leading_and_trailing_hyphens(self):
        """Edge case: Both leading and trailing hyphens should be stripped."""
        result = slugify('---hello---')
        assert result == 'hello'

    def test_should_handle_hyphen_separated_words(self):
        """Edge case: Words already separated by hyphens should remain."""
        result = slugify('hello-world-test')
        assert result == 'hello-world-test'

    def test_should_handle_text_with_apostrophes(self):
        """Edge case: Apostrophes (non-alphanumeric) should be removed."""
        result = slugify("it's nice")
        assert result == 'its-nice'

    def test_should_handle_text_with_parentheses(self):
        """Edge case: Parentheses should be removed, spaces preserved."""
        result = slugify('hello (world)')
        assert result == 'hello-world'

    def test_should_handle_single_character(self):
        """Edge case: Single character input."""
        result = slugify('a')
        assert result == 'a'

    def test_should_handle_single_special_character(self):
        """Edge case: Single special character should return empty."""
        result = slugify('@')
        assert result == ''

    def test_should_handle_text_with_dots(self):
        """Edge case: Dots should be removed."""
        result = slugify('file.name.test')
        assert result == 'filename-test'

    def test_should_handle_text_with_slashes(self):
        """Edge case: Slashes should be removed."""
        result = slugify('path/to/file')
        assert result == 'pathtofile'

    def test_should_handle_text_with_commas_and_periods(self):
        """Edge case: Punctuation marks should be removed."""
        result = slugify('hello, world. test!')
        assert result == 'hello-world-test'

    def test_should_handle_multiple_consecutive_spaces(self):
        """Edge case: Many consecutive spaces should become single hyphen."""
        result = slugify('hello          world')
        assert result == 'hello-world'

    def test_should_handle_leading_spaces_and_hyphens(self):
        """Edge case: Leading spaces and special chars should be stripped."""
        result = slugify('  ---hello')
        assert result == 'hello'

    def test_should_return_string_type(self):
        """Edge case: Return value should always be a string."""
        result = slugify('test')
        assert isinstance(result, str)

    def test_should_handle_very_long_text(self):
        """Edge case: Long text should be processed correctly."""
        long_text = 'hello world ' * 100
        result = slugify(long_text)
        # Result should be 'hello-world' repeated with proper hyphen collapsing
        assert 'hello-world' in result
        assert result.startswith('hello-world')


class TestSlugifyImportability:
    """Test suite for module importability and function availability."""

    def test_should_be_importable_from_src_utils_string_helpers(self):
        """AC8: Function should be importable from src.utils.string_helpers."""
        # If we got here, the import in the module header succeeded
        assert callable(slugify)
        assert hasattr(slugify, '__name__')
        assert slugify.__name__ == 'slugify'

    def test_slugify_function_accepts_string_parameter(self):
        """Function should accept a string parameter."""
        # This will fail if the function doesn't exist or has wrong signature
        try:
            slugify('test')
        except TypeError as e:
            pytest.fail(f"slugify() has incorrect signature: {e}")

    def test_slugify_function_returns_string(self):
        """Function should return a string value."""
        result = slugify('test')
        assert isinstance(result, str)
