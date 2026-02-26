#!/bin/bash
set -eo pipefail

echo "Sourcing Python virtual environment..."
# Check if venv exists before sourcing
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "Error: Virtual environment not found at .venv/bin/activate"
    exit 1
fi

echo "Verifying engagement scorer workflow by running its tests..."

# Check if the test file exists before running pytest
if [ -f "tests/workflows/test_engagement_scorer.py" ]; then
    pytest tests/workflows/test_engagement_scorer.py -v
else
    echo "Error: Test file not found at tests/workflows/test_engagement_scorer.py"
    exit 1
fi

echo "Verification complete. All tests passed."
