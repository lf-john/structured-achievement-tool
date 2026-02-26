#!/bin/bash

# verification_script.sh
# Verifies that the Mautic-SuiteCRM field mapping documentation has been created correctly.

# Path to the documentation file
DOC_FILE="MAUTIC_SUITECRM_FIELD_MAPPING.md"

# Check if the documentation file exists
if [ ! -f "$DOC_FILE" ]; then
  echo "Error: Documentation file '$DOC_FILE' not found."
  exit 1
fi

# Check for the presence of key sections in the documentation
# These sections are critical for fulfilling the story's acceptance criteria.

# 1. Check for the main title
if ! grep -q "# Mautic & SuiteCRM Bidirectional Field Mapping" "$DOC_FILE"; then
  echo "Error: Main title not found in '$DOC_FILE'."
  exit 1
fi

# 2. Check for the Field Mapping Table
if ! grep -q "## Field Mapping Configuration" "$DOC_FILE"; then
  echo "Error: 'Field Mapping Configuration' section is missing."
  exit 1
fi

# 3. Check for Custom Field Documentation
if ! grep -q "## Custom Field Mapping" "$DOC_FILE"; then
  echo "Error: 'Custom Field Mapping' section is missing."
  exit 1
fi

# 4. Check for Conflict Resolution Strategy
if ! grep -q "## Conflict Resolution Strategy" "$DOC_FILE"; then
  echo "Error: 'Conflict Resolution Strategy' section is missing."
  exit 1
fi

# 5. Check for at least one mapped field as an example
if ! grep -q "| `first_name`" "$DOC_FILE"; then
    echo "Error: Example field mapping for 'first_name' is missing."
    exit 1
fi

echo "Verification successful: '$DOC_FILE' contains all required sections."
exit 0
