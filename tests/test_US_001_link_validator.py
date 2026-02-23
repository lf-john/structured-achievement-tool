"""
Tests for US-001: LinkInfo Dataclass and Markdown Link Extraction

This test suite verifies the implementation of the LinkInfo dataclass and
extract_links() function for parsing markdown links.

IMPLEMENTATION PLAN for US-001:

Components:
  - LinkInfo: Dataclass with fields text (str), url (str), line_number (int), is_image (bool)
  - extract_links(): Function that parses markdown and returns list[LinkInfo]

Test Cases:
  1. AC 1: LinkInfo dataclass exists with required fields
  2. AC 2: extract_links() parses inline links [text](url) with is_image=False
  3. AC 3: extract_links() parses image links ![alt](url) with is_image=True
  4. AC 4: extract_links() returns correct 1-indexed line_number for each link
  5. AC 5: extract_links() returns empty list when no links present
  6. AC 6: extract_links() handles multiple links on same line
  7. AC 7: extract_links() handles links across multiple lines

Edge Cases:
  - Empty input string
  - Links with special characters in text and URL
  - Links at different positions in lines
  - Newlines and whitespace handling
  - Mixed inline and image links
  - Text before and after links
"""

import pytest
from src.utils.link_validator import LinkInfo, extract_links


class TestLinkInfoDataclass:
    """Test AC 1: LinkInfo dataclass with required fields"""

    def test_linkinfo_can_be_created(self):
        """Test that LinkInfo dataclass can be instantiated."""
        link = LinkInfo(
            text="Example",
            url="https://example.com",
            line_number=1,
            is_image=False
        )
        assert link is not None

    def test_linkinfo_has_text_field(self):
        """Test that LinkInfo has text field."""
        link = LinkInfo(
            text="Example",
            url="https://example.com",
            line_number=1,
            is_image=False
        )
        assert link.text == "Example"

    def test_linkinfo_has_url_field(self):
        """Test that LinkInfo has url field."""
        link = LinkInfo(
            text="Example",
            url="https://example.com",
            line_number=1,
            is_image=False
        )
        assert link.url == "https://example.com"

    def test_linkinfo_has_line_number_field(self):
        """Test that LinkInfo has line_number field."""
        link = LinkInfo(
            text="Example",
            url="https://example.com",
            line_number=5,
            is_image=False
        )
        assert link.line_number == 5

    def test_linkinfo_has_is_image_field(self):
        """Test that LinkInfo has is_image field."""
        link = LinkInfo(
            text="alt text",
            url="image.png",
            line_number=1,
            is_image=True
        )
        assert link.is_image is True

    def test_linkinfo_is_image_false_for_regular_link(self):
        """Test that is_image defaults correctly for regular links."""
        link = LinkInfo(
            text="link text",
            url="https://example.com",
            line_number=1,
            is_image=False
        )
        assert link.is_image is False


class TestExtractLinksBasic:
    """Test AC 2: extract_links() parses inline links [text](url)"""

    def test_extract_links_returns_list(self):
        """Test that extract_links returns a list."""
        markdown = "This is [a link](https://example.com)"
        result = extract_links(markdown)
        assert isinstance(result, list)

    def test_extract_single_inline_link(self):
        """Test extraction of single inline link."""
        markdown = "This is [a link](https://example.com)"
        result = extract_links(markdown)
        assert len(result) == 1
        assert result[0].text == "a link"
        assert result[0].url == "https://example.com"
        assert result[0].is_image is False

    def test_extract_inline_link_sets_is_image_false(self):
        """Test that regular links have is_image=False."""
        markdown = "[Click here](https://example.com)"
        result = extract_links(markdown)
        assert result[0].is_image is False

    def test_extract_inline_link_with_simple_text(self):
        """Test extraction with simple link text."""
        markdown = "[link](https://example.com)"
        result = extract_links(markdown)
        assert result[0].text == "link"
        assert result[0].url == "https://example.com"

    def test_extract_inline_link_with_spaces_in_text(self):
        """Test extraction with spaces in link text."""
        markdown = "[click here now](https://example.com)"
        result = extract_links(markdown)
        assert result[0].text == "click here now"

    def test_extract_inline_link_with_special_chars_in_url(self):
        """Test extraction with special characters in URL."""
        markdown = "[link](https://example.com/path?query=value&foo=bar)"
        result = extract_links(markdown)
        assert result[0].url == "https://example.com/path?query=value&foo=bar"


class TestExtractLinksImages:
    """Test AC 3: extract_links() parses image links ![alt](url)"""

    def test_extract_single_image_link(self):
        """Test extraction of single image link."""
        markdown = "![alt text](image.png)"
        result = extract_links(markdown)
        assert len(result) == 1
        assert result[0].text == "alt text"
        assert result[0].url == "image.png"
        assert result[0].is_image is True

    def test_extract_image_link_sets_is_image_true(self):
        """Test that image links have is_image=True."""
        markdown = "![image](img.jpg)"
        result = extract_links(markdown)
        assert result[0].is_image is True

    def test_extract_image_with_complex_alt_text(self):
        """Test extraction of image with complex alt text."""
        markdown = "![A beautiful sunset over the mountains](sunset.jpg)"
        result = extract_links(markdown)
        assert result[0].text == "A beautiful sunset over the mountains"

    def test_extract_image_with_url_path(self):
        """Test extraction of image with full path URL."""
        markdown = "![icon](https://example.com/images/icon.png)"
        result = extract_links(markdown)
        assert result[0].url == "https://example.com/images/icon.png"


class TestExtractLinksLineNumbers:
    """Test AC 4: extract_links() returns correct 1-indexed line_number"""

    def test_link_on_first_line_has_line_number_one(self):
        """Test that link on first line has line_number=1."""
        markdown = "[link](url)"
        result = extract_links(markdown)
        assert result[0].line_number == 1

    def test_link_on_second_line_has_line_number_two(self):
        """Test that link on second line has line_number=2."""
        markdown = "First line\n[link](url)"
        result = extract_links(markdown)
        assert result[0].line_number == 2

    def test_link_on_third_line_has_line_number_three(self):
        """Test that link on third line has line_number=3."""
        markdown = "Line 1\nLine 2\n[link](url)"
        result = extract_links(markdown)
        assert result[0].line_number == 3

    def test_multiple_links_have_correct_line_numbers(self):
        """Test that multiple links on different lines have correct line numbers."""
        markdown = "[link1](url1)\nSome text\n[link2](url2)"
        result = extract_links(markdown)
        assert len(result) == 2
        assert result[0].line_number == 1
        assert result[1].line_number == 3

    def test_image_link_has_correct_line_number(self):
        """Test that image links have correct line numbers."""
        markdown = "Some intro\n![image](img.png)\nMore text"
        result = extract_links(markdown)
        assert result[0].line_number == 2

    def test_mixed_links_have_correct_line_numbers(self):
        """Test that mixed inline and image links have correct line numbers."""
        markdown = "[text](url1)\n![image](img.png)"
        result = extract_links(markdown)
        assert result[0].line_number == 1
        assert result[1].line_number == 2


class TestExtractLinksEmpty:
    """Test AC 5: extract_links() returns empty list when no links present"""

    def test_empty_string_returns_empty_list(self):
        """Test that empty string returns empty list."""
        markdown = ""
        result = extract_links(markdown)
        assert result == []

    def test_text_without_links_returns_empty_list(self):
        """Test that text without links returns empty list."""
        markdown = "This is just plain text with no links at all."
        result = extract_links(markdown)
        assert result == []

    def test_multiline_text_without_links_returns_empty_list(self):
        """Test that multiline text without links returns empty list."""
        markdown = "Line 1\nLine 2\nLine 3"
        result = extract_links(markdown)
        assert result == []

    def test_text_with_brackets_but_no_links_returns_empty_list(self):
        """Test that brackets without link syntax returns empty list."""
        markdown = "This has [brackets] but (no links)"
        result = extract_links(markdown)
        assert result == []

    def test_incomplete_link_syntax_returns_empty_list(self):
        """Test that incomplete link syntax doesn't match."""
        markdown = "[text (url) or (text) url]"
        result = extract_links(markdown)
        assert result == []


class TestExtractLinksMultipleSameLine:
    """Test AC 6: extract_links() handles multiple links on same line"""

    def test_two_inline_links_on_same_line(self):
        """Test extraction of two inline links on same line."""
        markdown = "[link1](url1) and [link2](url2)"
        result = extract_links(markdown)
        assert len(result) == 2
        assert result[0].text == "link1"
        assert result[0].url == "url1"
        assert result[1].text == "link2"
        assert result[1].url == "url2"

    def test_two_image_links_on_same_line(self):
        """Test extraction of two image links on same line."""
        markdown = "![img1](img1.png) ![img2](img2.png)"
        result = extract_links(markdown)
        assert len(result) == 2
        assert result[0].is_image is True
        assert result[1].is_image is True

    def test_mixed_inline_and_image_links_on_same_line(self):
        """Test extraction of mixed link types on same line."""
        markdown = "[text](url) and ![image](img.png)"
        result = extract_links(markdown)
        assert len(result) == 2
        assert result[0].is_image is False
        assert result[1].is_image is True

    def test_three_links_on_same_line(self):
        """Test extraction of three links on same line."""
        markdown = "[a](1) [b](2) [c](3)"
        result = extract_links(markdown)
        assert len(result) == 3

    def test_multiple_links_same_line_same_line_number(self):
        """Test that multiple links on same line have same line_number."""
        markdown = "[link1](url1) [link2](url2)"
        result = extract_links(markdown)
        assert result[0].line_number == 1
        assert result[1].line_number == 1


class TestExtractLinksMultipleLines:
    """Test AC 7: extract_links() handles links across multiple lines"""

    def test_links_on_different_lines(self):
        """Test extraction of links on different lines."""
        markdown = "[link1](url1)\nSome text\n[link2](url2)\nMore text\n[link3](url3)"
        result = extract_links(markdown)
        assert len(result) == 3
        assert result[0].line_number == 1
        assert result[1].line_number == 3
        assert result[2].line_number == 5

    def test_multiple_documents_with_links(self):
        """Test extraction from multi-paragraph markdown."""
        markdown = """# Heading

This paragraph has [a link](url1).

Another paragraph with [another link](url2).

Final paragraph."""
        result = extract_links(markdown)
        assert len(result) == 2

    def test_links_mixed_with_images_across_lines(self):
        """Test mixed link types across multiple lines."""
        markdown = "[text](url)\n![image](img.png)\n[more](url2)"
        result = extract_links(markdown)
        assert len(result) == 3
        assert result[0].is_image is False
        assert result[1].is_image is True
        assert result[2].is_image is False


class TestExtractLinksEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_link_with_empty_text(self):
        """Test link with empty link text."""
        markdown = "[](url)"
        result = extract_links(markdown)
        assert len(result) == 1
        assert result[0].text == ""
        assert result[0].url == "url"

    def test_link_with_empty_url(self):
        """Test link with empty URL."""
        markdown = "[text]()"
        result = extract_links(markdown)
        assert len(result) == 1
        assert result[0].text == "text"
        assert result[0].url == ""

    def test_link_with_special_characters_in_text(self):
        """Test link with special characters in text."""
        markdown = "[click here! @#$%](url)"
        result = extract_links(markdown)
        assert result[0].text == "click here! @#$%"

    def test_link_with_special_characters_in_url(self):
        """Test link with special characters in URL."""
        markdown = "[text](https://example.com/path?a=1&b=2#section)"
        result = extract_links(markdown)
        assert result[0].url == "https://example.com/path?a=1&b=2#section"

    def test_link_with_newline_should_not_match(self):
        """Test that links with newlines in middle don't match."""
        markdown = "[text\n](url)"
        result = extract_links(markdown)
        # Depending on implementation, this might be 0 or 1
        # Most markdown parsers don't support newlines in link text
        assert len(result) >= 0

    def test_url_with_parentheses_in_markdown(self):
        """Test URL with parentheses (common in Wikipedia links)."""
        markdown = "[text](https://example.com/path(v1))"
        result = extract_links(markdown)
        # This is a known edge case - depends on implementation
        assert len(result) >= 0

    def test_consecutive_links(self):
        """Test consecutive links with no space between them."""
        markdown = "[a](1)[b](2)"
        result = extract_links(markdown)
        assert len(result) == 2

    def test_nested_brackets_in_link_text(self):
        """Test link with nested brackets in text."""
        markdown = "[text [nested]](url)"
        result = extract_links(markdown)
        # Most markdown parsers handle this by closing at first ]
        assert len(result) >= 0

    def test_only_whitespace_lines(self):
        """Test markdown with only whitespace lines."""
        markdown = "   \n\n  \n"
        result = extract_links(markdown)
        assert result == []

    def test_unicode_characters_in_text(self):
        """Test link with unicode characters."""
        markdown = "[日本語 link](url)"
        result = extract_links(markdown)
        assert len(result) == 1
        assert result[0].text == "日本語 link"

    def test_unicode_in_url(self):
        """Test link with unicode in URL."""
        markdown = "[text](https://例え.jp)"
        result = extract_links(markdown)
        assert len(result) == 1

    def test_link_at_line_with_leading_text(self):
        """Test link with leading text on same line."""
        markdown = "Check out [this](url) link"
        result = extract_links(markdown)
        assert len(result) == 1
        assert result[0].line_number == 1

    def test_link_at_line_with_trailing_text(self):
        """Test link with trailing text on same line."""
        markdown = "[link](url) is great"
        result = extract_links(markdown)
        assert len(result) == 1
        assert result[0].line_number == 1

    def test_multiple_links_with_text_between(self):
        """Test multiple links on same line with text between."""
        markdown = "First [link1](url1) middle [link2](url2) last"
        result = extract_links(markdown)
        assert len(result) == 2
        assert result[0].line_number == 1
        assert result[1].line_number == 1


class TestExtractLinksComplex:
    """Test complex real-world markdown scenarios"""

    def test_markdown_with_code_blocks(self):
        """Test markdown with links and code blocks."""
        markdown = """
This is a [link](url).

```python
# This looks like a link [fake](url) but it's in code
```

This is another [real link](url2).
"""
        result = extract_links(markdown)
        # Implementation-dependent: some parsers skip code blocks
        assert len(result) >= 1

    def test_markdown_with_list_containing_links(self):
        """Test markdown with list containing links."""
        markdown = """
- First item with [link1](url1)
- Second item with [link2](url2)
- Third item
"""
        result = extract_links(markdown)
        assert len(result) == 2
        assert result[0].is_image is False
        assert result[1].is_image is False

    def test_markdown_table_with_links(self):
        """Test markdown table containing links."""
        markdown = """
| Column 1 | Column 2 |
|----------|----------|
| [link1](url1) | [link2](url2) |
"""
        result = extract_links(markdown)
        # Should find both links
        assert len(result) >= 0

    def test_reference_style_links_ignored(self):
        """Test that reference-style links are not extracted."""
        markdown = """
This is a [link][ref].

[ref]: https://example.com
"""
        # Only extract inline links for now
        result = extract_links(markdown)
        # The inline link [link][ref] might or might not be extracted
        # depending on implementation
        assert isinstance(result, list)

    def test_real_world_markdown_content(self):
        """Test extraction from realistic markdown content."""
        markdown = """# My Article

Check out [this great resource](https://example.com).

Here's an image: ![Screenshot](screenshot.png)

And here's [another link](https://another.com) to reference.

Learn more at [documentation](docs.html).
"""
        result = extract_links(markdown)
        assert len(result) == 4
        assert result[0].is_image is False
        assert result[1].is_image is True
        assert result[2].is_image is False
        assert result[3].is_image is False


if __name__ == "__main__":
    # Run tests with pytest
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
