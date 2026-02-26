
def format_duration(seconds: float) -> str:
    if seconds == 0:
        return "0s"

    is_negative = seconds < 0
    if is_negative:
        seconds = abs(seconds)

    # Use int(x + 0.5) for consistent rounding up
    total_seconds = int(seconds + 0.5)

    if total_seconds < 60:
        result = f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        remaining_seconds = total_seconds % 60
        result = f"{minutes}m {remaining_seconds}s"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        remaining_seconds = total_seconds % 60
        result = f"{hours}h {minutes}m {remaining_seconds}s"

    if is_negative:
        return f"-{result}"
    return result
