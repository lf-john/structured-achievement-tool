import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class LinkInfo:
    text: str
    url: str
    line_number: int
    is_image: bool


@dataclass
class LinkValidationResult:
    is_valid: bool
    error: str | None


def extract_links(markdown_text: str) -> list[LinkInfo]:
    """Parse markdown text and return all inline and image links as LinkInfo objects."""
    pattern = re.compile(r'(!?)\[([^\]\n]*)\]\(([^)\n]*)\)')
    results = []
    for line_number, line in enumerate(markdown_text.split('\n'), start=1):
        for match in pattern.finditer(line):
            is_image = match.group(1) == '!'
            text = match.group(2)
            url = match.group(3)
            results.append(LinkInfo(text=text, url=url, line_number=line_number, is_image=is_image))
    return results


def validate_links(links: list[LinkInfo]) -> list[LinkValidationResult]:
    """Validate a list of LinkInfo objects and return LinkValidationResult per link.

    Validation rules:
    - Empty or whitespace-only URLs are invalid.
    - http/https URLs must have a non-empty netloc; missing netloc is invalid.
    - Relative paths (no scheme) are valid if non-empty.
    - Unsupported schemes (ftp, file, mailto, javascript, etc.) are treated as valid
      since they cannot be validated structurally by this tool.
    """
    results = []
    for link in links:
        url = link.url
        if not url or not url.strip():
            results.append(LinkValidationResult(is_valid=False, error="URL is empty"))
            continue
        parsed = urlparse(url)
        if parsed.scheme in ('http', 'https'):
            if not parsed.netloc:
                results.append(LinkValidationResult(
                    is_valid=False,
                    error=f"URL is missing host/netloc after scheme '{parsed.scheme}://'"
                ))
            else:
                results.append(LinkValidationResult(is_valid=True, error=None))
        else:
            # Relative paths and unsupported schemes are considered valid
            results.append(LinkValidationResult(is_valid=True, error=None))
    return results
