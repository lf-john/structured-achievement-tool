import re
from dataclasses import dataclass


@dataclass
class LinkInfo:
    text: str
    url: str
    line_number: int
    is_image: bool


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
