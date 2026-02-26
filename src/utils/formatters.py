
def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0s"

    if seconds < 60:  # Check original 'seconds' for the threshold
        rounded_seconds = round(seconds)
        return f"{rounded_seconds}s"
    elif seconds < 3600:
        rounded_seconds_total = round(seconds)  # Round for calculation
        minutes = int(rounded_seconds_total // 60)
        remaining_seconds = int(rounded_seconds_total % 60)
        return f"{minutes}m {remaining_seconds}s"
    else:
        rounded_seconds_total = round(seconds)  # Round for calculation
        hours = int(rounded_seconds_total // 3600)
        minutes = int((rounded_seconds_total % 3600) // 60)
        remaining_seconds = int(rounded_seconds_total % 60)
        return f"{hours}h {minutes}m {remaining_seconds}s"
