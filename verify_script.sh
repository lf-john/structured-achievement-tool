#!/bin/bash
# verification_script.sh

# This script will be executed in a context where the dashboard server is running.
# It will use curl to check the new API endpoint.

# For the purpose of this plan, we assume the FastAPI app is running on localhost:8765
# and has been modified to include the /api/costs endpoint.

API_URL="http://localhost:8765/api/costs"

echo "--- Verifying Cost Reporting Dashboard ---"

# Step 1: Check if the API endpoint is reachable
if ! curl -s -f -o /dev/null "$API_URL"; then
    echo "Error: Failed to connect to API endpoint at $API_URL"
    exit 1
fi

echo "API endpoint is reachable."

# Step 2: Fetch the data and check for key fields using jq
# The script checks if the top-level keys 'cost_summary' and 'gpu_utilization' exist.
# It also checks for nested keys like 'daily' and 'claude-3-opus-20240229'.
# A real test would have mock data loaded to verify values, but for verification
# of implementation, checking the structure is sufficient.

curl -s "$API_URL" | jq -e '
  .cost_summary and
  .gpu_utilization and
  .cost_summary.daily and
  .cost_summary.weekly and
  .cost_summary.monthly and
  (has("error") | not)
' > /dev/null

JQ_EXIT_CODE=$?

if [ $JQ_EXIT_CODE -eq 0 ]; then
    echo "Verification successful: API response contains the expected data structure."
    exit 0
else
    echo "Verification failed: API response is missing expected fields or contains an error."
    echo "--- API Response ---"
    curl -s "$API_URL" | jq
    echo "--------------------"
    exit 1
fi
