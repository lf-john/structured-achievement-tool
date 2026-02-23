"""Text truncation utility with word boundary support."""

_UNSET = object()


def truncate(text: str, max_length: int, suffix=_UNSET) -> str:
    """Truncate text to max_length, breaking at word boundaries.

    Args:
        text: The text to truncate.
        max_length: Maximum length of the result (including suffix).
        suffix: String to append to truncated text. Defaults to '...'.

    Returns:
        Original text if within max_length, otherwise truncated text with suffix.

    Raises:
        TypeError: If text is not a string or max_length is not an integer.
        ValueError: If max_length is negative, or if an explicitly-provided
                    suffix is longer than max_length.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(max_length, int):
        raise TypeError("max_length must be an integer")

    # Detect whether suffix was explicitly passed
    suffix_explicit = suffix is not _UNSET
    if not suffix_explicit:
        suffix = "..."

    # Validate negative max_length
    if max_length < 0:
        raise ValueError("max_length must be non-negative")

    # Validate explicitly-passed suffix fits within max_length
    if suffix_explicit and max_length < len(suffix):
        raise ValueError(
            f"max_length ({max_length}) must be >= len(suffix) ({len(suffix)})"
        )

    # Text within max_length: return unchanged
    if len(text) <= max_length:
        return text

    # Effective suffix: fall back to "" if the default suffix doesn't fit
    effective_suffix = suffix if max_length >= len(suffix) else ""

    if max_length == 0:
        return ""

    available = max_length - len(effective_suffix)

    if available <= 0:
        return effective_suffix

    # Truncate to available characters
    truncated_text = text[:available]

    # Find last word boundary (space character)
    last_space = truncated_text.rfind(" ")

    if last_space > 0:
        result = text[:last_space].rstrip() + effective_suffix
    else:
        # No usable word boundary: hard-truncate at character boundary
        result = truncated_text + effective_suffix

    return result
