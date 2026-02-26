# scripts/mautic/verify_fields.py
import os
import sys
import requests
from requests.auth import HTTPBasicAuth


# Add script directory to path to import field_definitions
sys.path.append(os.path.dirname(__file__))
from field_definitions import CUSTOM_FIELDS


# Mautic credentials from environment variables
MAUTIC_URL = os.getenv("MAUTIC_URL")
MAUTIC_USERNAME = os.getenv("MAUTIC_USERNAME")
MAUTIC_PASSWORD = os.getenv("MAUTIC_PASSWORD")

if not all([MAUTIC_URL, MAUTIC_USERNAME, MAUTIC_PASSWORD]):
    print("Error: Mautic environment variables (MAUTIC_URL, MAUTIC_USERNAME, MAUTIC_PASSWORD) are not set.")
    sys.exit(1)

auth = HTTPBasicAuth(MAUTIC_USERNAME, MAUTIC_PASSWORD)
headers = {"Content-Type": "application/json"}

def verify_fields():
    """Verifies that all required custom fields exist in Mautic."""
    url = f"{MAUTIC_URL}/api/fields/contact"
    try:
        response = requests.get(url, auth=auth, headers=headers, timeout=10)
        response.raise_for_status()
        
        existing_aliases = {field['alias'] for field in response.json().get('fields', [])}
        required_aliases = set(CUSTOM_FIELDS.keys())
        
        missing_fields = required_aliases - existing_aliases
        
        if not missing_fields:
            print("SUCCESS: All required Mautic custom fields are present.")
            sys.exit(0)
        else:
            print(f"FAILURE: The following Mautic custom fields are missing: {', '.join(missing_fields)}")
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Mautic API to verify fields: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_fields()
