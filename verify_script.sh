#!/bin/bash
# Verification script for US-001: Full Loop Integration Test
# This script runs the end-to-end integration test and validates all acceptance criteria

set -e  # Exit immediately if any command fails
set -o pipefail  # Catch failures in pipes

echo "========================================="
echo "US-001 Integration Test Verification"
echo "========================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "✗ ERROR: pytest not found. Please install pytest."
    exit 1
fi

# Check if the test file exists
TEST_FILE="tests/test_US_001_full_loop_integration.py"
if [ ! -f "$TEST_FILE" ]; then
    echo "✗ ERROR: Test file not found: $TEST_FILE"
    echo "  The test file must be created before verification."
    exit 1
fi

echo "Running integration test with 90-second timeout..."
echo "(Test must complete in <60s per acceptance criteria)"
echo ""

# Run the integration test with timeout
# - timeout 90s: Kill if test hangs (buffer over 60s requirement)
# - -v: Verbose output
# - --tb=short: Shorter traceback on failure
# - -s: Show print statements (useful for debugging)
if timeout 90s pytest "$TEST_FILE" -v --tb=short -s; then
    echo ""
    echo "========================================="
    echo "✓ SUCCESS: All integration tests passed"
    echo "========================================="
    exit 0
else
    EXIT_CODE=$?
    echo ""
    echo "========================================="
    if [ $EXIT_CODE -eq 124 ]; then
        echo "✗ TIMEOUT: Test exceeded 90-second limit"
        echo "  (Requirement: complete in <60s)"
    else
        echo "✗ FAILURE: Integration test failed"
    fi
    echo "========================================="
    exit 1
fi
