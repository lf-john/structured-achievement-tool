import logging
from src.mautic.mautic_engagement_service import MauticEngagementService
from src.mautic.suitecrm_client import SuiteCRMClient
from src.mautic.engagement_data_mapper import EngagementDataMapper

class MauticSuiteCRMSyncService:
    def __init__(self, mautic_engagement_service: MauticEngagementService,
                 suitecrm_client: SuiteCRMClient,
                 engagement_data_mapper: EngagementDataMapper):
        self.mautic_engagement_service = mautic_engagement_service
        self.suitecrm_client = suitecrm_client
        self.engagement_data_mapper = engagement_data_mapper

    def sync_engagement_data(self):
        try:
            engagement_data = self.mautic_engagement_service.get_new_engagement_data()
            if not engagement_data:
                logging.info("No new engagement data from Mautic to sync.")
                return

            for data_item in engagement_data:
                contact_id = data_item.get('contact_id')
                if not contact_id:
                    logging.warning(f"Engagement data item missing contact_id, skipping: {data_item}")
                    continue

                try:
                    suitecrm_payload = self.engagement_data_mapper.map_to_suitecrm_format(data_item)
                    self.suitecrm_client.update_contact(contact_id, suitecrm_payload)
                    logging.info(f"Successfully synced engagement data for contact {contact_id}.")
                except Exception as e:
                    logging.error(f"Error updating SuiteCRM contact {contact_id}: {e}", exc_info=True)

        except Exception as e:
            logging.error(f"Error syncing Mautic engagement data: {e}", exc_info=True)
