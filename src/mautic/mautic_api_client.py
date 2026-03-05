import os

import requests


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

    def get_contacts(self, limit=1, start=0, search=None, order_by=None, order_direction='asc') -> dict:
        print(f"Simulating GET request to /api/contacts with limit={limit}, start={start}, search={search}")
        # Placeholder for actual API call. Return mock data for now.
        # This mock data needs to be flexible enough for testing various scenarios.
        dummy_contacts = {
            "1": {"id": 1, "firstname": "John", "lastname": "Doe", "email": "john@example.com", "company": "ABC Inc.", "fields": {"core": {"lead_score": {"value": 10}}}},
            "2": {"id": 2, "firstname": "Jane", "lastname": "Smith", "email": "jane@example.com", "company": "XYZ Corp.", "fields": {"core": {"lead_score": {"value": 20}}}},
            "3": {"id": 3, "firstname": "Peter", "lastname": "Jones", "email": "peter@example.com", "company": "123 Corp.", "fields": {"core": {"lead_score": {"value": 15}}}},
            "4": {"id": 4, "firstname": "Alice", "lastname": "Brown", "email": "alice@example.com", "company": "Data LLC", "fields": {"core": {"lead_score": {"value": 25}}}}
        }

        # Apply basic filtering for simulation
        filtered_contacts = {}
        for contact_id, contact_data in dummy_contacts.items():
            if search:
                if search.lower() in str(contact_data.values()).lower():
                    filtered_contacts[contact_id] = contact_data
            else:
                filtered_contacts[contact_id] = contact_data

        total_count = len(filtered_contacts)

        # Apply limit and start for simulation
        contacts_list = list(filtered_contacts.values())
        if limit is not None and limit != 0:
            paginated_contacts = contacts_list[start : start + limit]
        else: # If limit is 0 or None, return all (for duplicate check)
            paginated_contacts = contacts_list[start:]


        # Convert back to dict format for response
        contacts_dict = {str(c['id']): c for c in paginated_contacts}

        return {"contacts": contacts_dict, "totalCount": total_count}

    def get_segments(self, limit=50, start=0) -> dict:
        print(f"Simulating GET request to /api/segments with limit={limit}, start={start}")
        dummy_segments = {
            "1": {"id": 1, "name": "Segment A", "contacts": 10},
            "2": {"id": 2, "name": "Segment B", "contacts": 5},
            "3": {"id": 3, "name": "Segment C", "contacts": 0}
        }
        segments_list = list(dummy_segments.values())
        paginated_segments = segments_list[start : start + limit]
        segments_dict = {str(s['id']): s for s in paginated_segments}
        return {"segments": segments_dict, "totalCount": len(dummy_segments)}

    def get_contact_by_id(self, contact_id: int) -> dict:
        print(f"Simulating GET request to /api/contacts/{contact_id}")
        dummy_contacts = {
            1: {"id": 1, "firstname": "John", "lastname": "Doe", "email": "john@example.com", "fields": {"core": {"lead_score": {"value": 10}}}},
            2: {"id": 2, "firstname": "Jane", "lastname": "Smith", "email": "jane@example.com", "fields": {"core": {"lead_score": {"value": 20}}}},
            3: {"id": 3, "firstname": "Peter", "lastname": "Jones", "email": "peter@example.com", "fields": {"core": {"lead_score": {"value": 15}}}}
        }
        contact = dummy_contacts.get(contact_id)
        if contact:
            return {"contact": contact}
        else:
            return {"error": f"Contact with ID {contact_id} not found"}
