# src/utils/mautic_client.py

import requests


class MauticClient:
    def __init__(self, api_url: str, token: str):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {token}"}

    def update_contact_score(self, contact_id: int, score: int) -> bool:
        """
        Updates a Mautic contact's lead_score field.
        """
        endpoint = f"{self.api_url}/contacts/{contact_id}/edit"
        payload = {"lead_score": score}
        try:
            response = requests.patch(endpoint, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            print(f"Successfully updated Mautic contact {contact_id} with score {score}")
            return True
        except requests.RequestException as e:
            print(f"Error updating Mautic contact {contact_id}: {e}")
            return False
