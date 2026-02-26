#!/bin/bash
# Verification script for Mautic custom fields (US-002)

# Exit immediately if a command exits with a non-zero status.
set -e

# Ensure required environment variables are set for the verification script
if [[ -z "$MAUTIC_URL" || -z "$MAUTIC_USERNAME" || -z "$MAUTIC_PASSWORD" ]]; then
  echo "Error: MAUTIC_URL, MAUTIC_USERNAME, and MAUTIC_PASSWORD environment variables must be set."
  exit 1
fi

# Activate Python virtual environment if it exists and is not active
if [ -d ".venv" ] && [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating Python virtual environment..."
    source .venv/bin/activate
fi

# Run the verification Python script
# Add scripts directory to PYTHONPATH to handle local imports
export PYTHONPATH=$(pwd)/scripts/mautic:$PYTHONPATH
python scripts/mautic/verify_fields.py
