"""
IMPLEMENTATION PLAN for US-001:

Components:
  - src/utils/email_warmup_generator.py: This new file will contain the core logic.
  - generate_email_warmup_schedule(start_volume: int, end_volume: int, domain: str, days: int = 28) -> list[dict]: This function will generate the daily schedule.
    - Responsibilities:
      - Calculate daily send volumes for a smooth ramp-up over 28 days.
      - Assign target audience segments based on the ramp-up phase (e.g., highly engaged initially, then broader).
      - Define expected bounce rate thresholds, possibly starting slightly higher and decreasing.
      - Ensure the output format is a list of dictionaries, each representing a day.

Test Cases:
  1. AC 1 (Schedule length): Verify the schedule contains 28 entries.
  2. AC 1 (Send volume ramp-up): Verify send volumes increase monotonically and are within a reasonable range from start to end.
  3. AC 1 (First and last day volumes): Verify the send volume for day 1 and day 28.
  4. AC 2 (Target audience presence): Verify each day has a non-empty 'target_audience_segment'.
  5. AC 2 (Audience segments content): Verify early days have "Highly Engaged Subscribers" and later days have "Broader Engaged Segments".
  6. AC 3 (Bounce rate presence): Verify each day has a numeric 'expected_bounce_rate_threshold'.
  7. AC 3 (Bounce rate thresholds content): Verify thresholds are within a sensible range (e.g., 0.005 to 0.01).

Edge Cases:
  - Invalid start_volume (non-positive) raises error.
  - start_volume greater than end_volume raises error.
  - Invalid days (non-positive) raises error.
  - Empty domain name is handled (though for this story, "logicalfront.net" is fixed, good to test robustness).
"""
import pytest
import sys
# We expect this import to fail initially, leading to TDD-RED state.
from src.utils.email_warmup_generator import generate_email_warmup_schedule

class TestEmailWarmupScheduleGenerator:

    def test_schedule_has_28_days(self):
        schedule = generate_email_warmup_schedule(
            start_volume=50, end_volume=2500, domain="logicalfront.net"
        )
        assert len(schedule) == 28

    def test_send_volumes_ramp_up_correctly(self):
        schedule = generate_email_warmup_schedule(
            start_volume=50, end_volume=2500, domain="logicalfront.net"
        )
        for i in range(len(schedule) - 1):
            assert schedule[i]["send_volume"] <= schedule[i+1]["send_volume"]
        assert schedule[0]["send_volume"] >= 50
        assert schedule[-1]["send_volume"] <= 2500

    def test_first_and_last_day_send_volumes(self):
        schedule = generate_email_warmup_schedule(
            start_volume=50, end_volume=2500, domain="logicalfront.net"
        )
        assert schedule[0]["send_volume"] == 50
        # Allow for minor discrepancies due to ramp-up calculation (e.g., rounding)
        assert abs(schedule[-1]["send_volume"] - 2500) < 50

    def test_each_day_has_target_audience_segment(self):
        schedule = generate_email_warmup_schedule(
            start_volume=50, end_volume=2500, domain="logicalfront.net"
        )
        for day_entry in schedule:
            assert "target_audience_segment" in day_entry
            assert isinstance(day_entry["target_audience_segment"], str)
            assert len(day_entry["target_audience_segment"]) > 0

    def test_audience_segments_reflect_ramp_up_phases(self):
        schedule = generate_email_warmup_schedule(
            start_volume=50, end_volume=2500, domain="logicalfront.net"
        )
        # First week: highly engaged
        for i in range(7):
            assert "Highly Engaged" in schedule[i]["target_audience_segment"]
        # Later weeks: broader
        for i in range(14, 28): # From week 3 onwards
            assert ("Broader" in schedule[i]["target_audience_segment"] or 
                    "Targeted Engaged" in schedule[i]["target_audience_segment"])


    def test_each_day_has_expected_bounce_rate_threshold(self):
        schedule = generate_email_warmup_schedule(
            start_volume=50, end_volume=2500, domain="logicalfront.net"
        )
        for day_entry in schedule:
            assert "expected_bounce_rate_threshold" in day_entry
            assert isinstance(day_entry["expected_bounce_rate_threshold"], (float, int))
            assert 0.0 <= day_entry["expected_bounce_rate_threshold"] <= 0.05 # Realistic threshold

    def test_bounce_rate_thresholds_are_reasonable(self):
        schedule = generate_email_warmup_schedule(
            start_volume=50, end_volume=2500, domain="logicalfront.net"
        )
        for day_entry in schedule:
            assert 0.001 <= day_entry["expected_bounce_rate_threshold"] <= 0.02

    def test_invalid_start_volume_raises_error(self):
        with pytest.raises(ValueError, match="Start volume must be positive"):
            generate_email_warmup_schedule(start_volume=0, end_volume=2500, domain="logicalfront.net")
        with pytest.raises(ValueError, match="Start volume must be positive"):
            generate_email_warmup_schedule(start_volume=-10, end_volume=2500, domain="logicalfront.net")

    def test_start_volume_greater_than_end_volume_raises_error(self):
        with pytest.raises(ValueError, match="End volume must be greater than or equal to start volume"):
            generate_email_warmup_schedule(start_volume=1000, end_volume=500, domain="logicalfront.net")

    def test_invalid_days_raises_error(self):
        with pytest.raises(ValueError, match="Number of days must be positive"):
            generate_email_warmup_schedule(start_volume=50, end_volume=2500, domain="logicalfront.net", days=0)
        with pytest.raises(ValueError, match="Number of days must be positive"):
            generate_email_warmup_schedule(start_volume=50, end_volume=2500, domain="logicalfront.net", days=-5)

    def test_empty_domain_name_is_handled(self):
        # Depending on implementation, this might raise an error or just proceed.
        # For now, let's expect it to not crash and have domain in output if used.
        schedule = generate_email_warmup_schedule(start_volume=50, end_volume=2500, domain="")
        assert schedule is not None
        assert len(schedule) == 28 # Still generates 28 days

# This is critical for TDD-RED-CHECK. It ensures a non-zero exit code if tests fail.
if __name__ == "__main__":
    pytest.main([__file__])
    # In a real pytest run, the exit code is handled by pytest itself.
    # For direct execution, this helps simulate the failure.
    # For the agent, simply running pytest on the file is sufficient for checking exit codes.
    # The actual failure will come from the import error, so this main block might not be strictly necessary
    # but it's good practice for local testing.
