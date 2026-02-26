#!/bin/bash
# Verification script for the Grafana setup test suite

# Exit immediately if a command exits with a non-zero status.
set -e

# Define the paths to the new test files
TEST_FILES=(
  "tests/test_grafana_client.py"
  "tests/test_dashboard_builder.py"
  "tests/test_grafana_setup.py"
)

# Check if the test files exist before running them
for f in "${TEST_FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "Error: Test file not found at $f"
    exit 1
  fi
done

# Run pytest on the newly created test files
# The -v flag enables verbose output.
echo "Running pytest for Grafana setup modules..."
pytest -v "${TEST_FILES[@]}"

# If pytest completes without a non-zero exit code, the verification is successful.
echo "Verification successful: All new tests passed."
exit 0
