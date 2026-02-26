import logging
from src.mautic.mautic_api_client import MauticApiClient

class MauticEngagementService:
    def __init__(self, mautic_client: MauticApiClient):
        self.mautic_client = mautic_client
        logging.info("MauticEngagementService initialized with MauticApiClient.")

    def get_new_engagement_data(self) -> list:
        """
        Fetches new engagement data from Mautic using the MauticApiClient.
        """
        logging.info("Fetching new engagement data from Mautic via API client.")
        # In a real scenario, we might pass a 'since' parameter to get only new data
        return self.mautic_client.get_recent_contact_activity()
