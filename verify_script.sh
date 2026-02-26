#!/bin/bash
set -e

# This script verifies the basic functionality of the import_leads.py script in dry-run mode.

# Create a dummy CSV for testing
cat <<EOL > test_leads.csv
email,firstname,lastname
test1@example.com,Test,User1
test2@example.com,Test,User2
EOL

# Path to the script
SCRIPT_PATH="scripts/import_leads.py"

# Check if the script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script $SCRIPT_PATH not found."
    exit 1
fi

# Make sure python is available
if ! command -v python3 &> /dev/null
then
    echo "python3 could not be found"
    exit 1
fi

# Run the script in dry-run mode
OUTPUT=$(python3 "$SCRIPT_PATH" --input-file test_leads.csv --dry-run 2>&1)

# Check for expected output
if ! echo "$OUTPUT" | grep -q "Dry run mode enabled."; then
    echo "Verification failed: Did not find 'Dry run mode enabled.' in output."
    exit 1
fi

if ! echo "$OUTPUT" | grep -q "Processing batch 1 of 1"; then
    echo "Verification failed: Did not find 'Processing batch 1 of 1' in output."
    exit 1
fi

if ! echo "$OUTPUT" | grep -q "Successfully processed 2 contacts in dry run."; then
    echo "Verification failed: Did not find 'Successfully processed 2 contacts in dry run.' in output."
    exit 1
fi

# Clean up
rm test_leads.csv

echo "Verification successful."
exit 0
