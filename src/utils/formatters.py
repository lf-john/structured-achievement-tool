def format_duration(seconds: float) -> str:
    """
    Converts a duration in seconds to a human-readable string.

    Args:
        seconds: The duration in seconds.

    Returns:
        A formatted string representing the duration.
    """
    if seconds <= 0:
        return '0s'

    if seconds < 60:
        # If original seconds is less than 60, display in seconds, rounded.
        s = int(round(seconds))
        return f"{s}s"
    
    elif seconds < 3600:
        # If original seconds is less than 3600 but 60 or more, display in minutes and seconds.
        total_s = int(round(seconds))
        m, s_rem = divmod(total_s, 60)
        return f"{m}m {s_rem}s"

    else: # seconds is 3600 or more
        # Display in hours, minutes, and seconds.
        total_s = int(round(seconds))
        h, rem = divmod(total_s, 3600)
        m, s_rem = divmod(rem, 60)
        return f"{h}h {m}m {s_rem}s"
