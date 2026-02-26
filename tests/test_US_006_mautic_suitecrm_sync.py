import unittest
from unittest.mock import MagicMock, patch
import os

# Import the services to be tested
from src.mautic.mautic_api_client import MauticApiClient
from src.mautic.suitecrm_client import SuiteCRMClient
from src.mautic.engagement_data_mapper import EngagementDataMapper
from src.mautic.mautic_engagement_service import MauticEngagementService
from src.mautic.sync_service import MauticSuiteCRMSyncService

class TestUS006MauticSuiteCRMSync(unittest.TestCase):

    def setUp(self):
        # Mock environment variables for client initialization
        os.environ['MAUTIC_BASE_URL'] = 'http://mautic.mock'
        os.environ['MAUTIC_API_KEY'] = 'mautic_api_key'
        os.environ['SUITECRM_BASE_URL'] = 'http://suitecrm.mock'
        os.environ['SUITECRM_API_KEY'] = 'suitecrm_api_key'

        self.mock_mautic_client = MagicMock(spec=MauticApiClient)
        self.mock_suitecrm_client = MagicMock(spec=SuiteCRMClient)
        self.mock_engagement_data_mapper = MagicMock(spec=EngagementDataMapper)
        self.mock_mautic_engagement_service = MagicMock(spec=MauticEngagementService)

        self.sync_service = MauticSuiteCRMSyncService(
            mautic_client=self.mock_mautic_client,
            suitecrm_client=self.mock_suitecrm_client,
            mautic_engagement_service=self.mock_mautic_engagement_service,
            engagement_data_mapper=self.mock_engagement_data_mapper
        )

    def tearDown(self):
        del os.environ['MAUTIC_BASE_URL']
        del os.environ['MAUTIC_API_KEY']
        del os.environ['SUITECRM_BASE_URL']
        del os.environ['SUITECRM_API_KEY']

    def test_ac1_new_contact_suitecrm_to_mautic(self):
        """AC1: New contact in SuiteCRM appears in Mautic."""
        suitecrm_contact = {
            "id": "suitecrm_123",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com"
        }
        self.mock_mautic_client.create_contact.return_value = {"contact": {"id": 1, "email": "john.doe@example.com"}, "status": "success"}

        response = self.sync_service.sync_suitecrm_to_mautic(suitecrm_contact)

        self.mock_mautic_client.create_contact.assert_called_once_with({
            "firstname": "John",
            "lastname": "Doe",
            "email": "john.doe@example.com"
        })
        self.assertIn("status", response)
        self.assertEqual(response["status"], "success")

    def test_ac2_new_contact_mautic_to_suitecrm(self):
        """AC2: New contact in Mautic appears in SuiteCRM."""
        mautic_contact = {
            "id": 456,
            "firstname": "Jane",
            "lastname": "Smith",
            "email": "jane.smith@example.com"
        }
        self.mock_suitecrm_client.create_contact.return_value = {"id": "suitecrm_456", "status": "success"}

        response = self.sync_service.sync_mautic_to_suitecrm(mautic_contact)

        self.mock_suitecrm_client.create_contact.assert_called_once_with({
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane.smith@example.com"
        })
        self.assertIn("status", response)
        self.assertEqual(response["status"], "success")

    def test_ac3_field_updates_bidirectionally_suitecrm_to_mautic(self):
        """AC3: Field updates propagate bidirectionally (SuiteCRM to Mautic)."""
        suitecrm_contact = {
            "id": "suitecrm_123",
            "first_name": "Jonathan", # Updated name
            "last_name": "Doe",
            "email": "john.doe@example.com"
        }
        mautic_id = 1
        self.mock_mautic_client.update_contact.return_value = {"contact": {"id": mautic_id, "firstname": "Jonathan"}, "status": "success"}

        response = self.sync_service.sync_suitecrm_to_mautic(suitecrm_contact, mautic_contact_id=mautic_id)

        self.mock_mautic_client.update_contact.assert_called_once_with(mautic_id, {
            "firstname": "Jonathan",
            "lastname": "Doe",
            "email": "john.doe@example.com"
        })
        self.assertIn("status", response)
        self.assertEqual(response["status"], "success")

    def test_ac3_field_updates_bidirectionally_mautic_to_suitecrm(self):
        """AC3: Field updates propagate bidirectionally (Mautic to SuiteCRM)."""
        mautic_contact = {
            "id": 456,
            "firstname": "Janet", # Updated name
            "lastname": "Smith",
            "email": "jane.smith@example.com"
        }
        suitecrm_id = "suitecrm_456"
        self.mock_suitecrm_client.update_contact.return_value = {"id": suitecrm_id, "status": "success"}

        response = self.sync_service.sync_mautic_to_suitecrm(mautic_contact, suitecrm_contact_id=suitecrm_id)

        self.mock_suitecrm_client.update_contact.assert_called_once_with(suitecrm_id, {
            "first_name": "Janet",
            "last_name": "Smith",
            "email": "jane.smith@example.com"
        })
        self.assertIn("status", response)
        self.assertEqual(response["status"], "success")

    def test_ac4_simulated_email_engagement_appears_in_suitecrm(self):
        """AC4: Simulated email engagement appears in SuiteCRM."""
        mock_engagement_data = [
            {'event_type': 'email.open', 'contact_id': 1, 'details': {'email': 'test@example.com'}},
            {'event_type': 'email.click', 'contact_id': 2, 'details': {'url': 'http://example.com/link'}}
        ]
        self.mock_mautic_engagement_service.get_new_engagement_data.return_value = mock_engagement_data
        
        self.mock_engagement_data_mapper.map_to_suitecrm_format.side_effect = [
            {'last_email_open': '2026-02-26', 'email': 'test@example.com'}, # for contact 1
            {'last_email_click': '2026-02-26', 'last_clicked_url': 'http://example.com/link', 'email': 'test2@example.com'} # for contact 2
        ]
        self.mock_suitecrm_client.update_contact.return_value = {"status": "success"}

        self.sync_service.sync_engagement_to_suitecrm()

        self.mock_mautic_engagement_service.get_new_engagement_data.assert_called_once()
        self.assertEqual(self.mock_engagement_data_mapper.map_to_suitecrm_format.call_count, len(mock_engagement_data))
        self.assertEqual(self.mock_suitecrm_client.update_contact.call_count, len(mock_engagement_data))

        # Verify calls to update_contact
        self.mock_suitecrm_client.update_contact.assert_any_call(
            '1', {'last_email_open': '2026-02-26', 'email': 'test@example.com'}
        )
        self.mock_suitecrm_client.update_contact.assert_any_call(
            '2', {'last_email_click': '2026-02-26', 'last_clicked_url': 'http://example.com/link', 'email': 'test2@example.com'}
        )
