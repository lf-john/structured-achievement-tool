import re
import unicodedata


def slugify(text: str) -> str:
    """Convert arbitrary text to a URL-safe slug."""
    # Normalize unicode to closest ASCII equivalent
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    # Lowercase
    text = text.lower()
    # Replace underscores with hyphens
    text = text.replace('_', '-')
    # Replace non-alphanumeric, non-hyphen, non-whitespace with space
    text = re.sub(r'[^a-z0-9\s-]', ' ', text)
    # Collapse whitespace sequences into a single hyphen
    text = re.sub(r'\s+', '-', text)
    # Collapse consecutive hyphens
    text = re.sub(r'-+', '-', text)
    # Strip leading/trailing hyphens
    text = text.strip('-')
    return text
