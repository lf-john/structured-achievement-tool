#!/bin/bash
# US-009 Verification Script
# Runs the pytest test case for the Claude API fallback logic.

# Exit immediately if a command exits with a non-zero status.
set -e

# Define the test file path
TEST_FILE="tests/test_us_009_agent_fallback.py"

# Check if the test file exists
if [ ! -f "$TEST_FILE" ]; then
    echo "ERROR: Test file not found at $TEST_FILE"
    exit 1
fi

# Run pytest on the specific test file
# The test will simulate an API failure and verify the fallback,
# notification, and content flagging mechanisms.
echo "Running verification test for US-009..."
pytest "$TEST_FILE" -v

# If pytest exits with 0, the test passed.
echo "Verification successful: Fallback logic is working as expected."
exit 0
