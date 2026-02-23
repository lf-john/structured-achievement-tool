import re

_UNITS = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
_TOKEN_RE = re.compile(r'(\d+)([dhms])')


def parse_duration(s: str) -> int:
    """Parse a human-readable duration string into total seconds.

    Supports units: d (days), h (hours), m (minutes), s (seconds).
    Raises ValueError for any invalid input.
    """
    if not s or not s.strip():
        raise ValueError(f"Invalid duration string: {s!r}")

    stripped = s.strip()
    tokens = _TOKEN_RE.findall(stripped)
    if not tokens:
        raise ValueError(f"No valid duration tokens found in: {s!r}")

    # Verify the entire stripped string is consumed by tokens + whitespace
    consumed = _TOKEN_RE.sub('', stripped)
    if consumed.strip():
        raise ValueError(f"Unparseable text in duration string: {s!r}")

    seen_units = set()
    total = 0
    for quantity, unit in tokens:
        if unit in seen_units:
            raise ValueError(f"Duplicate unit '{unit}' in duration string: {s!r}")
        seen_units.add(unit)
        total += int(quantity) * _UNITS[unit]

    return total
