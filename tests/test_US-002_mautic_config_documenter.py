import pytest
import sys
from unittest.mock import MagicMock

# Assuming the future implementation will be in src/utils/mautic_doc_generator.py
# This import is expected to fail with ModuleNotFoundError, causing the TDD-RED state.
try:
    from src.utils.mautic_doc_generator import generate_mautic_config_docs
except ImportError:
    # This block ensures the test can still run and fail explicitly if the import fails
    # rather than stopping execution immediately, allowing other test definitions to be
    # validated. The TDD-RED phase expects this ImportError for success.
    generate_mautic_config_docs = MagicMock(side_effect=ImportError("Mocked ImportError for TDD-RED"))


"""
IMPLEMENTATION PLAN for US-002:

Components:
  - `src/utils/mautic_doc_generator.py`: A new module containing a function `generate_mautic_config_docs`.
    - `generate_mautic_config_docs(warmup_plan: list[dict]) -> str`: This function will take a structured representation of the weekly warmup plan and return a Markdown-formatted string documenting the Mautic configurations and instructions.

Data Flow:
  - Input: `warmup_plan` (list of dicts, each dict for a week with 'week_num', 'queue_frequency', 'batch_size', 'rate_limit').
  - Processing: The function will iterate through the plan, format the data into a human-readable document, and append general instructions.
  - Output: A string containing the comprehensive documentation.

Integration Points:
  - This module will be a standalone utility, likely called by the orchestrator or a documentation generation script. It does not directly modify Mautic or cron jobs, but provides instructions on how to do so.

Edge Cases:
  - Empty `warmup_plan`: Should return a document indicating no plan or a default message.
  - Missing data for a week: The function should gracefully handle missing keys (e.g., `queue_frequency`) for a given week, perhaps by indicating "N/A" or "Not specified".
  - Invalid data types: The function should ideally raise an error or handle gracefully if input data types are incorrect (e.g., non-numeric batch size).

Test Cases:
  1. Mautic queue processing frequency documented per week. -> `test_should_document_queue_processing_frequency_per_week`
  2. Batch size per cron run documented per week. -> `test_should_document_batch_size_per_cron_run_per_week`
  3. Sending rate limit documented per week. -> `test_should_document_sending_rate_limit_per_week`
  4. Instructions on how to change Mautic settings provided. -> `test_should_provide_instructions_on_changing_mautic_settings`
  5. Instructions for adjusting Mautic cron frequency provided. -> `test_should_provide_instructions_for_adjusting_mautic_cron_frequency`
  6. Edge Case: Empty warmup plan. -> `test_should_handle_empty_warmup_plan`
  7. Edge Case: Missing specific data for a week. -> `test_should_handle_missing_weekly_data_gracefully`
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

    def test_should_document_queue_processing_frequency_per_week(self):
        """
        Verifies that the generated documentation includes the queue processing frequency
        for each week as per the acceptance criteria.
        """
        doc = generate_mautic_config_docs(self.SAMPLE_WARMUP_PLAN)
        assert "Week 1:" in doc
        assert "Queue Processing Frequency: 5 minutes" in doc
        assert "Week 2:" in doc
        assert "Queue Processing Frequency: 2 minutes" in doc

    def test_should_document_batch_size_per_cron_run_per_week(self):
        """
        Verifies that the generated documentation includes the batch size per cron run
        for each week as per the acceptance criteria.
        """
        doc = generate_mautic_config_docs(self.SAMPLE_WARMUP_PLAN)
        assert "Week 1:" in doc
        assert "Batch Size per Cron Run: 50" in doc
        assert "Week 2:" in doc
        assert "Batch Size per Cron Run: 100" in doc

    def test_should_document_sending_rate_limit_per_week(self):
        """
        Verifies that the generated documentation includes the sending rate limit
        for each week as per the acceptance criteria.
        """
        doc = generate_mautic_config_docs(self.SAMPLE_WARMUP_PLAN)
        assert "Week 1:" in doc
        assert "Sending Rate Limit (emails/minute): 100" in doc
        assert "Week 2:" in doc
        assert "Sending Rate Limit (emails/minute): 200" in doc

    def test_should_provide_instructions_on_changing_mautic_settings(self):
        """
        Verifies that the documentation includes general instructions on how to change
        Mautic settings.
        """
        doc = generate_mautic_config_docs(self.SAMPLE_WARMUP_PLAN)
        assert "Instructions on Changing Mautic Settings:" in doc
        assert "Mautic Admin UI Path" in doc
        assert "config file" in doc

    def test_should_provide_instructions_for_adjusting_mautic_cron_frequency(self):
        """
        Verifies that the documentation includes instructions for adjusting Mautic
        cron frequency using docker exec.
        """
        doc = generate_mautic_config_docs(self.SAMPLE_WARMUP_PLAN)
        assert "Adjusting Mautic Cron Frequency (docker exec):" in doc
        assert "docker exec" in doc
        assert "cron" in doc

    def test_should_handle_empty_warmup_plan(self):
        """
        Verifies that the function gracefully handles an empty warmup plan,
        producing a document that reflects this.
        """
        doc = generate_mautic_config_docs([])
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
        doc = generate_mautic_config_docs(incomplete_plan)
        assert "Week 3:" in doc
        assert "Queue Processing Frequency: 10 minutes" in doc
        assert "Batch Size per Cron Run: N/A" in doc # Expect N/A or similar for missing
        assert "Sending Rate Limit (emails/minute): 50" in doc


if __name__ == "__main__":
    pytest.main([__file__])
