import re
import unicodedata


def slugify(text: str) -> str:
    """Convert arbitrary text to a URL-safe slug."""
    # Normalize unicode: decompose characters (e.g. é → e + combining accent)
    text = unicodedata.normalize('NFKD', text)
    # Encode to ASCII bytes, ignoring non-ASCII, then decode back
    text = text.encode('ascii', 'ignore').decode('ascii')
    # Lowercase
    text = text.lower()
    # Replace underscores, dots, and whitespace with hyphens
    text = re.sub(r'[\s_\.]+', '-', text)
    # Strip all characters that are not alphanumeric or hyphens
    text = re.sub(r'[^a-z0-9-]', '', text)
    # Collapse consecutive hyphens
    text = re.sub(r'-+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    return text
