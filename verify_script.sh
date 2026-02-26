#!/bin/bash

# Ensure the script exits if any command fails
set -e

# Define the path to the verification script
VERIFY_PY_SCRIPT=".tmp_sdt/verify_router_logic.py"
VENV_PATH="venv/bin/activate"

# Check if the virtual environment exists
if [ ! -f "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH"

# Check if the python verification script exists
if [ ! -f "$VERIFY_PY_SCRIPT" ]; then
    echo "Error: Verification script not found at $VERIFY_PY_SCRIPT"
    exit 1
fi

echo "Running verification script..."
# Run the python script
python "$VERIFY_PY_SCRIPT"

# Deactivate is not strictly necessary in a script but is good practice
deactivate

echo "Verification script executed successfully."
