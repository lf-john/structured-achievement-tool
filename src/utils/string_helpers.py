import re
import unicodedata


def slugify(text: str) -> str:
    """Convert arbitrary text to a URL-safe slug."""
    # Normalize unicode: decompose accented chars, then encode to ASCII dropping non-ASCII
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    # Lowercase
    text = text.lower()
    # Replace non-alphanumeric characters (except hyphens) with hyphens
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # Collapse consecutive hyphens
    text = re.sub(r'-+', '-', text)
    # Strip leading/trailing hyphens
    text = text.strip('-')
    return text
