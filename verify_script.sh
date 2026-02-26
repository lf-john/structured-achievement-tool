#!/bin/bash

# Ensure the script fails if any command fails
set -e

# Run the health check script
OUTPUT=$(python3 src/health_check.py)

# Print the output for debugging purposes
echo "--- Health Check Script Output ---"
echo "${OUTPUT}"
echo "----------------------------------"

# Verify that the new metrics are present in the output
if echo "${OUTPUT}" | grep -q "CPU Load:" && echo "${OUTPUT}" | grep -q "Memory:"; then
  echo "✅ Verification successful: CPU Load and Memory metrics found in the output."
  exit 0
else
  echo "❌ Verification failed: Did not find 'CPU Load:' and/or 'Memory:' in the output."
  exit 1
fi
