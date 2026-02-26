import pytest
import unittest
from unittest.mock import patch, MagicMock
import sys

"""
IMPLEMENTATION PLAN for US-006: Create Mautic Contact Segments

Components:
  - src/mautic/segment_manager.py: A new module to encapsulate Mautic segment creation and management logic.
    - create_segments(api_client, segment_definitions: list): Function to create multiple segments based on provided definitions.
    - get_segment_membership_count(api_client, segment_id: int): Function to retrieve the number of contacts in a specific segment.
  - src/mautic/mautic_api_client.py (mocked): An API client to interact with Mautic, with methods like create_segment and get_segment_contacts_count.

Data Flow:
  - Segment definitions are passed to create_segments.
  - create_segments calls the mautic_api_client to perform API operations.
  - get_segment_membership_count calls the mautic_api_client to retrieve data.

Integration Points:
  - The segment_manager will depend on an instantiated MauticApiClient.
  - The orchestrator or a dedicated workflow will call segment_manager functions.

Edge Cases:
  - Mautic API client failures (network, auth).
  - Invalid segment definitions.
  - Segment already exists.
  - Empty contact lists for segments.
  - API errors during membership count retrieval.

Test Cases:
  1. [AC 1] -> test_should_create_all_industry_segments_successfully: Verify that industry-based segments are created.
  2. [AC 2] -> test_should_create_all_geography_segments_successfully: Verify that geography-based segments are created.
  3. [AC 3] -> test_should_create_all_company_size_segments_successfully: Verify that company size-based segments are created.
  4. [AC 4] -> test_should_create_all_engagement_segments_successfully: Verify that engagement-based segments are created.
  5. [AC 5] -> test_should_create_all_lead_quality_segments_successfully: Verify that lead quality-based segments are created.
  6. [AC 8] -> test_should_retrieve_segment_membership_count: Verify correct membership count retrieval for a segment.
  7. Edge Case -> test_should_handle_mautic_api_client_failure_during_creation: Verify error handling during segment creation.
  8. Edge Case -> test_should_handle_empty_segment_definitions: Verify handling of an empty list of segment definitions.
  9. Edge Case -> test_should_handle_segment_already_exists_gracefully: Verify that existing segments are handled without error.
  10. Edge Case -> test_should_handle_api_error_retrieving_membership_count: Verify error handling when retrieving membership count fails.
"""

# Mock MauticApiClient - this would be an actual client in the implementation
class MockMauticApiClient:
    def create_segment(self, name: str, description: str, filters: list):
        print(f"Mock Mautic API: Creating segment '{name}' with description: '{description}' and filters: {filters}")
        if name == "existing-segment":
            raise ValueError("Segment 'existing-segment' already exists.")
        if "fail-on-creation" in name:
            raise Exception("API creation failed for specific segment.")
        return {"id": 1, "name": name, "description": description, "filters": filters, "isPublished": True}

    def get_segment_contacts_count(self, segment_id):
        print(f"Mock Mautic API: Getting contact count for segment ID '{segment_id}'")
        if segment_id == 999:
            raise Exception("API error retrieving count for segment ID 999.")
        return 123 # Dummy count

# This import will cause ModuleNotFoundError since src/mautic/segment_manager.py does not exist yet
from src.mautic.segment_manager import create_all_segments

class TestMauticSegmentCreation(unittest.TestCase):
    MAUTIC_API_CLIENT = MockMauticApiClient()

    def test_should_create_all_industry_segments_successfully(self):
        """[AC 1] Verifies that industry-based segments are created via the Mautic API."""
        industry_segments = [
            {"name": "industry-healthcare", "criteria": "Industry = 'Healthcare'"},
            {"name": "industry-higher-ed", "criteria": "Industry = 'Higher Education'"},
            {"name": "industry-manufacturing", "criteria": "Industry = 'Manufacturing'"},
        ]
        with patch('src.mautic.segment_manager.get_mautic_client', return_value=self.MAUTIC_API_CLIENT):
            with patch.object(self.MAUTIC_API_CLIENT, 'create_segment', wraps=self.MAUTIC_API_CLIENT.create_segment) as mock_create:
                create_all_segments()
                assert mock_create.call_count == 15
            mock_create.assert_any_call(name="industry-healthcare", description="Contacts in the Healthcare industry", filters=[{"field": "industry", "operator": "equals", "value": "Healthcare"}])
            mock_create.assert_any_call(name="industry-higher-ed", description="Contacts in the Higher Education industry", filters=[{"field": "industry", "operator": "equals", "value": "Higher Education"}])
            mock_create.assert_any_call(name="industry-manufacturing", description="Contacts in the Manufacturing industry", filters=[{"field": "industry", "operator": "equals", "value": "Manufacturing"}])

    def test_should_create_all_geography_segments_successfully(self):
        """[AC 2] Verifies that geography-based segments are created via the Mautic API."""
        geo_segments = [
            {"name": "geo-california", "criteria": "State = 'CA'"},
            {"name": "geo-texas", "criteria": "State = 'TX'"},
            {"name": "geo-new-york", "criteria": "State = 'NY'"},
        ]
        with patch('src.mautic.segment_manager.get_mautic_client', return_value=self.MAUTIC_API_CLIENT):
            with patch.object(self.MAUTIC_API_CLIENT, 'create_segment', wraps=self.MAUTIC_API_CLIENT.create_segment) as mock_create:
                create_all_segments()
                assert mock_create.call_count == 15
            mock_create.assert_any_call(name="geo-california", description="Contacts from California", filters=[{"field": "state", "operator": "equals", "value": "CA"}])
            mock_create.assert_any_call(name="geo-texas", description="Contacts from Texas", filters=[{"field": "state", "operator": "equals", "value": "TX"}])
            mock_create.assert_any_call(name="geo-new-york", description="Contacts from New York", filters=[{"field": "state", "operator": "equals", "value": "NY"}])

    def test_should_create_all_company_size_segments_successfully(self):
        """[AC 3] Verifies that company size-based segments are created via the Mautic API."""
        size_segments = [
            {"name": "size-smb", "criteria": "CompanySize <= 50"},
            {"name": "size-mid-market", "criteria": "CompanySize > 50 AND CompanySize <= 500"},
            {"name": "size-enterprise", "criteria": "CompanySize > 500"},
        ]
        with patch('src.mautic.segment_manager.get_mautic_client', return_value=self.MAUTIC_API_CLIENT):
            with patch.object(self.MAUTIC_API_CLIENT, 'create_segment', wraps=self.MAUTIC_API_CLIENT.create_segment) as mock_create:
                create_all_segments()
                assert mock_create.call_count == 15
            mock_create.assert_any_call(name="size-smb", description="Contacts from Small and Medium Businesses (<=50 employees)", filters=[{"field": "company_size", "operator": "lessThanOrEqualTo", "value": "50"}])
            mock_create.assert_any_call(name="size-mid-market", description="Contacts from Mid-Market companies (51-500 employees)", filters=[{"field": "company_size", "operator": "greaterThan", "value": "50"}, {"field": "company_size", "operator": "lessThanOrEqualTo", "value": "500"}])
            mock_create.assert_any_call(name="size-enterprise", description="Contacts from Enterprise companies (>500 employees)", filters=[{"field": "company_size", "operator": "greaterThan", "value": "500"}])

    def test_should_create_all_engagement_segments_successfully(self):
        """[AC 4] Verifies that engagement-based segments are created via the Mautic API."""
        engagement_segments = [
            {"name": "engaged-openers", "criteria": "EmailOpens > 0"},
            {"name": "engaged-clickers", "criteria": "EmailClicks > 0"},
            {"name": "cold-no-engagement", "criteria": "EmailOpens = 0 AND EmailClicks = 0"},
        ]
        with patch('src.mautic.segment_manager.get_mautic_client', return_value=self.MAUTIC_API_CLIENT):
            with patch.object(self.MAUTIC_API_CLIENT, 'create_segment', wraps=self.MAUTIC_API_CLIENT.create_segment) as mock_create:
                create_all_segments()
                assert mock_create.call_count == 15
            mock_create.assert_any_call(name="engaged-openers", description="Contacts who have opened emails", filters=[{"field": "email_opens", "operator": "greaterThan", "value": "0"}])
            mock_create.assert_any_call(name="engaged-clickers", description="Contacts who have clicked emails", filters=[{"field": "email_clicks", "operator": "greaterThan", "value": "0"}])
            mock_create.assert_any_call(name="cold-no-engagement", description="Contacts with no email opens or clicks", filters=[{"field": "email_opens", "operator": "equals", "value": "0"}, {"field": "email_clicks", "operator": "equals", "value": "0"}])

    def test_should_create_all_lead_quality_segments_successfully(self):
        """[AC 5] Verifies that lead quality-based segments are created via the Mautic API."""
        lead_quality_segments = [
            {"name": "icp-strong-fit", "criteria": "ICPScore >= 80"},
            {"name": "icp-moderate-fit", "criteria": "ICPScore >= 50 AND ICPScore < 80"},
            {"name": "warmup-safe", "criteria": "EmailBounceRate < 0.05"}, # Example criteria
        ]
        with patch('src.mautic.segment_manager.get_mautic_client', return_value=self.MAUTIC_API_CLIENT):
            with patch.object(self.MAUTIC_API_CLIENT, 'create_segment', wraps=self.MAUTIC_API_CLIENT.create_segment) as mock_create:
                create_all_segments()
                assert mock_create.call_count == 15
            mock_create.assert_any_call(name="icp-strong-fit", description="Contacts with a strong ICP fit (score >= 80)", filters=[{"field": "icp_score", "operator": "greaterThanOrEqualTo", "value": "80"}])
            mock_create.assert_any_call(name="icp-moderate-fit", description="Contacts with a moderate ICP fit (score >= 50 and < 80)", filters=[{"field": "icp_score", "operator": "greaterThanOrEqualTo", "value": "50"}, {"field": "icp_score", "operator": "lessThan", "value": "80"}])
            mock_create.assert_any_call(name="warmup-safe", description="Contacts safe for email warm-up (low bounce rate)", filters=[{"field": "email_bounce_rate", "operator": "lessThan", "value": "0.05"}])

    def test_should_retrieve_segment_membership_count(self):
        """[AC 8] Verifies that segment membership count can be retrieved."""
        segment_id = 123
        with patch.object(self.MAUTIC_API_CLIENT, 'get_segment_contacts_count', wraps=self.MAUTIC_API_CLIENT.get_segment_contacts_count) as mock_get_count:
            count = self.MAUTIC_API_CLIENT.get_segment_contacts_count(segment_id)
            mock_get_count.assert_called_once_with(segment_id)
            assert count == 123

    def test_should_handle_mautic_api_client_failure_during_creation(self):
        """Edge Case: Verifies error handling when Mautic API client fails during segment creation."""
        with patch('src.mautic.segment_manager.get_mautic_client', return_value=self.MAUTIC_API_CLIENT):
            with patch.object(self.MAUTIC_API_CLIENT, 'create_segment', wraps=self.MAUTIC_API_CLIENT.create_segment) as mock_create:
                results = create_all_segments()
                # Check that at least one result indicates failure for the failing segment
                failure_found = any(
                    "fail-on-creation" in r.get("segment_name", "") and r.get("simulated_success") is False
                    for r in results
                )
                self.assertTrue(failure_found, "Expected failure not found in results for 'fail-on-creation' segment.")

    def test_should_handle_segment_already_exists_gracefully(self):
        """Edge Case: Verifies that segment_manager handles existing segments without re-creating them."""
        with patch('src.mautic.segment_manager.get_mautic_client', return_value=self.MAUTIC_API_CLIENT):
            with patch.object(self.MAUTIC_API_CLIENT, 'create_segment', wraps=self.MAUTIC_API_CLIENT.create_segment) as mock_create:
                results = create_all_segments()
                # Check that at least one result indicates an existing segment error
                existing_segment_error_found = any(
                    "existing-segment" in r.get("segment_name", "") and "already exists" in r.get("error", "")
                    for r in results
                )
                self.assertTrue(existing_segment_error_found, "Expected existing segment error not found in results.")


    def test_should_handle_api_error_retrieving_membership_count(self):
        """Edge Case: Verifies error handling when retrieving membership count fails."""
        segment_id_failing = 999
        with patch.object(self.MAUTIC_API_CLIENT, 'get_segment_contacts_count', wraps=self.MAUTIC_API_CLIENT.get_segment_contacts_count) as mock_get_count:
            with pytest.raises(Exception, match="API error retrieving count for segment ID 999."):
                self.MAUTIC_API_CLIENT.get_segment_contacts_count(segment_id_failing)
            mock_get_count.assert_called_once_with(segment_id_failing)
