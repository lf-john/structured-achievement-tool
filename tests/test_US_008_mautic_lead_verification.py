import pytest
import sys
from unittest.mock import MagicMock, patch

# Dummy default_api for patching purposes in TDD-RED phase
default_api = MagicMock()

"""
IMPLEMENTATION PLAN for US-008:

Components:
  - src/mautic/mautic_lead_verifier.py: A new module for Mautic lead verification logic.
    - MauticLeadVerificationService: A class to encapsulate all verification methods.
        - __init__(self, mautic_api_client: MauticApiClient): Initializes with a Mautic API client.
        - verify_total_contact_count(self, expected_count: int, excluded_records: int = 0) -> bool: Verifies total contact count.
        - verify_segment_counts(self, expected_segments: dict[str, int]) -> bool: Verifies counts for specified segments.
        - sample_contacts_for_field_mapping(self, sample_size: int = 10, fields_to_verify: list[str]) -> bool: Samples contacts and verifies field mapping.
        - confirm_demographic_lead_scores(self, sample_contact_ids: list[int], expected_scores: dict[int, dict[str, any]]) -> bool: Confirms lead scores for sample contacts.
        - confirm_no_duplicate_contacts(self) -> bool: Checks for duplicate contacts based on email.

Test Cases:
  1. [AC 1] -> test_should_verify_total_contact_count_match_expected_no_exclusions: Happy path, exact match.
  2. [AC 1] -> test_should_verify_total_contact_count_match_expected_with_exclusions: Happy path, with excluded records.
  3. [AC 1] -> test_should_fail_when_total_contact_count_mismatch: Mismatch in total count.
  4. [AC 1] -> test_should_handle_mautic_api_error_on_contact_count: API error during contact count retrieval.
  5. [AC 2] -> test_should_verify_segment_counts_all_reasonable_and_non_zero: Happy path for multiple segments.
  6. [AC 2] -> test_should_verify_segment_counts_with_expected_zero_segment: Happy path for an expected zero-count segment.
  7. [AC 2] -> test_should_fail_when_segment_count_mismatch: Mismatch in a segment count.
  8. [AC 2] -> test_should_fail_when_unexpected_zero_segment_count: Segment unexpectedly has zero contacts.
  9. [AC 2] -> test_should_handle_mautic_api_error_on_segment_count: API error during segment count retrieval.
  10. [AC 3] -> test_should_sample_contacts_and_verify_field_mapping_success: Happy path, all fields mapped correctly.
  11. [AC 3] -> test_should_fail_when_sample_contact_missing_expected_field: Sample contact missing a field.
  12. [AC 3] -> test_should_fail_when_sample_contact_field_value_mismatch: Sample contact field value mismatch.
  13. [AC 3] -> test_should_handle_not_enough_contacts_to_sample: Fewer contacts than sample size.
  14. [AC 4] -> test_should_confirm_demographic_lead_scores_applied_correctly: Happy path, scores match.
  15. [AC 4] -> test_should_fail_when_demographic_lead_score_missing: Missing lead score.
  16. [AC 4] -> test_should_fail_when_demographic_lead_score_mismatch: Lead score value mismatch.
  17. [AC 5] -> test_should_confirm_no_duplicate_contacts_found: Happy path, no duplicates.
  18. [AC 5] -> test_should_fail_when_duplicate_contacts_found: Duplicates found.
  19. [AC 5] -> test_should_handle_mautic_api_error_on_duplicate_check: API error during duplicate check.

Edge Cases:
  - Mautic API returns errors (e.g., network issues, invalid API key).
  - No contacts imported.
  - No segments found.
  - Sample contacts not found or missing expected fields/scores.
  - Deduplication logic leads to fewer contacts than expected (accounted for in `excluded_records`).
  - Empty or malformed responses from Mautic API.
"""

# Placeholder imports that are expected to fail, leading to TDD-RED state.
# The actual implementation will be in src/mautic/mautic_lead_verifier.py
try:
    from src.mautic.mautic_api_client import MauticApiClient # Existing client
    from src.mautic.mautic_lead_verifier import MauticLeadVerificationService
except ImportError:
    # Define mock classes/functions to allow tests to be written and explicitly fail later
    class MockMauticApiClient:
        def get_contacts(self, limit=1, start=0, search=None, order_by=None, order_direction='asc'):
            raise NotImplementedError("MauticApiClient.get_contacts is not implemented.")
        def get_segments(self, limit=50, start=0):
            raise NotImplementedError("MauticApiClient.get_segments is not implemented.")
        def get_contact_by_id(self, contact_id):
            raise NotImplementedError("MauticApiClient.get_contact_by_id is not implemented.")

    class MockMauticLeadVerificationService:
        def __init__(self, mautic_api_client):
            pass
        def verify_total_contact_count(self, expected_count, excluded_records=0):
            raise NotImplementedError("MauticLeadVerificationService.verify_total_contact_count is not implemented.")
        def verify_segment_counts(self, expected_segments):
            raise NotImplementedError("MauticLeadVerificationService.verify_segment_counts is not implemented.")
        def sample_contacts_for_field_mapping(self, sample_size=10, fields_to_verify=[]):
            raise NotImplementedError("MauticLeadVerificationService.sample_contacts_for_field_mapping is not implemented.")
        def confirm_demographic_lead_scores(self, sample_contact_ids, expected_scores):
            raise NotImplementedError("MauticLeadVerificationService.confirm_demographic_lead_scores is not implemented.")
        def confirm_no_duplicate_contacts(self):
            raise NotImplementedError("MauticLeadVerificationService.confirm_no_duplicate_contacts is not implemented.")

    MauticApiClient = MockMauticApiClient
    MauticLeadVerificationService = MockMauticLeadVerificationService


class TestMauticLeadVerificationService:
    @pytest.fixture
    def mock_mautic_api_client(self):
        return MagicMock(spec=MauticApiClient)

    @pytest.fixture
    def verifier_service(self, mock_mautic_api_client):
        return MauticLeadVerificationService(mautic_api_client=mock_mautic_api_client)

    # AC 1: Total contact count in Mautic verified to match expected (minus excluded records)
    def test_should_verify_total_contact_count_match_expected_no_exclusions(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contacts.return_value = {"contacts": {"1": {}, "2": {}, "3": {}}, "totalCount": 3}
        result = verifier_service.verify_total_contact_count(expected_count=3)
        mock_mautic_api_client.get_contacts.assert_called_once_with(limit=1) # Only fetch 1 contact to get totalCount
        assert result is True

    def test_should_verify_total_contact_count_match_expected_with_exclusions(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contacts.return_value = {"contacts": {"1": {}, "2": {}, "3": {}, "4": {}, "5": {}}, "totalCount": 5}
        result = verifier_service.verify_total_contact_count(expected_count=3, excluded_records=2)
        assert result is True

    def test_should_fail_when_total_contact_count_mismatch(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contacts.return_value = {"contacts": {"1": {}, "2": {}}, "totalCount": 2}
        result = verifier_service.verify_total_contact_count(expected_count=3)
        assert result is False

    def test_should_handle_mautic_api_error_on_contact_count(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contacts.side_effect = Exception("API Error")
        result = verifier_service.verify_total_contact_count(expected_count=3)
        assert result is False

    # AC 2: All segment counts verified to be reasonable and non-zero (unless expected)
    def test_should_verify_segment_counts_all_reasonable_and_non_zero(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_segments.return_value = {
            "segments": {
                "1": {"id": 1, "name": "Segment A", "contacts": 10},
                "2": {"id": 2, "name": "Segment B", "contacts": 5}
            }
        }
        expected_segments = {"Segment A": 10, "Segment B": 5}
        result = verifier_service.verify_segment_counts(expected_segments)
        mock_mautic_api_client.get_segments.assert_called_once_with(limit=50)
        assert result is True

    def test_should_verify_segment_counts_with_expected_zero_segment(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_segments.return_value = {
            "segments": {
                "1": {"id": 1, "name": "Segment A", "contacts": 10},
                "2": {"id": 2, "name": "Segment B", "contacts": 0}
            }
        }
        expected_segments = {"Segment A": 10, "Segment B": 0}
        result = verifier_service.verify_segment_counts(expected_segments)
        assert result is True

    def test_should_fail_when_segment_count_mismatch(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_segments.return_value = {
            "segments": {
                "1": {"id": 1, "name": "Segment A", "contacts": 10}
            }
        }
        expected_segments = {"Segment A": 9}
        result = verifier_service.verify_segment_counts(expected_segments)
        assert result is False

    def test_should_fail_when_unexpected_zero_segment_count(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_segments.return_value = {
            "segments": {
                "1": {"id": 1, "name": "Segment A", "contacts": 0}
            }
        }
        expected_segments = {"Segment A": 5} # Expected non-zero, but got zero
        result = verifier_service.verify_segment_counts(expected_segments)
        assert result is False

    def test_should_handle_mautic_api_error_on_segment_count(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_segments.side_effect = Exception("API Error")
        expected_segments = {"Segment A": 10}
        result = verifier_service.verify_segment_counts(expected_segments)
        assert result is False

    # AC 3: Sample of 10 contacts verified for correct field mapping
    def test_should_sample_contacts_and_verify_field_mapping_success(self, verifier_service, mock_mautic_api_client):
        # Mock get_contacts to return contacts with specific fields
        mock_mautic_api_client.get_contacts.return_value = {
            "contacts": {
                "1": {"id": 1, "firstname": "John", "lastname": "Doe", "email": "john@example.com", "company": "ABC Inc."},
                "2": {"id": 2, "firstname": "Jane", "lastname": "Smith", "email": "jane@example.com", "company": "XYZ Corp."}
            },
            "totalCount": 2
        }
        fields_to_verify = ["firstname", "lastname", "email", "company"]
        result = verifier_service.sample_contacts_for_field_mapping(sample_size=2, fields_to_verify=fields_to_verify)
        mock_mautic_api_client.get_contacts.assert_called_with(limit=2, start=0) # Asserting the sampling call
        assert result is True

    def test_should_fail_when_sample_contact_missing_expected_field(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contacts.return_value = {
            "contacts": {
                "1": {"id": 1, "firstname": "John", "email": "john@example.com"} # Missing 'lastname'
            },
            "totalCount": 1
        }
        fields_to_verify = ["firstname", "lastname", "email"]
        result = verifier_service.sample_contacts_for_field_mapping(sample_size=1, fields_to_verify=fields_to_verify)
        assert result is False

    def test_should_fail_when_sample_contact_field_value_mismatch(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contacts.return_value = {
            "contacts": {
                "1": {"id": 1, "firstname": "Jhn", "lastname": "Doe", "email": "john@example.com"} # Typo in firstname
            },
            "totalCount": 1
        }
        fields_to_verify = {"firstname": "John", "lastname": "Doe", "email": "john@example.com"} # Expect exact values
        # For simplicity in TDD-RED, assume sample_contacts_for_field_mapping will take dict as well
        # The actual implementation will iterate through samples and check if field is present.
        # This test will conceptually check if values match for a sample.
        result = verifier_service.sample_contacts_for_field_mapping(sample_size=1, fields_to_verify=fields_to_verify)
        assert result is False

    def test_should_handle_not_enough_contacts_to_sample(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contacts.return_value = {
            "contacts": {
                "1": {"id": 1, "firstname": "John", "lastname": "Doe", "email": "john@example.com"}
            },
            "totalCount": 1
        }
        fields_to_verify = ["firstname", "lastname", "email"]
        result = verifier_service.sample_contacts_for_field_mapping(sample_size=5, fields_to_verify=fields_to_verify)
        assert result is False

    # AC 4: Demographic lead scores confirmed to be applied correctly for sample contacts
    def test_should_confirm_demographic_lead_scores_applied_correctly(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contact_by_id.side_effect = [
            {"contact": {"id": 1, "fields": {"core": {"lead_score": {"value": 10}}}}},
            {"contact": {"id": 2, "fields": {"core": {"lead_score": {"value": 20}}}}}
        ]
        sample_contact_ids = [1, 2]
        expected_scores = {1: {"lead_score": 10}, 2: {"lead_score": 20}}
        result = verifier_service.confirm_demographic_lead_scores(sample_contact_ids, expected_scores)
        mock_mautic_api_client.get_contact_by_id.assert_any_call(1)
        mock_mautic_api_client.get_contact_by_id.assert_any_call(2)
        assert result is True

    def test_should_fail_when_demographic_lead_score_missing(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contact_by_id.return_value = {"contact": {"id": 1, "fields": {"core": {}}}} # Missing lead_score
        sample_contact_ids = [1]
        expected_scores = {1: {"lead_score": 10}}
        result = verifier_service.confirm_demographic_lead_scores(sample_contact_ids, expected_scores)
        assert result is False

    def test_should_fail_when_demographic_lead_score_mismatch(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contact_by_id.return_value = {"contact": {"id": 1, "fields": {"core": {"lead_score": {"value": 5}}}}} # Mismatch
        sample_contact_ids = [1]
        expected_scores = {1: {"lead_score": 10}}
        result = verifier_service.confirm_demographic_lead_scores(sample_contact_ids, expected_scores)
        assert result is False

    # AC 5: Absence of duplicate contacts confirmed via search or API check
    def test_should_confirm_no_duplicate_contacts_found(self, verifier_service, mock_mautic_api_client):
        # Mocking for no duplicates (all distinct emails)
        mock_mautic_api_client.get_contacts.return_value = {
            "contacts": {
                "1": {"id": 1, "email": "test1@example.com"},
                "2": {"id": 2, "email": "test2@example.com"},
                "totalCount": 2
            }
        }
        result = verifier_service.confirm_no_duplicate_contacts()
        mock_mautic_api_client.get_contacts.assert_called_with(limit=None) # Fetch all contacts to check duplicates
        assert result is True

    def test_should_fail_when_duplicate_contacts_found(self, verifier_service, mock_mautic_api_client):
        # Mocking for duplicates (same email for two contacts)
        mock_mautic_api_client.get_contacts.return_value = {
            "contacts": {
                "1": {"id": 1, "email": "duplicate@example.com"},
                "2": {"id": 2, "email": "duplicate@example.com"}
            },
            "totalCount": 2
        }
        result = verifier_service.confirm_no_duplicate_contacts()
        assert result is False

    def test_should_handle_mautic_api_error_on_duplicate_check(self, verifier_service, mock_mautic_api_client):
        mock_mautic_api_client.get_contacts.side_effect = Exception("API Error")
        result = verifier_service.confirm_no_duplicate_contacts()
        assert result is False

# This is critical for TDD-RED-CHECK. It ensures a non-zero exit code if tests fail.
if __name__ == "__main__":
    # Run pytest and exit with the appropriate code
    pytest_exit_code = pytest.main([__file__])
    sys.exit(pytest_exit_code)
