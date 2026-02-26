#!/bin/bash
set -e

# Path to the verification script
SCRIPT_PATH="scripts/verify_mautic_import.py"

# Placeholder for expected contacts. In a real CI/CD pipeline,
# this value would come from the lead import process.
EXPECTED_CONTACT_COUNT=500

# Check if the script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Verification script not found at $SCRIPT_PATH"
    exit 1
fi

# Activate python environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi


echo "Running Mautic import verification..."
python3 "$SCRIPT_PATH" --expected-contacts "$EXPECTED_CONTACT_COUNT"

if [ $? -eq 0 ]; then
    echo "Verification script completed successfully."
    exit 0
else
    echo "Verification script failed."
    exit 1
fi
