"""
IMPLEMENTATION PLAN for US-001: DurationParser Utility

Components:
  - parse_duration(s: str) -> int: Main function that parses human-readable duration
    strings (e.g., "2h30m", "1d", "45s") and returns the total number of seconds as
    an integer. Supports units: d (days=86400s), h (hours=3600s), m (minutes=60s),
    s (seconds=1s). Raises ValueError for invalid inputs.

Test Strategy:
  1. Acceptance Criteria (13 total):
     - AC1: parse_duration('2h30m') returns 9000
     - AC2: parse_duration('1d') returns 86400
     - AC3: parse_duration('45s') returns 45
     - AC4: parse_duration('1h 15m 30s') returns 4530
     - AC5: parse_duration('90m') returns 5400
     - AC6: parse_duration('1d 2h 3m 4s') returns 93784
     - AC7: Whitespace between components is handled correctly
     - AC8: parse_duration('') raises ValueError
     - AC9: parse_duration('abc') raises ValueError
     - AC10: parse_duration('2x') raises ValueError for unknown unit
     - AC11: parse_duration('1h abc') raises ValueError for partially invalid input
     - AC12: Function returns int, not float
     - AC13: Module importable as from src.utils.duration_parser import parse_duration

  2. Edge Cases:
     - Single unit types: "1d", "1h", "1m", "1s"
     - Multiple whitespace: "1h  30m", "  1h30m", "1h30m  "
     - Zero values: "0s", "0m", "0h", "0d"
     - Large values: "365d", "1000h"
     - Invalid cases: no quantity ("h"), non-numeric quantity ("ah"),
       float quantity ("1.5h"), reversed order ("h1"), duplicate units ("1h 2h"),
       negative values ("-1h"), only whitespace ("   ")

Test Organization:
  - TestDurationParserBasic: Acceptance criterion test cases
  - TestDurationParserWhitespace: Whitespace handling
  - TestDurationParserSingleUnits: Single unit variations
  - TestDurationParserErrors: Error cases and validation
  - TestDurationParserReturnType: Type checking
  - TestDurationParserZeroValues: Zero value handling
  - TestDurationParserLargeValues: Large value handling
  - TestDurationParserImport: Module import verification
"""

import pytest
from src.utils.duration_parser import parse_duration


class TestDurationParserBasic:
    """Test basic duration parsing from acceptance criteria."""

    def test_parse_2h30m_returns_9000(self):
        """AC1: parse_duration('2h30m') returns 9000"""
        assert parse_duration('2h30m') == 9000

    def test_parse_1d_returns_86400(self):
        """AC2: parse_duration('1d') returns 86400"""
        assert parse_duration('1d') == 86400

    def test_parse_45s_returns_45(self):
        """AC3: parse_duration('45s') returns 45"""
        assert parse_duration('45s') == 45

    def test_parse_1h_15m_30s_returns_4530(self):
        """AC4: parse_duration('1h 15m 30s') returns 4530"""
        assert parse_duration('1h 15m 30s') == 4530

    def test_parse_90m_returns_5400(self):
        """AC5: parse_duration('90m') returns 5400"""
        assert parse_duration('90m') == 5400

    def test_parse_1d_2h_3m_4s_returns_93784(self):
        """AC6: parse_duration('1d 2h 3m 4s') returns 93784

        Calculation: 1d=86400, 2h=7200, 3m=180, 4s=4
        Total: 86400 + 7200 + 180 + 4 = 93784
        """
        assert parse_duration('1d 2h 3m 4s') == 93784


class TestDurationParserWhitespace:
    """Test whitespace handling (AC7)."""

    def test_whitespace_no_spaces(self):
        """No spaces between components"""
        assert parse_duration('1h30m') == 5400

    def test_whitespace_single_space(self):
        """Single space between components"""
        assert parse_duration('1h 30m') == 5400

    def test_whitespace_multiple_spaces_between(self):
        """Multiple spaces between components"""
        assert parse_duration('1h  30m') == 5400

    def test_whitespace_multiple_spaces_complex(self):
        """Multiple spaces in complex duration"""
        assert parse_duration('1h  30m   45s') == 5445

    def test_whitespace_leading(self):
        """Leading whitespace"""
        assert parse_duration('  1h30m') == 5400

    def test_whitespace_trailing(self):
        """Trailing whitespace"""
        assert parse_duration('1h30m  ') == 5400

    def test_whitespace_leading_and_trailing(self):
        """Both leading and trailing whitespace"""
        assert parse_duration('  1h30m  ') == 5400

    def test_whitespace_space_after_unit(self):
        """Space after unit before next component"""
        assert parse_duration('2h 15m') == 8100


class TestDurationParserSingleUnits:
    """Test parsing of single unit types."""

    def test_parse_single_day(self):
        """Single day"""
        assert parse_duration('1d') == 86400

    def test_parse_single_hour(self):
        """Single hour"""
        assert parse_duration('1h') == 3600

    def test_parse_single_minute(self):
        """Single minute"""
        assert parse_duration('1m') == 60

    def test_parse_single_second(self):
        """Single second"""
        assert parse_duration('1s') == 1

    def test_parse_multiple_days(self):
        """Multiple days"""
        assert parse_duration('5d') == 432000

    def test_parse_multiple_hours(self):
        """Multiple hours"""
        assert parse_duration('10h') == 36000

    def test_parse_multiple_minutes(self):
        """Multiple minutes"""
        assert parse_duration('120m') == 7200

    def test_parse_multiple_seconds(self):
        """Multiple seconds"""
        assert parse_duration('300s') == 300

    def test_parse_large_single_unit(self):
        """Large single unit value"""
        assert parse_duration('48h') == 172800


class TestDurationParserErrors:
    """Test error handling and validation."""

    def test_empty_string_raises_valueerror(self):
        """AC8: parse_duration('') raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('')

    def test_invalid_input_abc_raises_valueerror(self):
        """AC9: parse_duration('abc') raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('abc')

    def test_unknown_unit_2x_raises_valueerror(self):
        """AC10: parse_duration('2x') raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('2x')

    def test_partially_invalid_input_raises_valueerror(self):
        """AC11: parse_duration('1h abc') raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1h abc')

    def test_unknown_unit_y_raises_valueerror(self):
        """Unknown unit 'y'"""
        with pytest.raises(ValueError):
            parse_duration('1y')

    def test_unknown_unit_w_raises_valueerror(self):
        """Unknown unit 'w' (week)"""
        with pytest.raises(ValueError):
            parse_duration('1w')

    def test_no_quantity_raises_valueerror(self):
        """Missing quantity before unit"""
        with pytest.raises(ValueError):
            parse_duration('h')

    def test_no_quantity_multiple_units_raises_valueerror(self):
        """Missing quantity on one unit"""
        with pytest.raises(ValueError):
            parse_duration('1h m')

    def test_non_numeric_quantity_raises_valueerror(self):
        """Non-numeric quantity"""
        with pytest.raises(ValueError):
            parse_duration('ah')

    def test_float_quantity_raises_valueerror(self):
        """Float quantity (should be integer)"""
        with pytest.raises(ValueError):
            parse_duration('1.5h')

    def test_float_with_multiple_decimals_raises_valueerror(self):
        """Float with multiple decimal places"""
        with pytest.raises(ValueError):
            parse_duration('2.5m')

    def test_reversed_order_raises_valueerror(self):
        """Reversed order: unit before quantity"""
        with pytest.raises(ValueError):
            parse_duration('h1')

    def test_duplicate_units_raises_valueerror(self):
        """Duplicate unit types"""
        with pytest.raises(ValueError):
            parse_duration('1h 2h')

    def test_duplicate_units_same_unit_twice(self):
        """Same unit appears twice"""
        with pytest.raises(ValueError):
            parse_duration('30m 15m')

    def test_negative_quantity_raises_valueerror(self):
        """Negative quantity"""
        with pytest.raises(ValueError):
            parse_duration('-1h')

    def test_only_whitespace_raises_valueerror(self):
        """Only whitespace"""
        with pytest.raises(ValueError):
            parse_duration('   ')

    def test_special_characters_raises_valueerror(self):
        """Special characters in input"""
        with pytest.raises(ValueError):
            parse_duration('1h@30m')

    def test_uppercase_units_raises_valueerror(self):
        """Uppercase units (should be lowercase)"""
        with pytest.raises(ValueError):
            parse_duration('1H30M')

    def test_mixed_case_units_raises_valueerror(self):
        """Mixed case units"""
        with pytest.raises(ValueError):
            parse_duration('1H 30m')


class TestDurationParserReturnType:
    """Test return type (AC12)."""

    def test_return_type_is_int(self):
        """AC12: Function returns int, not float"""
        result = parse_duration('1h30m45s')
        assert isinstance(result, int)
        assert not isinstance(result, bool)  # bool is subclass of int in Python
        assert result == 5445

    def test_all_acceptance_criteria_return_int(self):
        """All AC test cases return int"""
        assert isinstance(parse_duration('2h30m'), int)
        assert isinstance(parse_duration('1d'), int)
        assert isinstance(parse_duration('45s'), int)
        assert isinstance(parse_duration('1h 15m 30s'), int)
        assert isinstance(parse_duration('90m'), int)
        assert isinstance(parse_duration('1d 2h 3m 4s'), int)

    def test_single_units_return_int(self):
        """Single units return int"""
        assert isinstance(parse_duration('1d'), int)
        assert isinstance(parse_duration('1h'), int)
        assert isinstance(parse_duration('1m'), int)
        assert isinstance(parse_duration('1s'), int)


class TestDurationParserZeroValues:
    """Test zero value handling."""

    def test_parse_zero_seconds(self):
        """Zero seconds"""
        assert parse_duration('0s') == 0

    def test_parse_zero_minutes(self):
        """Zero minutes"""
        assert parse_duration('0m') == 0

    def test_parse_zero_hours(self):
        """Zero hours"""
        assert parse_duration('0h') == 0

    def test_parse_zero_days(self):
        """Zero days"""
        assert parse_duration('0d') == 0

    def test_parse_multiple_zeros(self):
        """Multiple zero components"""
        assert parse_duration('0d 0h 0m 0s') == 0

    def test_parse_zeros_with_nonzero(self):
        """Mix of zero and non-zero components"""
        assert parse_duration('0d 1h 0m 30s') == 3630


class TestDurationParserLargeValues:
    """Test large value handling."""

    def test_parse_large_days(self):
        """Large day value"""
        assert parse_duration('365d') == 31536000

    def test_parse_large_hours(self):
        """Large hour value"""
        assert parse_duration('1000h') == 3600000

    def test_parse_large_combined(self):
        """Large combined value"""
        # 100d = 8640000, 23h = 82800, 59m = 3540, 59s = 59
        # Total = 8640000 + 82800 + 3540 + 59 = 8726399
        assert parse_duration('100d 23h 59m 59s') == 8726399

    def test_parse_very_large_minutes(self):
        """Very large minute value"""
        assert parse_duration('10000m') == 600000


class TestDurationParserImport:
    """Test module import (AC13)."""

    def test_module_importable(self):
        """AC13: Module importable as from src.utils.duration_parser import parse_duration"""
        # If we got here, the import at the top of this file succeeded
        assert callable(parse_duration)

    def test_function_signature(self):
        """Function can be called with a string argument"""
        # This test verifies the basic interface exists
        try:
            result = parse_duration('1s')
            assert isinstance(result, int)
        except Exception as e:
            pytest.fail(f"Function call failed: {e}")
