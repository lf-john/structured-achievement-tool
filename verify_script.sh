#!/bin/bash

# Verification script for US-005

FILE="EMAIL_WARMUP_ABORT_CRITERIA.md"

if [ ! -f "$FILE" ]; then
    echo "Error: $FILE does not exist."
    exit 1
fi

if ! grep -q "Abort Criteria" "$FILE"; then
    echo "Error: 'Abort Criteria' section is missing from $FILE."
    exit 1
fi

if ! grep -q "Remediation Steps" "$FILE"; then
    echo "Error: 'Remediation Steps' section is missing from $FILE."
    exit 1
fi

echo "Verification successful: $FILE contains the required sections."
exit 0
