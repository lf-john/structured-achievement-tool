# scripts/mautic/create_fields.py
import os
import sys
import requests
from requests.auth import HTTPBasicAuth
from field_definitions import CUSTOM_FIELDS

# Mautic credentials from environment variables
MAUTIC_URL = os.getenv("MAUTIC_URL")
MAUTIC_USERNAME = os.getenv("MAUTIC_USERNAME")
MAUTIC_PASSWORD = os.getenv("MAUTIC_PASSWORD")

# Add script directory to path to import field_definitions
sys.path.append(os.path.dirname(__file__))

if not all([MAUTIC_URL, MAUTIC_USERNAME, MAUTIC_PASSWORD]):
    print("Error: Mautic environment variables (MAUTIC_URL, MAUTIC_USERNAME, MAUTIC_PASSWORD) are not set.")
    exit(1)

auth = HTTPBasicAuth(MAUTIC_USERNAME, MAUTIC_PASSWORD)
headers = {"Content-Type": "application/json"}

def get_existing_fields():
    """Fetches existing contact fields to avoid creating duplicates."""
    url = f"{MAUTIC_URL}/api/fields/contact"
    try:
        response = requests.get(url, auth=auth, headers=headers, timeout=10)
        response.raise_for_status()
        return {field['alias'] for field in response.json().get('fields', [])}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching existing fields: {e}")
        exit(1)

def create_fields():
    """Creates custom fields in Mautic based on definitions."""
    existing_aliases = get_existing_fields()
    print(f"Found existing fields: {existing_aliases}")

    url = f"{MAUTIC_URL}/api/fields/contact/new"

    for alias, definition in CUSTOM_FIELDS.items():
        if alias in existing_aliases:
            print(f"Field '{alias}' already exists. Skipping.")
            continue

        payload = {
            "label": definition["label"],
            "alias": alias,
            "type": definition["type"],
            "object": "contact",
        }
        if "properties" in definition:
            payload["properties"] = definition["properties"]
        
        try:
            print(f"Creating field '{alias}'...")
            response = requests.post(url, auth=auth, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            print(f"Successfully created field '{alias}'.")
        except requests.exceptions.RequestException as e:
            print(f"Error creating field '{alias}': {e}")
            if e.response:
                print(f"Response body: {e.response.text}")
    
    print("
Field creation process complete.")

if __name__ == "__main__":
    create_fields()
