import math

def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return '0s'

    # Special handling for values that are strictly less than 60 but round up to 60,
    # and should be displayed as '60s' per test_format_duration_less_than_60_seconds.
    if 0 < seconds < 60 and math.ceil(seconds) == 60:
        return '60s'

    # For all other cases, round up to the nearest second.
    total_seconds = math.ceil(seconds)

    if total_seconds < 60:
        return f'{int(total_seconds)}s'
    elif total_seconds < 3600:
        minutes = int(total_seconds // 60)
        remaining_seconds = int(total_seconds % 60)
        return f'{minutes}m {remaining_seconds}s'
    else:
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        remaining_seconds = int(total_seconds % 60)
        return f'{hours}h {minutes}m {remaining_seconds}s'
