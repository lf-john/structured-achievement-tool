import logging
from typing import Any

from src.mautic.engagement_data_mapper import EngagementDataMapper
from src.mautic.mautic_api_client import MauticApiClient
from src.mautic.mautic_engagement_service import MauticEngagementService
from src.mautic.suitecrm_client import SuiteCRMClient

logger = logging.getLogger(__name__)

class MauticSuiteCRMSyncService:
    def __init__(self, mautic_client: MauticApiClient, suitecrm_client: SuiteCRMClient, \
                 mautic_engagement_service: MauticEngagementService, engagement_data_mapper: EngagementDataMapper):
        self.mautic_client = mautic_client
        self.suitecrm_client = suitecrm_client
        self.mautic_engagement_service = mautic_engagement_service
        self.engagement_data_mapper = engagement_data_mapper
        logger.info("MauticSuiteCRMSyncService initialized with Mautic and SuiteCRM clients, engagement service, and data mapper.")

    def _map_suitecrm_to_mautic(self, suitecrm_contact: dict[str, Any]) -> dict[str, Any]:
        """
        Maps SuiteCRM contact data to Mautic contact data format.
        """
        mautic_contact = {
            "firstname": suitecrm_contact.get("first_name"),
            "lastname": suitecrm_contact.get("last_name"),
            "email": suitecrm_contact.get("email"),
            # Add other field mappings as needed
        }
        logger.debug(f"Mapped SuiteCRM contact {suitecrm_contact.get('id')} to Mautic format.")
        return {k: v for k, v in mautic_contact.items() if v is not None}

    def _map_mautic_to_suitecrm(self, mautic_contact: dict[str, Any]) -> dict[str, Any]:
        """
        Maps Mautic contact data to SuiteCRM contact data format.
        """
        suitecrm_contact = {
            "first_name": mautic_contact.get("firstname"),
            "last_name": mautic_contact.get("lastname"),
            "email": mautic_contact.get("email"),
            # Add other field mappings as needed
        }
        logger.debug(f"Mapped Mautic contact {mautic_contact.get('id')} to SuiteCRM format.")
        return {k: v for k, v in suitecrm_contact.items() if v is not None}

    def sync_suitecrm_to_mautic(self, suitecrm_contact_data: dict[str, Any], mautic_contact_id: int = None):
        """
        Synchronizes a SuiteCRM contact to Mautic.
        If mautic_contact_id is provided, updates the existing contact in Mautic.
        Otherwise, creates a new contact in Mautic.
        """
        logger.info(f"Attempting to sync SuiteCRM contact {suitecrm_contact_data.get('id')} to Mautic.")
        mautic_payload = self._map_suitecrm_to_mautic(suitecrm_contact_data)

        if mautic_contact_id:
            # Update existing Mautic contact
            try:
                response = self.mautic_client.update_contact(mautic_contact_id, mautic_payload)
                logger.info(f"Updated Mautic contact {mautic_contact_id} from SuiteCRM. Response: {response}")
                return response
            except Exception as e:
                logger.error(f"Failed to update Mautic contact {mautic_contact_id} from SuiteCRM: {e}")
                raise
        else:
            # Create new Mautic contact
            try:
                response = self.mautic_client.create_contact(mautic_payload)
                logger.info(f"Created Mautic contact from SuiteCRM. Response: {response}")
                return response
            except Exception as e:
                logger.error(f"Failed to create Mautic contact from SuiteCRM: {e}")
                raise

    def sync_mautic_to_suitecrm(self, mautic_contact_data: dict[str, Any], suitecrm_contact_id: str = None):
        """
        Synchronizes a Mautic contact to SuiteCRM.
        If suitecrm_contact_id is provided, updates the existing contact in SuiteCRM.
        Otherwise, creates a new contact in SuiteCRM.
        """
        logger.info(f"Attempting to sync Mautic contact {mautic_contact_data.get('id')} to SuiteCRM.")
        suitecrm_payload = self._map_mautic_to_suitecrm(mautic_contact_data)

        if suitecrm_contact_id:
            # Update existing SuiteCRM contact
            try:
                response = self.suitecrm_client.update_contact(suitecrm_contact_id, suitecrm_payload)
                logger.info(f"Updated SuiteCRM contact {suitecrm_contact_id} from Mautic. Response: {response}")
                return response
            except Exception as e:
                logger.error(f"Failed to update SuiteCRM contact {suitecrm_contact_id} from Mautic: {e}")
                raise
        else:
            # Create new SuiteCRM contact
            try:
                response = self.suitecrm_client.create_contact(suitecrm_payload)
                logger.info(f"Created SuiteCRM contact from Mautic. Response: {response}")
                return response
            except Exception as e:
                logger.error(f"Failed to create SuiteCRM contact from Mautic: {e}")
                raise

    def sync_engagement_to_suitecrm(self):
        """
        Fetches new engagement data from Mautic, maps it to SuiteCRM format, and updates SuiteCRM.
        """
        logger.info("Starting synchronization of Mautic engagement data to SuiteCRM.")
        engagement_data = self.mautic_engagement_service.get_new_engagement_data()

        if not engagement_data:
            logger.info("No new Mautic engagement data to sync.")
            return

        for engagement_record in engagement_data:
            contact_id = engagement_record.get('contact_id')
            if not contact_id:
                logger.warning(f"Engagement record missing contact_id, skipping: {engagement_record}")
                continue

            suitecrm_payload = self.engagement_data_mapper.map_to_suitecrm_format(engagement_record)
            if not suitecrm_payload: # If mapper returns empty, nothing to update
                logger.info(f"No SuiteCRM relevant data mapped for engagement record: {engagement_record}")
                continue

            try:
                # In a real scenario, we'd need to link Mautic contact_id to SuiteCRM contact_id
                # For now, we'll assume a direct mapping or that SuiteCRM can handle updates by email/id
                # For demonstration, we'll just use the Mautic contact_id as a dummy SuiteCRM contact_id
                self.suitecrm_client.update_contact(str(contact_id), suitecrm_payload)
                logger.info(f"Successfully synced engagement for Mautic contact {contact_id} to SuiteCRM.")
            except Exception as e:
                logger.error(f"Failed to sync engagement for Mautic contact {contact_id} to SuiteCRM: {e}")


