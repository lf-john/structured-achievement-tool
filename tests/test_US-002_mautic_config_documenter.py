import pytest
import sys
from unittest.mock import MagicMock

# AMENDED BY US-002: Updated the import path to match the new naming convention and updated the mock signature.
# Assuming the future implementation will be in src/utils/mautic_config_documenter.py
# This import is expected to fail with ModuleNotFoundError, causing the TDD-RED state.
try:
    from src.utils.mautic_config_documenter import generate_mautic_config_docs
except ImportError:
    # This block ensures the test can still run and fail explicitly if the import fails
    # rather than stopping execution immediately, allowing other test definitions to be
    # validated. The TDD-RED phase expects this ImportError for success.
    # AMENDED BY US-002: Updated MagicMock to accept new parameters.
    def generate_mautic_config_docs(warmup_plan, current_cron_line, mautic_config_settings):
        raise ImportError("Mocked ImportError for TDD-RED: generate_mautic_config_docs is not implemented.")


"""
IMPLEMENTATION PLAN for US-002: Adjust and Document Mautic Cron Frequency for Week 1 Warmup

Components:
  - `src/utils/mautic_config_documenter.py`: This existing module's `generate_mautic_config_docs` function will be enhanced.
    - `generate_mautic_config_docs(warmup_plan: list[dict], current_cron_line: str, mautic_config_settings: dict) -> str`: This function will take a structured representation of the weekly warmup plan, the current Mautic cron line for `mautic:emails:send`, and Mautic configuration settings (including `mailer_spool_msg_limit` if available). It will return a Markdown-formatted string documenting Mautic configurations, the cron schedule, and explicit instructions for daily cron adjustment or verification of `mailer_spool_msg_limit`.

Data Flow:
  - Input:
    - `warmup_plan` (list of dicts): Existing input, providing weekly email sending parameters.
    - `current_cron_line` (str): The detected current cron line for `mautic:emails:send`.
    - `mautic_config_settings` (dict): A dictionary that may contain `mailer_spool_msg_limit`.
  - Processing: The function will integrate all provided data into a human-readable document, detailing cron frequency, daily limits, and modification instructions.
  - Output: A comprehensive Markdown string including all Mautic configuration details and cron instructions.

Integration Points:
  - The `generate_mautic_config_docs` function will be modified. This utility is expected to be called by the orchestrator or a documentation generation script. It provides instructions related to Mautic and cron jobs but does not directly modify them.

Edge Cases:
  - Empty `warmup_plan`: Should return a document indicating no plan or a default message.
  - Missing data for a week in `warmup_plan`: The function should gracefully handle missing keys (e.g., `queue_frequency`) for a given week, perhaps by indicating "N/A" or "Not specified".
  - Empty `current_cron_line`: Should indicate that the current cron line could not be determined.
  - Missing `mailer_spool_msg_limit` in `mautic_config_settings`: Should mention that the spool limit is not set or needs verification.
  - Invalid data types: The function should ideally raise an error or handle gracefully if input data types are incorrect.

Test Cases:
  1. AC 1: The `mautic:emails:send` cron is configured to run effectively once per day or is capped by `mailer_spool_msg_limit`. -> `test_should_document_effective_daily_cron_or_spool_limit`
  2. AC 2: The current cron line for `mautic:emails:send` is documented. -> `test_should_document_current_mautic_emails_send_cron_line`
  3. AC 3: Instructions on how to modify the cron schedule are documented. -> `test_should_provide_instructions_for_adjusting_mautic_cron_frequency` (Existing test, ensuring it covers new context)

Edge Cases:
  - Empty warmup plan. -> `test_should_handle_empty_warmup_plan`
  - Missing specific data for a week. -> `test_should_handle_missing_weekly_data_gracefully`
  - Empty current cron line. -> `test_should_handle_empty_cron_line`
  - Missing mailer_spool_msg_limit in config. -> `test_should_handle_missing_spool_limit_in_config`
"""

class TestMauticConfigDocumenter:

    # Define a sample warmup plan for testing
    SAMPLE_WARMUP_PLAN = [
        {
            "week_num": 1,
            "queue_frequency": "5 minutes",
            "batch_size": 50,
            "rate_limit": 100
        },
        {
            "week_num": 2,
            "queue_frequency": "2 minutes",
            "batch_size": 100,
            "rate_limit": 200
        }
    ]

    # AMENDED BY US-002: Added sample cron line and mautic config for new tests.
    SAMPLE_CRON_LINE = "* * * * * php /var/www/html/bin/console mautic:emails:send"
    SAMPLE_MAUTIC_CONFIG_WITH_SPOOL = {"mailer_spool_msg_limit": 500}
    SAMPLE_MAUTIC_CONFIG_WITHOUT_SPOOL = {}

    def test_should_document_queue_processing_frequency_per_week(self):
        """
        Verifies that the generated documentation includes the queue processing frequency
        for each week as per the acceptance criteria.
        """
        # AMENDED BY US-002: Updated call to include new parameters.
        doc = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "Week 1:" in doc
        assert "Queue Processing Frequency: 5 minutes" in doc
        assert "Week 2:" in doc
        assert "Queue Processing Frequency: 2 minutes" in doc

    def test_should_document_batch_size_per_cron_run_per_week(self):
        """
        Verifies that the generated documentation includes the batch size per cron run
        for each week as per the acceptance criteria.
        """
        # AMENDED BY US-002: Updated call to include new parameters.
        doc = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "Week 1:" in doc
        assert "Batch Size per Cron Run: 50" in doc
        assert "Week 2:" in doc
        assert "Batch Size per Cron Run: 100" in doc

    def test_should_document_sending_rate_limit_per_week(self):
        """
        Verifies that the generated documentation includes the sending rate limit
        for each week as per the acceptance criteria.
        """
        # AMENDED BY US-002: Updated call to include new parameters.
        doc = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "Week 1:" in doc
        assert "Sending Rate Limit (emails/minute): 100" in doc
        assert "Week 2:" in doc
        assert "Sending Rate Limit (emails/minute): 200" in doc

    def test_should_provide_instructions_on_changing_mautic_settings(self):
        """
        Verifies that the documentation includes general instructions on how to change
        Mautic settings.
        """
        # AMENDED BY US-002: Updated call to include new parameters.
        doc = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "Instructions on Changing Mautic Settings:" in doc
        assert "Mautic Admin UI Path" in doc
        assert "config file" in doc

    def test_should_provide_instructions_for_adjusting_mautic_cron_frequency(self):
        """
        Verifies that the documentation includes instructions for adjusting Mautic
        cron frequency using docker exec. (AC 3)
        """
        # AMENDED BY US-002: Updated call to include new parameters and added assertions for AC3.
        doc = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "Adjusting Mautic Cron Frequency (docker exec):" in doc
        assert "docker exec" in doc
        assert "cron" in doc
        assert "run once per day" in doc or "capped by mailer_spool_msg_limit" in doc


    # AMENDED BY US-002: Added new test for AC 1.
    def test_should_document_effective_daily_cron_or_spool_limit(self):
        """
        Verifies that the documentation explicitly mentions the effective daily run
        or the role of mailer_spool_msg_limit in capping daily volume. (AC 1)
        """
        # Test with spool limit
        doc_with_spool = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "effectively once per day" in doc_with_spool or \
               f"capped by mailer_spool_msg_limit ({self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL['mailer_spool_msg_limit']})" in doc_with_spool

        # Test without spool limit (should emphasize daily run)
        doc_without_spool = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITHOUT_SPOOL
        )
        assert "effectively once per day" in doc_without_spool or \
               "capped by mailer_spool_msg_limit (not configured)" in doc_without_spool # or similar phrasing

    # AMENDED BY US-002: Added new test for AC 2.
    def test_should_document_current_mautic_emails_send_cron_line(self):
        """
        Verifies that the documentation includes the current cron line for
        mautic:emails:send. (AC 2)
        """
        doc = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "Current `mautic:emails:send` Cron Line:" in doc
        assert self.SAMPLE_CRON_LINE in doc

    def test_should_handle_empty_warmup_plan(self):
        """
        Verifies that the function gracefully handles an empty warmup plan,
        producing a document that reflects this.
        """
        # AMENDED BY US-002: Updated call to include new parameters.
        doc = generate_mautic_config_docs(
            [],
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "No Mautic Warmup Plan provided or configured." in doc
        assert "Instructions on Changing Mautic Settings:" in doc # Still include general instructions

    def test_should_handle_missing_weekly_data_gracefully(self):
        """
        Verifies that the function gracefully handles a warmup plan with a week
        having missing data points.
        """
        incomplete_plan = [
            {
                "week_num": 3,
                "queue_frequency": "10 minutes",
                # batch_size is missing
                "rate_limit": 50
            }
        ]
        # AMENDED BY US-002: Updated call to include new parameters.
        doc = generate_mautic_config_docs(
            incomplete_plan,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "Week 3:" in doc
        assert "Queue Processing Frequency: 10 minutes" in doc
        assert "Batch Size per Cron Run: N/A" in doc # Expect N/A or similar for missing
        assert "Sending Rate Limit (emails/minute): 50" in doc

    # AMENDED BY US-002: Added new test for empty cron line edge case.
    def test_should_handle_empty_cron_line(self):
        """
        Verifies that the function gracefully handles an empty current cron line.
        """
        doc = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            "",
            self.SAMPLE_MAUTIC_CONFIG_WITH_SPOOL
        )
        assert "Current `mautic:emails:send` Cron Line: Not determined or empty." in doc

    # AMENDED BY US-002: Added new test for missing spool limit edge case.
    def test_should_handle_missing_spool_limit_in_config(self):
        """
        Verifies that the function gracefully handles missing mailer_spool_msg_limit in config.
        """
        doc = generate_mautic_config_docs(
            self.SAMPLE_WARMUP_PLAN,
            self.SAMPLE_CRON_LINE,
            self.SAMPLE_MAUTIC_CONFIG_WITHOUT_SPOOL
        )
        assert "mailer_spool_msg_limit: Not configured or detected." in doc


if __name__ == "__main__":
    pytest.main([__file__])
