import requests
import json
import sys

def check_prometheus_targets():
    """
    Queries the Prometheus targets API and checks the health of each target.
    Exits with 1 if any target is unhealthy or if the request fails, otherwise exits with 0.
    """
    prometheus_url = "http://localhost:9090/api/v1/targets"
    try:
        response = requests.get(prometheus_url, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Prometheus at {prometheus_url}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON response from Prometheus.", file=sys.stderr)
        sys.exit(1)

    if data['status'] != 'success':
        print(f"Prometheus API returned status: {data['status']}", file=sys.stderr)
        sys.exit(1)

    active_targets = data.get('data', {}).get('activeTargets', [])
    if not active_targets:
        print("No active targets found.")
        sys.exit(0)

    unhealthy_targets = []
    print("Prometheus Target Health:")
    for target in active_targets:
        job = target.get('scrapePool', 'N/A')
        endpoint = target.get('scrapeUrl', 'N/A')
        health = target.get('health', 'N/A').upper()
        last_error = target.get('lastError', '')

        print(f"- Job: {job}, Endpoint: {endpoint}, Health: {health}")
        if health != 'UP':
            unhealthy_targets.append(target)
            if last_error:
                print(f"  Error: {last_error}")

    if unhealthy_targets:
        print(f"\nFound {len(unhealthy_targets)} unhealthy targets.", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nAll targets are healthy.")
        sys.exit(0)

if __name__ == "__main__":
    check_prometheus_targets()
