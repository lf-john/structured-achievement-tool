#!/bin/bash
# verify_script.sh

# This script verifies that the lead scoring documentation has been added to the guide.
# It checks for the presence of the main header for the new section.

if grep -q "## Mautic Lead Scoring Configuration" "lead-import-guide.md"; then
  echo "Verification successful: Lead scoring documentation found."
  exit 0
else
  echo "Verification failed: Lead scoring documentation not found."
  exit 1
fi
