from src.utils.formatters import format_duration


def test_format_duration_less_than_60_seconds():
    assert format_duration(45) == "45s"
    assert format_duration(1) == "1s"
    assert format_duration(59.9) == "1m 0s"


def test_format_duration_less_than_3600_seconds():
    assert format_duration(60) == "1m 0s"
    assert format_duration(90) == "1m 30s"
    assert format_duration(3599) == "59m 59s"
    assert format_duration(12.5 * 60) == "12m 30s"


def test_format_duration_3600_plus_seconds():
    assert format_duration(3600) == "1h 0m 0s"
    assert format_duration(3601) == "1h 0m 1s"
    assert format_duration(7265) == "2h 1m 5s"
    assert format_duration(86399) == "23h 59m 59s"


def test_format_duration_zero_and_negative_inputs():
    assert format_duration(0) == "0s"
    assert format_duration(-10) == "-10s"
    assert format_duration(-0.001) == "-0s"
