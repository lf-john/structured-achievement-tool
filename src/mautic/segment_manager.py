import os
from .mautic_api_client import MauticApiClient

def get_mautic_client() -> MauticApiClient:
    # In a real scenario, these would come from secure configuration or environment variables
    mautic_base_url = os.getenv("MAUTIC_BASE_URL", "http://localhost:8080")
    mautic_api_key = os.getenv("MAUTIC_API_KEY", "dummy_api_key")
    return MauticApiClient(base_url=mautic_base_url, api_key=mautic_api_key)

def create_all_segments():
    client = get_mautic_client()

    segment_definitions = [
        # Industry Segments
        {"name": "industry-healthcare", "description": "Contacts in the Healthcare industry", "filters": [{"field": "industry", "operator": "equals", "value": "Healthcare"}]},
        {"name": "industry-higher-ed", "description": "Contacts in the Higher Education industry", "filters": [{"field": "industry", "operator": "equals", "value": "Higher Education"}]},
        {"name": "industry-manufacturing", "description": "Contacts in the Manufacturing industry", "filters": [{"field": "industry", "operator": "equals", "value": "Manufacturing"}]},

        # Geography Segments (top 10 states - for this example, we'll use the 3 provided)
        {"name": "geo-california", "description": "Contacts from California", "filters": [{"field": "state", "operator": "equals", "value": "CA"}]},
        {"name": "geo-texas", "description": "Contacts from Texas", "filters": [{"field": "state", "operator": "equals", "value": "TX"}]},
        {"name": "geo-new-york", "description": "Contacts from New York", "filters": [{"field": "state", "operator": "equals", "value": "NY"}]},

        # Company Size Segments
        {"name": "size-smb", "description": "Contacts from Small and Medium Businesses (<=50 employees)", "filters": [{"field": "company_size", "operator": "lessThanOrEqualTo", "value": "50"}]},
        {"name": "size-mid-market", "description": "Contacts from Mid-Market companies (51-500 employees)", "filters": [{"field": "company_size", "operator": "greaterThan", "value": "50"}, {"field": "company_size", "operator": "lessThanOrEqualTo", "value": "500"}]},
        {"name": "size-enterprise", "description": "Contacts from Enterprise companies (>500 employees)", "filters": [{"field": "company_size", "operator": "greaterThan", "value": "500"}]},

        # Engagement Segments
        {"name": "engaged-openers", "description": "Contacts who have opened emails", "filters": [{"field": "email_opens", "operator": "greaterThan", "value": "0"}]},
        {"name": "engaged-clickers", "description": "Contacts who have clicked emails", "filters": [{"field": "email_clicks", "operator": "greaterThan", "value": "0"}]},
        {"name": "cold-no-engagement", "description": "Contacts with no email opens or clicks", "filters": [{"field": "email_opens", "operator": "equals", "value": "0"}, {"field": "email_clicks", "operator": "equals", "value": "0"}]},

        # Lead Quality Segments
        {"name": "icp-strong-fit", "description": "Contacts with a strong ICP fit (score >= 80)", "filters": [{"field": "icp_score", "operator": "greaterThanOrEqualTo", "value": "80"}]},
        {"name": "icp-moderate-fit", "description": "Contacts with a moderate ICP fit (score >= 50 and < 80)", "filters": [{"field": "icp_score", "operator": "greaterThanOrEqualTo", "value": "50"}, {"field": "icp_score", "operator": "lessThan", "value": "80"}]},
        {"name": "warmup-safe", "description": "Contacts safe for email warm-up (low bounce rate)", "filters": [{"field": "email_bounce_rate", "operator": "lessThan", "value": "0.05"}]},
    ]

    print("Attempting to create Mautic segments...")
    results = []
    for segment in segment_definitions:
        print(f"Creating segment: {segment['name']}")
        result = client.create_segment(
            name=segment["name"],
            description=segment["description"],
            filters=segment["filters"]
        )
        results.append(result)
        if "simulated_success" in result and result["simulated_success"]:
            print(f"Successfully simulated creation of segment: {segment['name']}")
        else:
            print(f"Failed to simulate creation of segment: {segment['name']} - {result.get('error', 'Unknown error')}")
    return results

if __name__ == "__main__":
    create_all_segments()
