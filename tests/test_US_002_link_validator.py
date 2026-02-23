"""
Tests for US-002: URL Validation and Malformed Link Flagging

This test suite verifies the implementation of URL validation for LinkInfo objects.
Tests cover validation of http/https URLs, relative paths, empty URLs, and various edge cases.

IMPLEMENTATION PLAN for US-002:

Components:
  - LinkValidationResult: Dataclass with fields is_valid (bool), error (str | None)
  - validate_links(): Function that takes list[LinkInfo] and returns list[LinkValidationResult]

Test Cases:
  1. AC 1: Valid HTTP/HTTPS URLs with scheme and netloc are marked as valid
  2. AC 2: HTTP/HTTPS URLs missing netloc are marked invalid with error message
  3. AC 3: Relative paths are marked as valid
  4. AC 4: Empty string URLs are marked as invalid
  5. AC 5: Unsupported schemes are handled consistently
  6. AC 6: validate_links() returns LinkValidationResult objects with is_valid and error

Edge Cases:
  - HTTP vs HTTPS URLs
  - URLs with query strings and fragments
  - Relative paths with various formats (./, ../, /)
  - Whitespace handling
  - Special characters in valid URLs
  - Multiple links validation in one call
  - Combination of valid and invalid URLs
"""

import pytest
from dataclasses import dataclass
from src.utils.link_validator import LinkInfo, validate_links, LinkValidationResult


class TestLinkValidationResultStructure:
    """Test AC 6: LinkValidationResult structure with is_valid and error fields"""

    def test_link_validation_result_has_is_valid_field(self):
        """Test that LinkValidationResult has is_valid boolean field."""
        result = LinkValidationResult(is_valid=True, error=None)
        assert hasattr(result, 'is_valid')
        assert result.is_valid is True

    def test_link_validation_result_has_error_field(self):
        """Test that LinkValidationResult has error field."""
        result = LinkValidationResult(is_valid=False, error="Invalid URL")
        assert hasattr(result, 'error')
        assert result.error == "Invalid URL"

    def test_link_validation_result_valid_with_no_error(self):
        """Test LinkValidationResult with valid=True and error=None."""
        result = LinkValidationResult(is_valid=True, error=None)
        assert result.is_valid is True
        assert result.error is None

    def test_link_validation_result_invalid_with_error_message(self):
        """Test LinkValidationResult with valid=False and error message."""
        result = LinkValidationResult(is_valid=False, error="URL missing netloc")
        assert result.is_valid is False
        assert result.error == "URL missing netloc"


class TestValidateLinksFunction:
    """Test that validate_links() function exists and returns proper structure"""

    def test_validate_links_returns_list(self):
        """Test that validate_links returns a list."""
        link = LinkInfo(text="test", url="https://example.com", line_number=1, is_image=False)
        result = validate_links([link])
        assert isinstance(result, list)

    def test_validate_links_returns_correct_length(self):
        """Test that validate_links returns same number of results as input links."""
        links = [
            LinkInfo(text="link1", url="https://example.com", line_number=1, is_image=False),
            LinkInfo(text="link2", url="https://test.com", line_number=2, is_image=False),
            LinkInfo(text="link3", url="../relative.html", line_number=3, is_image=False),
        ]
        results = validate_links(links)
        assert len(results) == 3

    def test_validate_links_accepts_empty_list(self):
        """Test that validate_links handles empty link list."""
        results = validate_links([])
        assert results == []

    def test_validate_links_result_items_are_link_validation_results(self):
        """Test that results are LinkValidationResult objects."""
        link = LinkInfo(text="test", url="https://example.com", line_number=1, is_image=False)
        results = validate_links([link])
        assert len(results) > 0
        assert hasattr(results[0], 'is_valid')
        assert hasattr(results[0], 'error')


class TestHTTPSURLValidation:
    """Test AC 1: Valid HTTP/HTTPS URLs with scheme and netloc are marked as valid"""

    def test_valid_https_url_with_scheme_and_netloc(self):
        """Test that valid HTTPS URL with scheme and netloc is marked valid."""
        link = LinkInfo(text="link", url="https://example.com", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True
        assert results[0].error is None

    def test_valid_https_url_with_path(self):
        """Test that valid HTTPS URL with path is marked valid."""
        link = LinkInfo(text="link", url="https://example.com/path/to/page", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_valid_https_url_with_query_string(self):
        """Test that valid HTTPS URL with query string is marked valid."""
        link = LinkInfo(text="link", url="https://example.com/search?q=test&sort=asc", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_valid_https_url_with_fragment(self):
        """Test that valid HTTPS URL with fragment is marked valid."""
        link = LinkInfo(text="link", url="https://example.com/page#section", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_valid_https_url_with_port(self):
        """Test that valid HTTPS URL with port is marked valid."""
        link = LinkInfo(text="link", url="https://example.com:8443", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_valid_https_url_with_subdomain(self):
        """Test that valid HTTPS URL with subdomain is marked valid."""
        link = LinkInfo(text="link", url="https://api.example.com", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_valid_http_url_with_scheme_and_netloc(self):
        """Test that valid HTTP URL with scheme and netloc is marked valid."""
        link = LinkInfo(text="link", url="http://example.com", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True
        assert results[0].error is None

    def test_valid_http_url_with_path(self):
        """Test that valid HTTP URL with path is marked valid."""
        link = LinkInfo(text="link", url="http://example.com/path", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_valid_http_url_with_query_and_fragment(self):
        """Test that valid HTTP URL with query and fragment is marked valid."""
        link = LinkInfo(text="link", url="http://example.com/page?id=1#top", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True


class TestInvalidHTTPSURLValidation:
    """Test AC 2: HTTP/HTTPS URLs missing netloc are marked invalid with error message"""

    def test_https_url_missing_netloc(self):
        """Test that HTTPS URL missing netloc (empty host) is marked invalid."""
        link = LinkInfo(text="link", url="https://", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is False
        assert results[0].error is not None
        assert isinstance(results[0].error, str)

    def test_https_url_missing_netloc_with_path(self):
        """Test that HTTPS URL with scheme but no netloc and path is invalid."""
        link = LinkInfo(text="link", url="https:///path", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is False
        assert results[0].error is not None

    def test_http_url_missing_netloc(self):
        """Test that HTTP URL missing netloc is marked invalid."""
        link = LinkInfo(text="link", url="http://", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is False
        assert results[0].error is not None

    def test_http_url_missing_netloc_with_path(self):
        """Test that HTTP URL with path but no netloc is invalid."""
        link = LinkInfo(text="link", url="http:///path/to/resource", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is False
        assert results[0].error is not None

    def test_malformed_https_url_error_message_descriptive(self):
        """Test that error message for malformed URL is descriptive."""
        link = LinkInfo(text="link", url="https://", line_number=1, is_image=False)
        results = validate_links([link])
        error = results[0].error
        assert error is not None
        assert len(error) > 0
        # Should mention something about missing host/netloc
        assert any(word in error.lower() for word in ['host', 'netloc', 'domain', 'empty', 'missing'])


class TestRelativePathValidation:
    """Test AC 3: Relative paths are marked as valid"""

    def test_relative_path_with_dot_slash(self):
        """Test that relative path with ./ is marked valid."""
        link = LinkInfo(text="link", url="./images/photo.jpg", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True
        assert results[0].error is None

    def test_relative_path_with_dot_dot_slash(self):
        """Test that relative path with ../ is marked valid."""
        link = LinkInfo(text="link", url="../styles/main.css", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_relative_path_with_leading_slash(self):
        """Test that absolute path (root-relative) is marked valid."""
        link = LinkInfo(text="link", url="/assets/img.jpg", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_relative_path_simple_filename(self):
        """Test that simple relative filename is marked valid."""
        link = LinkInfo(text="link", url="document.pdf", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_relative_path_with_multiple_levels(self):
        """Test that relative path with multiple directory levels is valid."""
        link = LinkInfo(text="link", url="../../parent/sibling/file.html", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_relative_path_with_special_characters(self):
        """Test that relative path with dashes, underscores is valid."""
        link = LinkInfo(text="link", url="./my-folder/my_file-v2.html", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_relative_path_with_query_string(self):
        """Test that relative path with query string is valid."""
        link = LinkInfo(text="link", url="./page.html?id=123", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_relative_path_with_fragment(self):
        """Test that relative path with fragment is valid."""
        link = LinkInfo(text="link", url="./page.html#section", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True


class TestEmptyURLValidation:
    """Test AC 4: Empty string URLs are marked as invalid"""

    def test_empty_string_url_is_invalid(self):
        """Test that empty string URL is marked invalid."""
        link = LinkInfo(text="link", url="", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is False
        assert results[0].error is not None

    def test_whitespace_only_url_is_invalid(self):
        """Test that whitespace-only URL is marked invalid."""
        link = LinkInfo(text="link", url="   ", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is False

    def test_empty_url_has_error_message(self):
        """Test that empty URL has descriptive error message."""
        link = LinkInfo(text="link", url="", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].error is not None
        assert len(results[0].error) > 0


class TestUnsupportedSchemeValidation:
    """Test AC 5: Unsupported schemes are handled consistently"""

    def test_ftp_scheme_handled(self):
        """Test that FTP scheme URLs are handled (valid or invalid, documented)."""
        link = LinkInfo(text="link", url="ftp://example.com/file.zip", line_number=1, is_image=False)
        results = validate_links([link])
        # Implementation should document whether this is valid or invalid
        # For now, test that it returns a valid LinkValidationResult
        assert hasattr(results[0], 'is_valid')
        assert isinstance(results[0].is_valid, bool)
        assert results[0].error is None or isinstance(results[0].error, str)

    def test_file_scheme_handled(self):
        """Test that file:// scheme URLs are handled."""
        link = LinkInfo(text="link", url="file:///path/to/file", line_number=1, is_image=False)
        results = validate_links([link])
        assert hasattr(results[0], 'is_valid')
        assert isinstance(results[0].is_valid, bool)

    def test_mailto_scheme_handled(self):
        """Test that mailto: scheme is handled."""
        link = LinkInfo(text="link", url="mailto:user@example.com", line_number=1, is_image=False)
        results = validate_links([link])
        assert hasattr(results[0], 'is_valid')
        assert isinstance(results[0].is_valid, bool)

    def test_javascript_scheme_handled(self):
        """Test that javascript: scheme is handled."""
        link = LinkInfo(text="link", url="javascript:void(0)", line_number=1, is_image=False)
        results = validate_links([link])
        assert hasattr(results[0], 'is_valid')
        assert isinstance(results[0].is_valid, bool)


class TestMultipleLinkValidation:
    """Test validate_links() with multiple links"""

    def test_validate_multiple_mixed_valid_links(self):
        """Test validation of multiple valid links."""
        links = [
            LinkInfo(text="https", url="https://example.com", line_number=1, is_image=False),
            LinkInfo(text="http", url="http://example.com", line_number=2, is_image=False),
            LinkInfo(text="relative", url="./file.html", line_number=3, is_image=False),
            LinkInfo(text="absolute", url="/assets/image.png", line_number=4, is_image=False),
        ]
        results = validate_links(links)
        assert len(results) == 4
        assert all(r.is_valid is True for r in results)
        assert all(r.error is None for r in results)

    def test_validate_multiple_with_invalid_links(self):
        """Test validation of mix of valid and invalid links."""
        links = [
            LinkInfo(text="valid", url="https://example.com", line_number=1, is_image=False),
            LinkInfo(text="invalid1", url="https://", line_number=2, is_image=False),
            LinkInfo(text="valid2", url="./relative.html", line_number=3, is_image=False),
            LinkInfo(text="invalid2", url="", line_number=4, is_image=False),
        ]
        results = validate_links(links)
        assert len(results) == 4
        assert results[0].is_valid is True
        assert results[1].is_valid is False
        assert results[2].is_valid is True
        assert results[3].is_valid is False

    def test_validate_all_invalid_links(self):
        """Test validation when all links are invalid."""
        links = [
            LinkInfo(text="empty", url="", line_number=1, is_image=False),
            LinkInfo(text="malformed", url="https://", line_number=2, is_image=False),
            LinkInfo(text="whitespace", url="   ", line_number=3, is_image=False),
        ]
        results = validate_links(links)
        assert all(r.is_valid is False for r in results)
        assert all(r.error is not None for r in results)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_url_with_special_characters_valid(self):
        """Test URL with valid special characters in path."""
        link = LinkInfo(text="link", url="https://example.com/path-with_special.chars", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_url_with_unicode_valid(self):
        """Test URL with unicode characters."""
        link = LinkInfo(text="link", url="https://例え.jp/パス", line_number=1, is_image=False)
        results = validate_links([link])
        # Unicode URLs should be handled (valid or invalid, but no crash)
        assert hasattr(results[0], 'is_valid')

    def test_url_with_long_path(self):
        """Test URL with very long path."""
        long_path = "https://example.com/" + "very/" * 50 + "long.html"
        link = LinkInfo(text="link", url=long_path, line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_url_with_numeric_domain(self):
        """Test URL with numeric IP-like domain."""
        link = LinkInfo(text="link", url="https://192.168.1.1", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_url_with_localhost(self):
        """Test localhost URL."""
        link = LinkInfo(text="link", url="https://localhost:3000", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_image_link_validation(self):
        """Test that image links are validated the same way."""
        link = LinkInfo(text="alt", url="https://example.com/image.png", line_number=1, is_image=True)
        results = validate_links([link])
        assert results[0].is_valid is True

    def test_invalid_relative_path_not_created(self):
        """Test that invalid (non-existent) relative paths are still marked valid."""
        # Relative paths are valid regardless of whether they exist
        link = LinkInfo(text="link", url="./nonexistent/path/to/nowhere.html", line_number=1, is_image=False)
        results = validate_links([link])
        assert results[0].is_valid is True


class TestErrorMessages:
    """Test that error messages are descriptive and helpful"""

    def test_empty_url_error_message_descriptive(self):
        """Test error message for empty URL."""
        link = LinkInfo(text="link", url="", line_number=1, is_image=False)
        results = validate_links([link])
        error = results[0].error
        assert error is not None
        # Error should be clear about the problem
        assert any(word in error.lower() for word in ['empty', 'blank', 'url', 'required'])

    def test_malformed_https_error_is_consistent(self):
        """Test that malformed https:// error is consistent across calls."""
        link1 = LinkInfo(text="link", url="https://", line_number=1, is_image=False)
        link2 = LinkInfo(text="link", url="https://", line_number=2, is_image=False)
        results1 = validate_links([link1])
        results2 = validate_links([link2])
        # Errors for same malformed URL should be the same
        assert results1[0].error == results2[0].error


if __name__ == "__main__":
    # Run tests with pytest
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
