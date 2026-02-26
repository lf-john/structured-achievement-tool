import requests
import os

class MauticApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def create_contact(self, payload: dict) -> dict:
        endpoint = f"{self.base_url}/api/contacts/new"
        print(f"Simulating POST request to {endpoint} with payload: {payload}")
        try:
            # response = requests.post(endpoint, headers=self.headers, json=payload)
            # response.raise_for_status()
            # return response.json()
            dummy_id = os.urandom(4).hex()
            print(f"Simulated Mautic contact created with ID: {dummy_id}")
            return {"contact": {"id": dummy_id, **payload}, "status": "success"}
        except requests.exceptions.RequestException as e:
            print(f"Error creating Mautic contact: {e}")
            raise

    def update_contact(self, contact_id: int, payload: dict) -> dict:
        endpoint = f"{self.base_url}/api/contacts/{contact_id}/edit"
        print(f"Simulating PATCH/PUT request to {endpoint} for contact {contact_id} with payload: {payload}")
        try:
            # response = requests.patch(endpoint, headers=self.headers, json=payload)
            # response.raise_for_status()
            # return response.json()
            print(f"Simulated Mautic contact {contact_id} updated.")
            return {"contact": {"id": contact_id, **payload}, "status": "success"}
        except requests.exceptions.RequestException as e:
            print(f"Error updating Mautic contact {contact_id}: {e}")
            raise

    def get_recent_contact_activity(self, since_datetime=None) -> list:
        """
        Simulates fetching recent contact activity from Mautic.
        In a real scenario, this would call a Mautic API endpoint to retrieve recent events/activity.
        """
        print(f"Simulating fetching recent Mautic contact activity since {since_datetime}")
        # Placeholder for actual API call. Return mock data for now.
        return [
            {'event_type': 'email.open', 'contact_id': 1, 'details': {'email': 'test@example.com'}},
            {'event_type': 'email.click', 'contact_id': 2, 'details': {'url': 'http://example.com/link'}},
            {'event_type': 'form.submit', 'contact_id': 3, 'details': {'form_name': 'Contact Us', 'fields': {'name': 'John Doe'}}},
            {'event_type': 'email.open', 'contact_id': 101, 'details': {'email': 'new.contact@example.com'}} # New contact activity
        ]

    def create_segment(self, name: str, description: str, filters: list) -> dict:
        endpoint = f"{self.base_url}/api/segments"
        payload = {
            "name": name,
            "alias": name.lower().replace(" ", "-").replace("_", "-"),
            "description": description,
            "isPublished": True,
            "filters": filters
        }
        print(f"Simulating POST request to {endpoint} with payload: {payload}")
        # In a real scenario, this would be:
        # try:
        #     response = requests.post(endpoint, headers=self.headers, json=payload)
        #     response.raise_for_status()
        #     return response.json()
        # except requests.exceptions.RequestException as e:
        #     print(f"Error creating segment {name}: {e}")
        #     return {"error": str(e)}
        return {"simulated_success": True, "segment_name": name, "payload": payload}

    def get_segment_membership_count(self, segment_id: int) -> int:
        print(f"Simulating fetching membership count for segment ID {segment_id}")
        return 0 # Simulate no members for now
