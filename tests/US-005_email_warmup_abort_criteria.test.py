"""
IMPLEMENTATION PLAN for US-005:

Components:
  - src/monitoring/email_warmup_monitor.py: A new module to encapsulate email warmup monitoring logic.
    - EmailWarmupMonitor class:
      - __init__(self, bounce_threshold: float, complaint_threshold: float): Initializes with configurable thresholds.
      - check_abort_criteria(self, current_bounce_rate: float, current_complaint_rate: float, ses_account_status: str) -> list[str]:
        - Takes current email metrics and SES status.
        - Returns a list of violated criteria (e.g., ["bounce_rate_exceeded", "ses_paused"]).
      - get_remediation_steps(self, violated_criteria: list[str]) -> dict[str, str]:
        - Takes a list of violated criteria.
        - Returns a dictionary mapping each violated criterion to its specific remediation steps.

Test Cases:
  1. Specific abort criteria defined -> test_should_not_abort_when_all_metrics_normal, test_should_abort_on_high_bounce_rate, test_should_abort_on_high_complaint_rate, test_should_abort_on_ses_account_pause, test_should_identify_multiple_abort_criteria.
  2. Remediation steps for each abort criterion provided -> test_should_provide_remediation_for_high_bounce_rate, test_should_provide_remediation_for_high_complaint_rate, test_should_provide_remediation_for_ses_account_pause, test_should_provide_combined_remediation_for_multiple_criteria.

Edge Cases:
  - Rates exactly at the threshold boundaries.
  - Zero bounce/complaint rates.
  - Unexpected SES account statuses.
  - Empty list of violated criteria for remediation.
"""
import pytest
import sys

# We expect these imports to fail initially, leading to TDD-RED state.
from src.monitoring.email_warmup_monitor import EmailWarmupMonitor

class TestEmailWarmupMonitor:
    def setup_method(self):
        # Using typical thresholds for testing
        self.monitor = EmailWarmupMonitor(bounce_threshold=0.05, complaint_threshold=0.001)

    def test_should_not_abort_when_all_metrics_normal(self):
        violated_criteria = self.monitor.check_abort_criteria(
            current_bounce_rate=0.03,
            current_complaint_rate=0.0005,
            ses_account_status="Healthy"
        )
        assert len(violated_criteria) == 0

    def test_should_abort_on_high_bounce_rate(self):
        violated_criteria = self.monitor.check_abort_criteria(
            current_bounce_rate=0.051, # Just over threshold
            current_complaint_rate=0.0005,
            ses_account_status="Healthy"
        )
        assert "bounce_rate_exceeded" in violated_criteria
        assert len(violated_criteria) == 1

    def test_should_abort_on_high_complaint_rate(self):
        violated_criteria = self.monitor.check_abort_criteria(
            current_bounce_rate=0.03,
            current_complaint_rate=0.0011, # Just over threshold
            ses_account_status="Healthy"
        )
        assert "complaint_rate_exceeded" in violated_criteria
        assert len(violated_criteria) == 1

    def test_should_abort_on_ses_account_pause(self):
        violated_criteria = self.monitor.check_abort_criteria(
            current_bounce_rate=0.03,
            current_complaint_rate=0.0005,
            ses_account_status="Paused"
        )
        assert "ses_account_paused" in violated_criteria
        assert len(violated_criteria) == 1

    def test_should_identify_multiple_abort_criteria(self):
        violated_criteria = self.monitor.check_abort_criteria(
            current_bounce_rate=0.06,
            current_complaint_rate=0.002,
            ses_account_status="Paused"
        )
        assert "bounce_rate_exceeded" in violated_criteria
        assert "complaint_rate_exceeded" in violated_criteria
        assert "ses_account_paused" in violated_criteria
        assert len(violated_criteria) == 3

    def test_should_handle_rates_at_threshold_boundary(self):
        # Test exact threshold values
        violated_criteria = self.monitor.check_abort_criteria(
            current_bounce_rate=0.05, # Exactly at threshold, should not abort
            current_complaint_rate=0.001, # Exactly at threshold, should not abort
            ses_account_status="Healthy"
        )
        assert len(violated_criteria) == 0

        # Test slightly above thresholds
        violated_criteria_above = self.monitor.check_abort_criteria(
            current_bounce_rate=0.05 + 1e-9,
            current_complaint_rate=0.001 + 1e-9,
            ses_account_status="Healthy"
        )
        assert "bounce_rate_exceeded" in violated_criteria_above
        assert "complaint_rate_exceeded" in violated_criteria_above
        assert len(violated_criteria_above) == 2


    def test_should_provide_remediation_for_high_bounce_rate(self):
        violated = ["bounce_rate_exceeded"]
        remediation = self.monitor.get_remediation_steps(violated)
        assert "bounce_rate_exceeded" in remediation
        assert isinstance(remediation["bounce_rate_exceeded"], str)
        assert "reduce sending volume" in remediation["bounce_rate_exceeded"].lower()

    def test_should_provide_remediation_for_high_complaint_rate(self):
        violated = ["complaint_rate_exceeded"]
        remediation = self.monitor.get_remediation_steps(violated)
        assert "complaint_rate_exceeded" in remediation
        assert isinstance(remediation["complaint_rate_exceeded"], str)
        assert "review email content" in remediation["complaint_rate_exceeded"].lower()

    def test_should_provide_remediation_for_ses_account_pause(self):
        violated = ["ses_account_paused"]
        remediation = self.monitor.get_remediation_steps(violated)
        assert "ses_account_paused" in remediation
        assert isinstance(remediation["ses_account_paused"], str)
        assert "contact aws support" in remediation["ses_account_paused"].lower()

    def test_should_provide_combined_remediation_for_multiple_criteria(self):
        violated = ["bounce_rate_exceeded", "complaint_rate_exceeded", "ses_account_paused"]
        remediation = self.monitor.get_remediation_steps(violated)
        assert "bounce_rate_exceeded" in remediation
        assert "complaint_rate_exceeded" in remediation
        assert "ses_account_paused" in remediation
        assert len(remediation) == 3
        assert isinstance(remediation["bounce_rate_exceeded"], str)
        assert isinstance(remediation["complaint_rate_exceeded"], str)
        assert isinstance(remediation["ses_account_paused"], str)

    def test_should_return_empty_remediation_for_no_violations(self):
        violated = []
        remediation = self.monitor.get_remediation_steps(violated)
        assert len(remediation) == 0

# This is critical for TDD-RED-CHECK. It ensures a non-zero exit code if tests fail.
if __name__ == "__main__":
    pytest.main([__file__])
