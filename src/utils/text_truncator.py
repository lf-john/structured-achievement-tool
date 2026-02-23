def truncate(text: str, max_length: int, suffix: str = '...') -> str:
    """Truncate text to max_length characters, breaking at word boundaries.

    Args:
        text: The text to truncate.
        max_length: Maximum length of the result including the suffix.
        suffix: String appended after truncation. Defaults to '...'.

    Returns:
        The original text if it fits within max_length, otherwise the text
        truncated at the last word boundary (space) with suffix appended.

    Raises:
        ValueError: If max_length < len(suffix).
    """
    if max_length < len(suffix):
        raise ValueError(
            f"max_length ({max_length}) must be >= len(suffix) ({len(suffix)})"
        )

    if len(text) <= max_length:
        return text

    available = max_length - len(suffix)

    if available == 0:
        return suffix

    # If the character immediately after the available region is a space,
    # the word ends exactly at the boundary.
    if text[available] == ' ':
        return text[:available].rstrip(' ') + suffix

    # Find the last space within the available region (only ' ', not tabs/newlines).
    truncated = text[:available]
    last_space = truncated.rfind(' ')

    if last_space >= 0:
        # If the space is at the very end of available region, keep trailing
        # spaces as part of the word portion (multiple-space boundary).
        if last_space == available - 1:
            return text[:available] + suffix
        return text[:last_space].rstrip(' ') + suffix

    # No word boundary found; hard-truncate at exactly available chars.
    return text[:available] + suffix
