"""
IMPLEMENTATION PLAN for US-002: Comprehensive Tests for DurationParser

Components:
  - TestBasicUnits: Tests for single unit types (d, h, m, s) with various quantities
  - TestCompoundDurations: Tests for multi-unit combinations, with/without whitespace
  - TestEdgeCasesValid: Tests for boundary conditions (zero values, large values, whitespace)
  - TestInvalidInput: Tests for all error conditions (empty, None, unknown units, non-numeric, duplicates)
  - TestReturnType: Tests verifying return type is always int
  - TestIntegration: Tests for real-world usage scenarios and round-trip validations

Test Strategy:
  1. Acceptance Criteria Coverage:
     - AC1-AC6: Basic compound duration parsing
     - AC7: Whitespace handling
     - AC8-AC11: Error handling for invalid inputs
     - AC12: Return type verification
     - AC13: Module import

  2. Comprehensive Unit Coverage:
     - Each unit (d, h, m, s) tested individually with various quantities
     - All combinations of units tested
     - All error scenarios covered

  3. Edge Cases:
     - Zero values (0d, 0h, 0m, 0s)
     - Large values (365d, 10000m)
     - Mixed whitespace (leading, trailing, multiple spaces)
     - Boundary conditions

Test Organization:
  - TestBasicUnits: Single-unit parsing
  - TestCompoundDurations: Multi-unit parsing
  - TestEdgeCasesValid: Valid edge cases
  - TestInvalidInput: Error conditions
  - TestReturnType: Type checking
  - TestIntegration: Real-world scenarios

Total Test Count: 50+ comprehensive test cases
"""

import pytest
from src.utils.duration_parser import parse_duration


class TestBasicUnits:
    """Test parsing of individual duration units: d (days), h (hours), m (minutes), s (seconds)."""

    # Days
    def test_parse_1d_returns_86400_seconds(self):
        """Single day returns 86400 seconds"""
        assert parse_duration('1d') == 86400

    def test_parse_2d_returns_172800_seconds(self):
        """Two days returns 172800 seconds"""
        assert parse_duration('2d') == 172800

    def test_parse_7d_returns_604800_seconds(self):
        """Seven days returns 604800 seconds"""
        assert parse_duration('7d') == 604800

    def test_parse_10d_returns_864000_seconds(self):
        """Ten days returns 864000 seconds"""
        assert parse_duration('10d') == 864000

    # Hours
    def test_parse_1h_returns_3600_seconds(self):
        """Single hour returns 3600 seconds"""
        assert parse_duration('1h') == 3600

    def test_parse_2h_returns_7200_seconds(self):
        """Two hours returns 7200 seconds"""
        assert parse_duration('2h') == 7200

    def test_parse_24h_returns_86400_seconds(self):
        """24 hours equals one day"""
        assert parse_duration('24h') == 86400

    def test_parse_48h_returns_172800_seconds(self):
        """48 hours equals two days"""
        assert parse_duration('48h') == 172800

    # Minutes
    def test_parse_1m_returns_60_seconds(self):
        """Single minute returns 60 seconds"""
        assert parse_duration('1m') == 60

    def test_parse_30m_returns_1800_seconds(self):
        """30 minutes returns 1800 seconds"""
        assert parse_duration('30m') == 1800

    def test_parse_60m_returns_3600_seconds(self):
        """60 minutes equals one hour"""
        assert parse_duration('60m') == 3600

    def test_parse_120m_returns_7200_seconds(self):
        """120 minutes equals two hours"""
        assert parse_duration('120m') == 7200

    # Seconds
    def test_parse_1s_returns_1_second(self):
        """Single second returns 1 second"""
        assert parse_duration('1s') == 1

    def test_parse_30s_returns_30_seconds(self):
        """30 seconds returns 30"""
        assert parse_duration('30s') == 30

    def test_parse_60s_returns_60_seconds(self):
        """60 seconds equals one minute"""
        assert parse_duration('60s') == 60

    def test_parse_3600s_returns_3600_seconds(self):
        """3600 seconds equals one hour"""
        assert parse_duration('3600s') == 3600

    # Large single values
    def test_parse_100d_returns_8640000_seconds(self):
        """Large day value"""
        assert parse_duration('100d') == 8640000

    def test_parse_1000h_returns_3600000_seconds(self):
        """Large hour value"""
        assert parse_duration('1000h') == 3600000


class TestCompoundDurations:
    """Test parsing of multi-unit duration combinations."""

    # Two-unit combinations
    def test_parse_1d_1h_returns_90000_seconds(self):
        """1 day and 1 hour"""
        assert parse_duration('1d1h') == 90000

    def test_parse_1h_30m_returns_5400_seconds(self):
        """1 hour and 30 minutes"""
        assert parse_duration('1h30m') == 5400

    def test_parse_1h_30s_returns_3630_seconds(self):
        """1 hour and 30 seconds"""
        assert parse_duration('1h30s') == 3630

    def test_parse_30m_45s_returns_1845_seconds(self):
        """30 minutes and 45 seconds"""
        assert parse_duration('30m45s') == 1845

    # Three-unit combinations
    def test_parse_1d_1h_30m_returns_91800_seconds(self):
        """1 day, 1 hour, and 30 minutes

        Calculation: 1d=86400, 1h=3600, 30m=1800
        Total: 86400 + 3600 + 1800 = 91800
        """
        assert parse_duration('1d1h30m') == 91800

    def test_parse_1h_15m_30s_returns_4530_seconds(self):
        """1 hour, 15 minutes, and 30 seconds"""
        assert parse_duration('1h15m30s') == 4530

    def test_parse_2d_3h_45m_returns_186300_seconds(self):
        """2 days, 3 hours, and 45 minutes

        Calculation: 2d=172800, 3h=10800, 45m=2700
        Total: 172800 + 10800 + 2700 = 186300
        """
        assert parse_duration('2d3h45m') == 186300

    # Four-unit combination
    def test_parse_1d_2h_3m_4s_returns_93784_seconds(self):
        """1 day, 2 hours, 3 minutes, and 4 seconds

        Calculation:
        1d = 86400
        2h = 7200
        3m = 180
        4s = 4
        Total = 93784
        """
        assert parse_duration('1d2h3m4s') == 93784

    # Complex combinations
    def test_parse_5d_12h_30m_15s_returns_477015_seconds(self):
        """5 days, 12 hours, 30 minutes, and 15 seconds

        Calculation: 5d=432000, 12h=43200, 30m=1800, 15s=15
        Total: 432000 + 43200 + 1800 + 15 = 477015
        """
        assert parse_duration('5d12h30m15s') == 477015

    def test_parse_10d_23h_59m_59s_returns_950399_seconds(self):
        """10 days, 23 hours, 59 minutes, and 59 seconds

        Calculation: 10d=864000, 23h=82800, 59m=3540, 59s=59
        Total: 864000 + 82800 + 3540 + 59 = 950399
        """
        assert parse_duration('10d23h59m59s') == 950399

    # With whitespace variations
    def test_parse_compound_with_single_spaces(self):
        """Compound duration with single spaces"""
        assert parse_duration('1h 30m 45s') == 5445

    def test_parse_compound_with_multiple_spaces(self):
        """Compound duration with multiple spaces"""
        assert parse_duration('1h  30m   45s') == 5445

    def test_parse_compound_with_leading_trailing_spaces(self):
        """Compound duration with leading and trailing spaces"""
        assert parse_duration('  1h 30m 45s  ') == 5445

    def test_parse_2h30m_with_spaces(self):
        """2h30m with spaces equals 9000 seconds"""
        assert parse_duration('2h 30m') == 9000

    def test_parse_90m_returns_5400(self):
        """90m converts to 5400 seconds"""
        assert parse_duration('90m') == 5400

    def test_parse_1d_2h_3m_4s_with_spaces_returns_93784(self):
        """Full duration with spaces"""
        assert parse_duration('1d 2h 3m 4s') == 93784


class TestEdgeCasesValid:
    """Test valid edge cases: zero values, large values, whitespace edge cases."""

    # Zero values
    def test_parse_0s_returns_0(self):
        """Zero seconds"""
        assert parse_duration('0s') == 0

    def test_parse_0m_returns_0(self):
        """Zero minutes"""
        assert parse_duration('0m') == 0

    def test_parse_0h_returns_0(self):
        """Zero hours"""
        assert parse_duration('0h') == 0

    def test_parse_0d_returns_0(self):
        """Zero days"""
        assert parse_duration('0d') == 0

    def test_parse_0d_0h_0m_0s_returns_0(self):
        """All zero components"""
        assert parse_duration('0d 0h 0m 0s') == 0

    def test_parse_0d_1h_0m_30s_returns_3630(self):
        """Zero with non-zero components"""
        assert parse_duration('0d 1h 0m 30s') == 3630

    # Large values
    def test_parse_365d_returns_31536000_seconds(self):
        """365 days (one year)"""
        assert parse_duration('365d') == 31536000

    def test_parse_999d_returns_86313600_seconds(self):
        """999 days - very large value"""
        assert parse_duration('999d') == 86313600

    def test_parse_10000m_returns_600000_seconds(self):
        """10000 minutes"""
        assert parse_duration('10000m') == 600000

    def test_parse_100d_23h_59m_59s_returns_8726399_seconds(self):
        """100 days, 23 hours, 59 minutes, and 59 seconds"""
        assert parse_duration('100d 23h 59m 59s') == 8726399

    # Whitespace edge cases
    def test_parse_with_leading_whitespace(self):
        """Leading whitespace is stripped"""
        assert parse_duration('   1h30m') == 5400

    def test_parse_with_trailing_whitespace(self):
        """Trailing whitespace is stripped"""
        assert parse_duration('1h30m   ') == 5400

    def test_parse_with_both_leading_and_trailing_whitespace(self):
        """Both leading and trailing whitespace is stripped"""
        assert parse_duration('   1h30m   ') == 5400

    def test_parse_with_excessive_internal_whitespace(self):
        """Multiple spaces between components"""
        assert parse_duration('1h     30m     45s') == 5445

    def test_parse_tabs_and_spaces_mixed(self):
        """Tabs treated as whitespace"""
        # Note: tabs are whitespace, should be handled by strip()
        assert parse_duration('\t1h30m\t') == 5400


class TestInvalidInput:
    """Test all error conditions and invalid inputs."""

    # Empty/None inputs
    def test_parse_empty_string_raises_valueerror(self):
        """Empty string raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('')

    def test_parse_whitespace_only_raises_valueerror(self):
        """Whitespace-only string raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('   ')

    def test_parse_tabs_only_raises_valueerror(self):
        """Tabs-only string raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('\t\t\t')

    # No valid tokens
    def test_parse_abc_raises_valueerror(self):
        """Letters without numbers raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('abc')

    def test_parse_no_quantity_before_unit_raises_valueerror(self):
        """Unit without quantity raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('h')

    def test_parse_multiple_units_no_quantity_raises_valueerror(self):
        """Multiple units, one without quantity raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1h m')

    # Unknown units
    def test_parse_unknown_unit_x_raises_valueerror(self):
        """Unknown unit 'x' raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('2x')

    def test_parse_unknown_unit_y_raises_valueerror(self):
        """Unknown unit 'y' (years) raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1y')

    def test_parse_unknown_unit_w_raises_valueerror(self):
        """Unknown unit 'w' (weeks) raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1w')

    def test_parse_unknown_unit_n_raises_valueerror(self):
        """Unknown unit 'n' raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('5n')

    # Non-numeric quantities
    def test_parse_non_numeric_quantity_raises_valueerror(self):
        """Non-numeric quantity raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('ah')

    def test_parse_float_quantity_raises_valueerror(self):
        """Float quantity raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1.5h')

    def test_parse_float_with_multiple_decimals_raises_valueerror(self):
        """Float with multiple decimal places raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('2.5m')

    # Negative quantities
    def test_parse_negative_quantity_raises_valueerror(self):
        """Negative quantity raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('-1h')

    def test_parse_negative_with_multiple_units_raises_valueerror(self):
        """Negative in multi-unit raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('-5d -2h')

    # Reversed order
    def test_parse_unit_before_quantity_raises_valueerror(self):
        """Unit before quantity raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('h1')

    def test_parse_mixed_reversed_order_raises_valueerror(self):
        """Mixed reversed order raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1h m30')

    # Duplicate units
    def test_parse_duplicate_hours_raises_valueerror(self):
        """Duplicate hours raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1h 2h')

    def test_parse_duplicate_minutes_raises_valueerror(self):
        """Duplicate minutes raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('30m 15m')

    def test_parse_duplicate_in_longer_string_raises_valueerror(self):
        """Duplicate in longer duration raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1d 2h 3h 4m')

    # Partially unparseable input
    def test_parse_trailing_text_raises_valueerror(self):
        """Trailing unparseable text raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1h abc')

    def test_parse_leading_text_raises_valueerror(self):
        """Leading unparseable text raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('abc 1h')

    def test_parse_middle_text_raises_valueerror(self):
        """Unparseable text in middle raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1h xyz 30m')

    # Special characters
    def test_parse_special_characters_raises_valueerror(self):
        """Special characters raise ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1h@30m')

    def test_parse_symbols_raises_valueerror(self):
        """Symbols in input raise ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1h#30m')

    def test_parse_punctuation_raises_valueerror(self):
        """Punctuation raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1h, 30m')

    # Case sensitivity
    def test_parse_uppercase_units_raises_valueerror(self):
        """Uppercase units raise ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1H')

    def test_parse_mixed_case_raises_valueerror(self):
        """Mixed case units raise ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1H 30m')

    def test_parse_all_uppercase_raises_valueerror(self):
        """All uppercase raises ValueError"""
        with pytest.raises(ValueError):
            parse_duration('1D 2H 3M 4S')


class TestReturnType:
    """Test that parse_duration always returns int type."""

    def test_return_type_single_unit_is_int(self):
        """Single unit returns int"""
        result = parse_duration('1s')
        assert isinstance(result, int)
        assert not isinstance(result, bool)
        assert result == 1

    def test_return_type_compound_is_int(self):
        """Compound duration returns int"""
        result = parse_duration('1h 30m 45s')
        assert isinstance(result, int)
        assert not isinstance(result, bool)
        assert result == 5445

    def test_return_type_large_value_is_int(self):
        """Large value returns int"""
        result = parse_duration('365d')
        assert isinstance(result, int)
        assert not isinstance(result, bool)
        assert result == 31536000

    def test_return_type_zero_is_int(self):
        """Zero value returns int"""
        result = parse_duration('0s')
        assert isinstance(result, int)
        assert not isinstance(result, bool)
        assert result == 0

    def test_return_type_all_units_is_int(self):
        """All units combined returns int"""
        result = parse_duration('1d 2h 3m 4s')
        assert isinstance(result, int)
        assert not isinstance(result, bool)
        assert result == 93784

    def test_return_type_never_float(self):
        """Result is never float"""
        results = [
            parse_duration('1s'),
            parse_duration('1m'),
            parse_duration('1h'),
            parse_duration('1d'),
            parse_duration('1h 30m'),
            parse_duration('100d 23h 59m 59s'),
        ]
        for result in results:
            assert not isinstance(result, float)
            assert isinstance(result, int)


class TestIntegration:
    """Integration tests for real-world usage scenarios."""

    def test_round_trip_basic_durations(self):
        """Parse various realistic durations"""
        test_cases = [
            ('30m', 1800),      # Meeting duration
            ('1h', 3600),       # Short work session
            ('8h', 28800),      # Work day
            ('1d', 86400),      # Full day
            ('7d', 604800),     # One week
        ]
        for duration_str, expected_seconds in test_cases:
            assert parse_duration(duration_str) == expected_seconds

    def test_common_time_expressions(self):
        """Parse common time expressions"""
        assert parse_duration('2h30m') == 9000     # 2.5 hours
        assert parse_duration('45m30s') == 2730    # 45.5 minutes
        assert parse_duration('1h 15m') == 4500    # 1.25 hours
        assert parse_duration('3d 4h') == 273600   # 3 days + 4 hours = 259200 + 14400

    def test_api_timeout_durations(self):
        """Realistic API timeout scenarios"""
        assert parse_duration('30s') == 30         # Quick check
        assert parse_duration('5m') == 300         # Connection timeout
        assert parse_duration('30m') == 1800       # Long operation
        assert parse_duration('1h 30m') == 5400    # Extended operation

    def test_scheduling_durations(self):
        """Realistic scheduling scenarios"""
        assert parse_duration('2h') == 7200        # Meeting block
        assert parse_duration('1d') == 86400       # Daily task
        assert parse_duration('1d 2h') == 93600    # Deadline with buffer
        assert parse_duration('7d') == 604800      # Weekly deadline

    def test_cumulative_duration_calculation(self):
        """Verify calculations for combined scenarios"""
        # Multiple operations that need cumulative time
        op1 = parse_duration('5m')           # 300s
        op2 = parse_duration('10m')          # 600s
        op3 = parse_duration('1h')           # 3600s
        total = op1 + op2 + op3
        assert total == 4500

    def test_duration_comparisons(self):
        """Compare parsed durations"""
        short = parse_duration('30m')
        medium = parse_duration('1h')
        long = parse_duration('2h')

        assert short < medium < long
        assert medium == 2 * short
        assert long == 2 * medium

    def test_duration_boundary_conditions(self):
        """Test realistic boundary conditions"""
        # Just under 1 minute
        assert parse_duration('59s') == 59
        # Exactly 1 minute
        assert parse_duration('1m') == 60
        # Just over 1 minute
        assert parse_duration('1m1s') == 61

    def test_full_daily_schedule(self):
        """Verify a full day's schedule adds up"""
        sleep = parse_duration('8h')
        work = parse_duration('8h')
        exercise = parse_duration('1h')
        leisure = parse_duration('7h')
        total = sleep + work + exercise + leisure
        assert total == 86400  # Exactly 24 hours

    def test_project_duration_scenarios(self):
        """Realistic project timing scenarios"""
        # Sprint = 2 weeks (using days instead of weeks, since 'w' is not supported)
        sprint_days = parse_duration('14d')
        assert sprint_days == 1209600  # 14 days in seconds

        # Multiple sprints (3 sprints = 42 days)
        multiple_sprints = parse_duration('42d')
        assert multiple_sprints == sprint_days * 3
