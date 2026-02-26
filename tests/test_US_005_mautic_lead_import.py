import pytest
import sys
from unittest.mock import MagicMock, patch, mock_open
import os
import time

"""
IMPLEMENTATION PLAN for US-005:

Components:
  - marketing-automation/scripts/import_leads.py: Main script orchestrating the lead import.
    - MauticAPIClient: A class/module for handling Mautic API interactions, including authentication, HTTP requests, rate limiting, and retry mechanisms.
    - LeadImporter: A class/module responsible for reading the CSV, chunking data into batches, and coordinating with MauticAPIClient.
    - ProgressTracker: A mechanism (e.g., file-based) to save and load the last processed batch/row index to enable resume functionality.
    - LoggerFactory: For generating detailed logs about created, updated, and failed contacts.

Test Cases:
  1. [AC 1, AC 2] Should successfully import leads in batches via Mautic API.
  2. [AC 3] Should process CSV input in batches of 200 contacts.
  3. [AC 4] Should handle Mautic API rate limiting (HTTP 429) with retries and exponential backoff.
  4. [AC 4] Should handle transient Mautic API server errors (HTTP 5xx) with retries.
  5. [AC 5] Should correctly save and load import progress.
  6. [AC 5] Should resume importing from the last saved progress point.
  7. [AC 6] Should log detailed results including created, updated, and failed contacts per batch.
  8. [AC 7] Should correctly parse and use data from a cleaned CSV file.

Edge Cases:
  - Empty input CSV file.
  - CSV file with fewer contacts than the batch size.
  - All contacts failing during API import (e.g., due to invalid data).
  - Mautic API returning an unexpected response format.
  - Script interrupted without prior progress saved.
"""

# Expected to fail due to missing module/class
from marketing_automation.scripts.import_leads import MauticAPIClient, LeadImporter, ProgressTracker, LoggerFactory

class TestMauticLeadImport:

    @pytest.fixture
    def mock_mautic_api_client(self):
        with patch('marketing_automation.scripts.import_leads.MauticAPIClient') as MockClient:
            instance = MockClient.return_value
            # Default successful response for API calls
            instance.import_contacts_batch.return_value = {
                'created': 200, 'updated': 0, 'failed': 0, 'results': [{'id': i} for i in range(200)]
            }
            yield instance

    @pytest.fixture
    def mock_progress_tracker(self):
        with patch('marketing_automation.scripts.import_leads.ProgressTracker') as MockTracker:
            instance = MockTracker.return_value
            instance.load_progress.return_value = {'last_processed_row': 0}
            yield instance

    @pytest.fixture
    def mock_logger(self):
        with patch('marketing_automation.scripts.import_leads.LoggerFactory') as MockLogger:
            instance = MockLogger.get_logger.return_value
            yield instance
    
    @pytest.fixture
    def mock_sleep(self):
        with patch('time.sleep', MagicMock()) as mock:
            yield mock

    @pytest.fixture
    def sample_csv_content(self):
        # Generate content for a CSV file with more than one batch of contacts
        header = """email,firstname,lastname
"""
        rows = [f"test{i}@example.com,Test,User{i}" for i in range(500)] # 500 contacts, 2.5 batches
        return header + "\n".join(rows) + "\n"

    def test_should_import_leads_successfully_in_batches(self, mock_mautic_api_client, mock_progress_tracker, mock_logger, sample_csv_content):
        """
        [AC 1, AC 2] Should successfully import leads in batches via Mautic API.
        Verifies that the main import logic processes a CSV and calls the Mautic API client.
        """
        csv_path = "cleaned_leads.csv"
        # Mock file reading
        with patch('builtins.open', mock_open(read_data=sample_csv_content)):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200)
            importer.run_import()

            # Expect 3 batches for 500 contacts with a batch size of 200
            assert mock_mautic_api_client.import_contacts_batch.call_count == 3
            # Check if progress was saved after each batch
            assert mock_progress_tracker.save_progress.call_count == 3
            assert mock_logger.info.call_count >= 3 # Log per batch + overall summary

    def test_should_process_csv_in_batches_of_200(self, mock_mautic_api_client, mock_progress_tracker, mock_logger, sample_csv_content):
        """
        [AC 3] Should process CSV input in batches of 200 contacts.
        Ensures the LeadImporter correctly chunks the CSV data.
        """
        csv_path = "cleaned_leads.csv"
        with patch('builtins.open', mock_open(read_data=sample_csv_content)):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200)
            importer.run_import()

            # Check the arguments passed to import_contacts_batch
            # First batch should have 200 contacts
            first_call_args = mock_mautic_api_client.import_contacts_batch.call_args_list[0].args[0]
            assert len(first_call_args) == 200
            # Second batch should have 200 contacts
            second_call_args = mock_mautic_api_client.import_contacts_batch.call_args_list[1].args[0]
            assert len(second_call_args) == 200
            # Third batch should have 100 contacts (500 - 200 - 200)
            third_call_args = mock_mautic_api_client.import_contacts_batch.call_args_list[2].args[0]
            assert len(third_call_args) == 100

    def test_should_handle_rate_limiting_with_retries(self, mock_mautic_api_client, mock_progress_tracker, mock_logger, mock_sleep, sample_csv_content):
        """
        [AC 4] Should handle Mautic API rate limiting (HTTP 429) with retries and exponential backoff.
        Mocks a rate limit error and verifies the retry mechanism.
        """
        csv_path = "cleaned_leads.csv"
        # Simulate a 429 (Too Many Requests) on the first attempt, then success
        mock_mautic_api_client.import_contacts_batch.side_effect = [
            MagicMock(status_code=429, json=lambda: {'error': 'Rate limit exceeded'}),
            {'created': 200, 'updated': 0, 'failed': 0, 'results': [{'id': i} for i in range(200)]}
        ]

        with patch('builtins.open', mock_open(read_data=sample_csv_content)):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200, max_retries=1)
            importer.run_import()

            # Expect 2 calls for the first batch (initial failure + retry success)
            # and then the subsequent batches will be called once each
            assert mock_mautic_api_client.import_contacts_batch.call_count == (1 + 1) + 2 # Initial call + retry, then 2 more batches
            assert mock_sleep.call_count >= 1 # Should have slept at least once for retry

    def test_should_handle_api_server_errors_with_retries(self, mock_mautic_api_client, mock_progress_tracker, mock_logger, mock_sleep, sample_csv_content):
        """
        [AC 4] Should handle transient Mautic API server errors (HTTP 5xx) with retries.
        Mocks a server error and verifies the retry mechanism.
        """
        csv_path = "cleaned_leads.csv"
        # Simulate a 500 (Internal Server Error) on the first attempt, then success
        mock_mautic_api_client.import_contacts_batch.side_effect = [
            MagicMock(status_code=500, json=lambda: {'error': 'Server error'}),
            {'created': 200, 'updated': 0, 'failed': 0, 'results': [{'id': i} for i in range(200)]}
        ]

        with patch('builtins.open', mock_open(read_data=sample_csv_content)):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200, max_retries=1)
            importer.run_import()

            assert mock_mautic_api_client.import_contacts_batch.call_count == (1 + 1) + 2
            assert mock_sleep.call_count >= 1 # Should have slept at least once for retry

    def test_should_save_and_load_progress(self, mock_mautic_api_client, mock_progress_tracker, mock_logger, sample_csv_content):
        """
        [AC 5] Should correctly save and load import progress.
        Verifies that the ProgressTracker methods are called.
        """
        csv_path = "cleaned_leads.csv"
        # Simulate a partial import by having the progress tracker load_progress return a non-zero value
        mock_progress_tracker.load_progress.return_value = {'last_processed_row': 200}

        with patch('builtins.open', mock_open(read_data=sample_csv_content)):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200)
            importer.run_import()

            mock_progress_tracker.load_progress.assert_called_once()
            assert mock_progress_tracker.save_progress.call_count == 2 # Should save progress twice for the remaining 2 batches

    def test_should_resume_from_last_processed_batch(self, mock_mautic_api_client, mock_progress_tracker, mock_logger, sample_csv_content):
        """
        [AC 5] Should resume importing from the last saved progress point.
        Verifies that the import starts from the correct batch index.
        """
        csv_path = "cleaned_leads.csv"
        # Simulate that the first batch (rows 0-199) has already been processed
        mock_progress_tracker.load_progress.return_value = {'last_processed_row': 200}

        with patch('builtins.open', mock_open(read_data=sample_csv_content)):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200)
            importer.run_import()

            # Only the remaining 2 batches should be processed
            assert mock_mautic_api_client.import_contacts_batch.call_count == 2
            # Verify the content of the first call (which should be the second batch from the CSV)
            second_batch_contacts = mock_mautic_api_client.import_contacts_batch.call_args_list[0].args[0]
            assert second_batch_contacts[0]['email'] == 'test200@example.com' # Should start from contact 200

    def test_should_log_batch_results_correctly(self, mock_mautic_api_client, mock_progress_tracker, mock_logger, sample_csv_content):
        """
        [AC 6] Should log detailed results including created, updated, and failed contacts per batch.
        Verifies that the logger is called with appropriate messages.
        """
        csv_path = "cleaned_leads.csv"
        # Simulate some failures in one batch
        mock_mautic_api_client.import_contacts_batch.side_effect = [
            {'created': 190, 'updated': 5, 'failed': 5, 'results': [{'id': i} for i in range(190)] + [{'error': 'invalid'} for _ in range(10)]},
            {'created': 200, 'updated': 0, 'failed': 0, 'results': [{'id': i} for i in range(200)]},
            {'created': 100, 'updated': 0, 'failed': 0, 'results': [{'id': i} for i in range(100)]}
        ]

        with patch('builtins.open', mock_open(read_data=sample_csv_content)):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200)
            importer.run_import()

            # Check for specific log messages
            mock_logger.info.assert_any_call(
                "Batch processed: Created=190, Updated=5, Failed=5, Total=200"
            )
            mock_logger.error.assert_any_call(
                "Failed to import some contacts in batch. Details: [{'error': 'invalid'}, {'error': 'invalid'}, {'error': 'invalid'}, {'error': 'invalid'}, {'error': 'invalid'}]"
            )
            # Ensure other batches also logged successfully
            mock_logger.info.assert_any_call(
                "Batch processed: Created=200, Updated=0, Failed=0, Total=200"
            )
            mock_logger.info.assert_any_call(
                "Batch processed: Created=100, Updated=0, Failed=0, Total=100"
            )
            mock_logger.info.assert_any_call(
                "Import process completed. Total contacts: Created=490, Updated=5, Failed=5"
            )
            assert mock_logger.info.call_count >= 4
            assert mock_logger.error.call_count >= 1

    def test_should_handle_empty_csv_file(self, mock_mautic_api_client, mock_progress_tracker, mock_logger):
        """
        Edge Case: Empty input CSV file.
        The script should handle an empty CSV gracefully and not attempt any API calls.
        """
        csv_path = "empty_leads.csv"
        with patch('builtins.open', mock_open(read_data="email,firstname,lastname\n")):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200)
            importer.run_import()

            mock_mautic_api_client.import_contacts_batch.assert_not_called()
            mock_progress_tracker.save_progress.assert_not_called()
            mock_logger.info.assert_any_call("No leads found in CSV to import.")
            mock_logger.info.assert_any_call("Import process completed. Total contacts: Created=0, Updated=0, Failed=0")


    def test_should_handle_csv_fewer_than_batch_size(self, mock_mautic_api_client, mock_progress_tracker, mock_logger):
        """
        Edge Case: CSV file with fewer contacts than the batch size.
        Should import the single, smaller batch successfully.
        """
        csv_path = "small_leads.csv"
        small_csv = "email,firstname,lastname\n" + "\n".join([f"test{i}@example.com,Small,User{i}" for i in range(50)]) + "\n"
        with patch('builtins.open', mock_open(read_data=small_csv)):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200)
            importer.run_import()

            mock_mautic_api_client.import_contacts_batch.assert_called_once()
            assert len(mock_mautic_api_client.import_contacts_batch.call_args.args[0]) == 50
            mock_progress_tracker.save_progress.assert_called_once()
            mock_logger.info.assert_any_call(
                "Batch processed: Created=50, Updated=0, Failed=0, Total=50"
            )
            mock_logger.info.assert_any_call("Import process completed. Total contacts: Created=50, Updated=0, Failed=0")

    def test_should_handle_all_contacts_fail(self, mock_mautic_api_client, mock_progress_tracker, mock_logger, sample_csv_content):
        """
        Edge Case: All contacts fail during API import (e.g., due to invalid data).
        The script should log all failures and correctly tally them.
        """
        csv_path = "failing_leads.csv"
        mock_mautic_api_client.import_contacts_batch.return_value = {
            'created': 0, 'updated': 0, 'failed': 200, 'results': [{'error': 'invalid'} for _ in range(200)]
        }
        mock_mautic_api_client.import_contacts_batch.side_effect = [
            {'created': 0, 'updated': 0, 'failed': 200, 'results': [{'error': 'invalid'} for _ in range(200)]},
            {'created': 0, 'updated': 0, 'failed': 200, 'results': [{'error': 'invalid'} for _ in range(200)]},
            {'created': 0, 'updated': 0, 'failed': 100, 'results': [{'error': 'invalid'} for _ in range(100)]},
        ]

        with patch('builtins.open', mock_open(read_data=sample_csv_content)):
            importer = LeadImporter(csv_path, mock_mautic_api_client, mock_progress_tracker, mock_logger, batch_size=200)
            importer.run_import()

            assert mock_mautic_api_client.import_contacts_batch.call_count == 3
            mock_logger.error.assert_any_call(
                "Failed to import some contacts in batch. Details: [{'error': 'invalid'}, {'error': 'invalid'}, {'error': 'invalid'}, {'error': 'invalid'}, {'error': 'invalid'}]"
            )
            mock_logger.info.assert_any_call(
                "Import process completed. Total contacts: Created=0, Updated=0, Failed=500"
            )
            
# This is critical for TDD-RED-CHECK. It ensures a non-zero exit code if tests fail.
if __name__ == "__main__":
    pytest.main([__file__])
    # The above pytest.main should ideally be enough for the orchestrator to detect failure.
    # However, if for some reason it doesn't propagate a non-zero exit code,
    # adding a explicit sys.exit(1) on failure would guarantee it.
    # For now, relying on pytest's default behavior for import errors.
