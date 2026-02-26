import math

def format_duration(seconds: float) -> str:
    """
    Formats a duration in seconds into a human-readable string (e.g., "1h 2m 3s").

    Args:
        seconds: The duration in seconds (can be a float).

    Returns:
        A formatted string representing the duration.
    """
    if seconds == 0:
        return "0s"

    sign = "-" if seconds < 0 else ""
    # Explicitly implement round half up for the absolute number of seconds
    abs_seconds = int(abs(seconds) + 0.5)

    if abs_seconds == 0:
        return sign + "0s"

    hours = abs_seconds // 3600
    minutes = (abs_seconds % 3600) // 60
    remaining_seconds = abs_seconds % 60

    parts = []

    if hours > 0:
        parts.append(f"{hours}h")

    if hours > 0 or minutes > 0:
        parts.append(f"{minutes}m")

    # Always include seconds if hours or minutes are present, or if it's only seconds (e.g., 45s)
    if hours > 0 or minutes > 0 or remaining_seconds > 0 or len(parts) == 0:
        parts.append(f"{remaining_seconds}s")

    return sign + " ".join(parts)
