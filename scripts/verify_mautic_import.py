#!/usr/bin/env python3
import argparse
import json
import random
import sys
import requests

def load_config():
    """Loads configuration from config.json."""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Could not decode config.json.", file=sys.stderr)
        sys.exit(1)

def get_api_headers(config):
    """Returns headers for Mautic API requests."""
    token = config.get('mautic_api_token')
    if not token or token == "YOUR_MAUTIC_API_TOKEN":
        print("Error: Mautic API token is not configured in config.json.", file=sys.stderr)
        sys.exit(1)
    return {
        'Authorization': f'Bearer {token}'
    }

def check_contact_count(base_url, headers, expected_count):
    """Verify total contact count."""
    print(f"Verifying contact count...")
    url = f"{base_url}/api/contacts?limit=1"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        total_contacts = int(data.get('total', 0))
        print(f"Found {total_contacts} contacts in Mautic.")
        # Allow for some deviation due to deduplication/invalids
        if not (expected_count * 0.9 <= total_contacts <= expected_count * 1.1):
            print(f"Warning: Total contact count {total_contacts} differs significantly from expected {expected_count}.", file=sys.stderr)
            # This is a warning, not a failure, as per story context
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error fetching contact count: {e}", file=sys.stderr)
        return False

def check_segment_counts(base_url, headers):
    """Verify segment counts are reasonable."""
    print("Verifying segment counts...")
    url = f"{base_url}/api/segments?limit=50"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        segments = response.json().get('segments', {})
        if not segments:
            print("Warning: No segments found.", file=sys.stderr)
            return True # Not a failure if no segments exist
        
        failures = []
        for segment_id, segment_data in segments.items():
            if 'contacts' in segment_data and segment_data['contacts'] is None:
                 # Mautic 5 can have null here, we need to query the contact list
                 contacts_url = f"{base_url}/api/segments/{segment_id}/contacts?limit=1"
                 contact_resp = requests.get(contacts_url, headers=headers)
                 contact_resp.raise_for_status()
                 contact_count = int(contact_resp.json().get('total', 0))
            else:
                 contact_count = int(segment_data.get('contacts', 0))

            if contact_count == 0:
                print(f"Warning: Segment '{segment_data['name']}' (ID: {segment_id}) has 0 contacts.")
        
        print(f"Verified {len(segments)} segments.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error fetching segments: {e}", file=sys.stderr)
        return False

def check_contact_samples(base_url, headers, sample_size=10):
    """Verify field mapping and lead scores for a sample of contacts."""
    print(f"Verifying a sample of {sample_size} contacts...")
    url = f"{base_url}/api/contacts?limit={sample_size}&orderBy=id&orderByDir=DESC"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        contacts = response.json().get('contacts', {})
        if len(contacts) < sample_size:
            print(f"Warning: Found only {len(contacts)} contacts to sample, less than the desired {sample_size}.")
        
        if not contacts:
             print("Error: No contacts found to sample.", file=sys.stderr)
             return False

        failures = []
        for contact_id, contact_data in contacts.items():
            # Check field mapping
            if not contact_data.get('fields', {}).get('core', {}).get('email', {}).get('value'):
                failures.append(f"Contact ID {contact_id}: Email is missing.")
            # Check lead score
            score = contact_data.get('points', 0)
            if score <= 0:
                failures.append(f"Contact ID {contact_id}: Demographic lead score not applied (score: {score}).")

        if failures:
            print("Sample verification failed:", file=sys.stderr)
            for f in failures:
                print(f"- {f}", file=sys.stderr)
            return False
        
        print("Contact sample verification successful.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error fetching contact samples: {e}", file=sys.stderr)
        return False

def check_duplicates(base_url, headers):
    """Check for duplicate contacts based on email from a sample."""
    print("Verifying absence of duplicate contacts...")
    url = f"{base_url}/api/contacts?limit=5&orderBy=id&orderByDir=DESC"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        contacts = response.json().get('contacts', {})
        if not contacts:
            print("Warning: No contacts to check for duplicates.")
            return True

        for _, contact_data in contacts.items():
            email = contact_data.get('fields', {}).get('core', {}).get('email', {}).get('value')
            if email:
                search_url = f"{base_url}/api/contacts?search=email:{requests.utils.quote(email)}"
                search_resp = requests.get(search_url, headers=headers)
                search_resp.raise_for_status()
                search_data = search_resp.json()
                if int(search_data.get('total', 0)) > 1:
                    print(f"Error: Duplicate contact found for email: {email}", file=sys.stderr)
                    return False
        
        print("No duplicate contacts found in sample.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error checking for duplicates: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Verify Mautic lead import via API.")
    parser.add_argument('--expected-contacts', type=int, required=True, help="The expected number of contacts.")
    args = parser.parse_args()

    config = load_config()
    mautic_config = config.get('mautic_api_url')
    if not mautic_config:
        print("Error: 'mautic_api_url' not in config.json.", file=sys.stderr)
        sys.exit(1)
    
    base_url = mautic_config.rstrip('/')
    headers = get_api_headers(config)

    checks = {
        "Contact Count": check_contact_count(base_url, headers, args.expected_contacts),
        "Segment Counts": check_segment_counts(base_url, headers),
        "Contact Samples": check_contact_samples(base_url, headers),
        "Duplicate Check": check_duplicates(base_url, headers),
    }

    if all(checks.values()):
        print("
All verification checks passed successfully!")
        sys.exit(0)
    else:
        print("
Some verification checks failed.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
