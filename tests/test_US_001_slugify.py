"""
IMPLEMENTATION PLAN for US-001: Implement slugify utility function

Components:
  - src/utils/__init__.py: Package marker (empty file)
  - src/utils/string_helpers.py: Module containing slugify() function
    * slugify(text: str) -> str: Converts arbitrary text into URL-safe slugs

Function Requirements:
  - Convert text to lowercase
  - Replace whitespace with hyphens
  - Strip characters that are not alphanumeric or hyphens
  - Collapse multiple consecutive hyphens into one
  - Strip leading/trailing hyphens from the result

Test Cases (mapped to Acceptance Criteria):
  1. AC 1: slugify('Hello World') returns 'hello-world'
  2. AC 2: slugify('Hello, World!') returns 'hello-world'
  3. AC 3: slugify('  leading and trailing  ') returns 'leading-and-trailing'
  4. AC 4: slugify('multiple---hyphens') returns 'multiple-hyphens'
  5. AC 5: slugify('special @#$ chars') returns 'special-chars'
  6. AC 6: slugify('') returns ''
  7. AC 7: Function is importable from src.utils.string_helpers

Edge Cases:
  - Text with only whitespace
  - Text with only special characters
  - Text with numbers
  - Text with unicode/accented characters
  - Text with existing hyphens and spaces
  - Mixed case with punctuation
  - Single character input
  - Very long input
"""

import pytest
from src.utils.string_helpers import slugify


class TestSlugifyBasicCases:
    """Test acceptance criteria: Basic text transformations."""

    def test_simple_text_with_space(self):
        """AC 1: slugify('Hello World') returns 'hello-world'"""
        result = slugify('Hello World')
        assert result == 'hello-world'

    def test_text_with_punctuation(self):
        """AC 2: slugify('Hello, World!') returns 'hello-world'"""
        result = slugify('Hello, World!')
        assert result == 'hello-world'

    def test_leading_and_trailing_spaces(self):
        """AC 3: slugify('  leading and trailing  ') returns 'leading-and-trailing'"""
        result = slugify('  leading and trailing  ')
        assert result == 'leading-and-trailing'

    def test_multiple_consecutive_hyphens(self):
        """AC 4: slugify('multiple---hyphens') returns 'multiple-hyphens'"""
        result = slugify('multiple---hyphens')
        assert result == 'multiple-hyphens'

    def test_special_characters_removal(self):
        """AC 5: slugify('special @#$ chars') returns 'special-chars'"""
        result = slugify('special @#$ chars')
        assert result == 'special-chars'

    def test_empty_string(self):
        """AC 6: slugify('') returns ''"""
        result = slugify('')
        assert result == ''

    def test_importable_from_module(self):
        """AC 7: Function is importable from src.utils.string_helpers"""
        from src.utils.string_helpers import slugify as imported_slugify
        assert callable(imported_slugify)
        assert imported_slugify.__name__ == 'slugify'


class TestSlugifyEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_only_whitespace(self):
        """Input is only spaces should return empty string."""
        result = slugify('     ')
        assert result == ''

    def test_only_special_characters(self):
        """Input with only special characters should return empty string."""
        result = slugify('@#$%^&*()')
        assert result == ''

    def test_text_with_numbers(self):
        """Numbers should be preserved in the slug."""
        result = slugify('Hello 123 World')
        assert result == 'hello-123-world'

    def test_single_character(self):
        """Single alphanumeric character should be preserved."""
        result = slugify('a')
        assert result == 'a'

    def test_single_special_character(self):
        """Single special character should be removed."""
        result = slugify('@')
        assert result == ''

    def test_hyphen_at_start(self):
        """Leading hyphen should be stripped."""
        result = slugify('-hello')
        assert result == 'hello'

    def test_hyphen_at_end(self):
        """Trailing hyphen should be stripped."""
        result = slugify('hello-')
        assert result == 'hello'

    def test_hyphens_at_both_ends(self):
        """Both leading and trailing hyphens should be stripped."""
        result = slugify('---hello-world---')
        assert result == 'hello-world'

    def test_multiple_spaces_collapse(self):
        """Multiple consecutive spaces should become single hyphen."""
        result = slugify('hello     world')
        assert result == 'hello-world'

    def test_mixed_whitespace_types(self):
        """Different whitespace characters should be treated as hyphens."""
        result = slugify('hello\tworld\ntest')
        assert result == 'hello-world-test'

    def test_hyphen_and_space_combination(self):
        """Combination of hyphens and spaces."""
        result = slugify('hello- -world')
        assert result == 'hello-world'

    def test_all_uppercase(self):
        """All uppercase text should be converted to lowercase."""
        result = slugify('HELLO WORLD')
        assert result == 'hello-world'

    def test_mixed_case(self):
        """Mixed case should be converted to lowercase."""
        result = slugify('HeLLo WoRLd')
        assert result == 'hello-world'

    def test_numbers_only(self):
        """Numbers only should be preserved."""
        result = slugify('123456')
        assert result == '123456'

    def test_alphanumeric_with_special_chars(self):
        """Alphanumeric should be kept, special chars removed."""
        result = slugify('test123!@#abc')
        assert result == 'test123abc'

    def test_very_long_text(self):
        """Long text should be properly slugified."""
        long_text = 'This is a very long text with many words and special characters!@#$%'
        result = slugify(long_text)
        assert result == 'this-is-a-very-long-text-with-many-words-and-special-characters'

    def test_unicode_characters_removed(self):
        """Unicode characters that are not alphanumeric should be removed."""
        result = slugify('café')
        assert result == 'caf'  # 'é' is not ASCII alphanumeric, removed

    def test_punctuation_variety(self):
        """Various punctuation marks should be removed."""
        result = slugify('hello, world! how (are) you?')
        assert result == 'hello-world-how-are-you'

    def test_underscore_removal(self):
        """Underscores should be removed."""
        result = slugify('hello_world_test')
        assert result == 'helloworld-test'

    def test_parentheses_removal(self):
        """Parentheses should be removed."""
        result = slugify('test (something) here')
        assert result == 'test-something-here'

    def test_slash_removal(self):
        """Forward slashes should be removed."""
        result = slugify('path/to/file')
        assert result == 'pathtofile'

    def test_backslash_removal(self):
        """Backslashes should be removed."""
        result = slugify('path\\to\\file')
        assert result == 'pathtofile'

    def test_dots_removal(self):
        """Dots should be removed."""
        result = slugify('file.name.txt')
        assert result == 'filenametxt'

    def test_hash_removal(self):
        """Hash symbols should be removed."""
        result = slugify('#hashtag #another')
        assert result == 'hashtag-another'

    def test_dollar_removal(self):
        """Dollar signs should be removed."""
        result = slugify('$100 $200')
        assert result == '100-200'

    def test_percent_removal(self):
        """Percent signs should be removed."""
        result = slugify('100% discount')
        assert result == '100-discount'

    def test_ampersand_removal(self):
        """Ampersands should be removed."""
        result = slugify('cats & dogs')
        assert result == 'cats-dogs'

    def test_asterisk_removal(self):
        """Asterisks should be removed."""
        result = slugify('test*case*here')
        assert result == 'testcasehere'

    def test_plus_removal(self):
        """Plus signs should be removed."""
        result = slugify('C++ java+script')
        assert result == 'c-java-script'

    def test_equals_removal(self):
        """Equals signs should be removed."""
        result = slugify('a=b=c')
        assert result == 'abc'

    def test_pipe_removal(self):
        """Pipe symbols should be removed."""
        result = slugify('option1 | option2')
        assert result == 'option1-option2'

    def test_colon_removal(self):
        """Colons should be removed."""
        result = slugify('12:00:00 time')
        assert result == '120000-time'

    def test_semicolon_removal(self):
        """Semicolons should be removed."""
        result = slugify('statement;another;one')
        assert result == 'statementanotherone'

    def test_quote_removal(self):
        """Quotes should be removed."""
        result = slugify('"quoted" text \'here\'')
        assert result == 'quoted-text-here'

    def test_angle_brackets_removal(self):
        """Angle brackets should be removed."""
        result = slugify('<html>tag</html>')
        assert result == 'htmltaghtml'

    def test_square_brackets_removal(self):
        """Square brackets should be removed."""
        result = slugify('[array] [elements]')
        assert result == 'array-elements'

    def test_curly_braces_removal(self):
        """Curly braces should be removed."""
        result = slugify('{object} {json}')
        assert result == 'object-json'

    def test_question_mark_removal(self):
        """Question marks should be removed."""
        result = slugify('why? how? what?')
        assert result == 'why-how-what'

    def test_exclamation_removal(self):
        """Exclamation marks should be removed."""
        result = slugify('wow! great! awesome!')
        assert result == 'wow-great-awesome'

    def test_tilde_removal(self):
        """Tildes should be removed."""
        result = slugify('~approximate ~value')
        assert result == 'approximate-value'

    def test_backtick_removal(self):
        """Backticks should be removed."""
        result = slugify('`code` `here`')
        assert result == 'code-here'

    def test_combined_complex_string(self):
        """Complex string with many different special characters."""
        result = slugify('!@#$%^&*()_+-={}[]|:;<>,.?/~`')
        assert result == ''

    def test_complex_real_world_example(self):
        """Real-world example: document title."""
        result = slugify('How to Build a REST API (2024) - Best Practices!')
        assert result == 'how-to-build-a-rest-api-2024-best-practices'


class TestSlugifyReturnType:
    """Test that slugify returns the correct type."""

    def test_returns_string(self):
        """slugify should always return a string."""
        result = slugify('test')
        assert isinstance(result, str)

    def test_returns_string_for_empty_input(self):
        """slugify should return string even for empty input."""
        result = slugify('')
        assert isinstance(result, str)

    def test_returns_string_for_special_chars_only(self):
        """slugify should return string even when input is only special chars."""
        result = slugify('@#$%')
        assert isinstance(result, str)
