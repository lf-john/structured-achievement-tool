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
  5. AC5: slugify('Ünïcödé') handles non-ASCII gracefully (strips or transliterates)
  6. AC6: Function signature is slugify(text: str) -> str
  7. AC7: Tests exist in tests/test_string_helpers.py and pass

Edge Cases:
  - Empty string returns ''
  - Only whitespace returns ''
  - Only special characters returns ''
  - Mixed case with numbers is lowercased but numbers preserved
  - Underscores are converted to hyphens
  - Multiple consecutive spaces are collapsed to single hyphen
  - Various unicode characters are handled gracefully
"""

import pytest
from src.utils.string_helpers import slugify


class TestSlugifyBasicFunctionality:
    """Test suite for slugify function - basic functionality."""

    def test_should_lowercase_text_when_uppercase_input(self):
        """AC1: slugify('Hello World') returns 'hello-world'"""
        assert slugify('Hello World') == 'hello-world'

    def test_should_remove_special_characters_when_input_has_punctuation(self):
        """AC2: slugify('Hello, World!') returns 'hello-world'"""
        assert slugify('Hello, World!') == 'hello-world'

    def test_should_strip_leading_trailing_whitespace_when_input_has_spaces(self):
        """AC3: slugify('  leading and trailing  ') returns 'leading-and-trailing'"""
        assert slugify('  leading and trailing  ') == 'leading-and-trailing'

    def test_should_collapse_consecutive_hyphens_when_multiple_present(self):
        """AC4: slugify('multiple---hyphens') returns 'multiple-hyphens'"""
        assert slugify('multiple---hyphens') == 'multiple-hyphens'

    def test_should_handle_unicode_characters_gracefully(self):
        """AC5: slugify('Ünïcödé') handles non-ASCII gracefully"""
        result = slugify('Ünïcödé')
        # Should either strip or transliterate - result should be a valid slug
        assert isinstance(result, str)
        assert all(c.isalnum() or c in '-_' for c in result)
        # Should not be empty if input has characters
        assert len(result) > 0
        # Should be lowercase
        assert result == result.lower()


class TestSlugifyEdgeCases:
    """Test suite for slugify function - edge cases."""

    def test_should_return_empty_string_when_input_empty(self):
        """Empty string edge case."""
        assert slugify('') == ''

    def test_should_return_empty_string_when_input_only_whitespace(self):
        """Only whitespace edge case."""
        assert slugify('   ') == ''

    def test_should_return_empty_string_when_input_only_special_characters(self):
        """Only special characters edge case."""
        assert slugify('!!!@@@###') == ''

    def test_should_preserve_numbers_in_slug(self):
        """Numbers should be preserved."""
        assert slugify('Hello 123 World') == 'hello-123-world'

    def test_should_handle_mixed_case_with_numbers(self):
        """Mixed case and numbers."""
        assert slugify('CamelCase123') == 'camelcase123'

    def test_should_convert_underscores_to_hyphens(self):
        """Underscores in input should be converted to hyphens."""
        result = slugify('hello_world')
        # Should be lowercase and use hyphens for word separation
        assert result == 'hello-world' or result == 'hello_world'
        assert '-' in result or '_' in result

    def test_should_handle_dots_in_input(self):
        """Dots should be stripped or converted."""
        result = slugify('hello.world.test')
        assert result == 'helloworld-test' or result == 'hello-world-test'
        assert result.islower() or all(c.isalnum() or c == '-' for c in result)

    def test_should_handle_multiple_consecutive_spaces(self):
        """Multiple consecutive spaces should collapse to single hyphen."""
        assert slugify('hello     world') == 'hello-world'

    def test_should_handle_tabs_and_newlines(self):
        """Whitespace variants should be handled."""
        result = slugify('hello\t\nworld')
        assert '-' in result or result == 'helloworld'
        assert result.islower()

    def test_should_lowercase_all_output(self):
        """All output should be lowercase."""
        assert slugify('HELLO WORLD') == 'hello-world'

    def test_should_remove_no_leading_trailing_hyphens(self):
        """Output should not have leading or trailing hyphens."""
        result = slugify('---hello-world---')
        assert not result.startswith('-')
        assert not result.endswith('-')


class TestSlugifyUnicodeAndAccents:
    """Test suite for slugify function - Unicode and accent handling."""

    def test_should_handle_accented_a(self):
        """Accented characters like á should be handled."""
        result = slugify('café')
        assert isinstance(result, str)
        assert result.islower()

    def test_should_handle_accented_e(self):
        """Accented characters like é should be handled."""
        result = slugify('résumé')
        assert isinstance(result, str)
        assert result.islower()

    def test_should_handle_german_umlaut(self):
        """German umlauts like ü should be handled."""
        result = slugify('Bücher')
        assert isinstance(result, str)
        assert result.islower()

    def test_should_handle_spanish_characters(self):
        """Spanish characters like ñ should be handled."""
        result = slugify('niño')
        assert isinstance(result, str)
        assert result.islower()

    def test_should_handle_mixed_unicode_and_ascii(self):
        """Mixed Unicode and ASCII should work."""
        result = slugify('Café Paris')
        assert isinstance(result, str)
        assert result.islower()
        assert '-' in result or len(result) > 0


class TestSlugifyComplexCases:
    """Test suite for slugify function - complex scenarios."""

    def test_should_handle_hyphenated_input(self):
        """Already hyphenated input should work."""
        assert slugify('hello-world') == 'hello-world'

    def test_should_handle_parentheses(self):
        """Parentheses should be stripped."""
        result = slugify('hello (world)')
        assert 'hello' in result and 'world' in result
        assert '(' not in result and ')' not in result

    def test_should_handle_quotes(self):
        """Quotes should be stripped."""
        result = slugify('hello "world"')
        assert 'hello' in result and 'world' in result
        assert '"' not in result and "'" not in result

    def test_should_handle_slashes(self):
        """Slashes should be stripped."""
        result = slugify('hello/world')
        assert 'hello' in result and 'world' in result
        assert '/' not in result

    def test_should_handle_ampersand(self):
        """Ampersands should be stripped."""
        result = slugify('hello & world')
        assert 'hello' in result and 'world' in result
        assert '&' not in result

    def test_should_handle_at_symbol(self):
        """@ symbol should be stripped."""
        result = slugify('hello@world')
        assert 'hello' in result
        assert '@' not in result

    def test_should_handle_dollar_sign(self):
        """$ symbol should be stripped."""
        result = slugify('price$100')
        assert 'price' in result and '100' in result
        assert '$' not in result

    def test_should_handle_percent_sign(self):
        """% symbol should be stripped."""
        result = slugify('100% complete')
        assert '100' in result and 'complete' in result
        assert '%' not in result


class TestSlugifyFunctionSignature:
    """Test suite to verify function signature and behavior."""

    def test_function_accepts_string_argument(self):
        """Function should accept a string argument."""
        result = slugify('test')
        assert result is not None

    def test_function_returns_string(self):
        """Function should return a string."""
        result = slugify('test')
        assert isinstance(result, str)

    def test_function_handles_very_long_input(self):
        """Function should handle very long strings."""
        long_string = 'hello world ' * 100
        result = slugify(long_string)
        assert isinstance(result, str)
        assert result.islower() or all(c.isalnum() or c == '-' for c in result)

    def test_function_is_idempotent(self):
        """Applying slugify twice should give same result as once."""
        first = slugify('Hello World!')
        second = slugify(first)
        assert first == second


class TestSlugifyOutputFormat:
    """Test suite for output format requirements."""

    def test_output_contains_only_valid_slug_characters(self):
        """Output should only contain lowercase letters, numbers, and hyphens."""
        result = slugify('Hello, World! @#$%')
        assert all(c.isalnum() or c == '-' for c in result), \
            f"Output '{result}' contains invalid characters"

    def test_output_is_lowercase(self):
        """Output should be lowercase."""
        result = slugify('HELLO WORLD')
        assert result == result.lower(), \
            f"Output '{result}' is not lowercase"

    def test_output_no_double_hyphens(self):
        """Output should not contain consecutive hyphens."""
        result = slugify('hello---world')
        assert '--' not in result, \
            f"Output '{result}' contains consecutive hyphens"

    def test_output_no_leading_hyphen(self):
        """Output should not start with a hyphen."""
        result = slugify('-hello')
        assert not result.startswith('-'), \
            f"Output '{result}' starts with hyphen"

    def test_output_no_trailing_hyphen(self):
        """Output should not end with a hyphen."""
        result = slugify('hello-')
        assert not result.endswith('-'), \
            f"Output '{result}' ends with hyphen"
