from src.utils.formatters import format_duration


def test_format_duration_less_than_60_seconds():
    assert format_duration(45) == "45s"
    assert format_duration(1) == "1s"

def test_format_duration_zero_seconds():
    assert format_duration(0) == "0s"
    assert format_duration(0.0) == "0s"

def test_format_duration_between_60_and_3599_seconds():
    assert format_duration(75) == "1m 15s"
    assert format_duration(1500) == "25m 0s"
    assert format_duration(59.5) == "1m 0s" # Rounds up

def test_format_duration_3600_seconds_or_more():
    assert format_duration(3600) == "1h 0m 0s"
    assert format_duration(8145.7) == "2h 15m 46s" # Rounds up 8145.7 + 0.5 = 8146.2 -> 8146 (2h 15m 46s)
    assert format_duration(3599.5) == "1h 0m 0s" # Rounds up

def test_format_duration_negative_seconds():
    assert format_duration(-45) == "-45s"
    assert format_duration(-75) == "-1m 15s"
    assert format_duration(-3600) == "-1h 0m 0s"
    assert format_duration(-8145.7) == "-2h 15m 46s"
    assert format_duration(-0.1) == "-0s" # Rounds to 0, then negates
    assert format_duration(-0.5) == "-1s" # Rounds to 1, then negates

def test_format_duration_rounding_edge_cases():
    assert format_duration(0.4) == "0s"
    assert format_duration(0.6) == "1s"
    assert format_duration(59.4) == "59s"
    assert format_duration(59.6) == "1m 0s"
    assert format_duration(3599.4) == "59m 59s"
    assert format_duration(3599.6) == "1h 0m 0s"
