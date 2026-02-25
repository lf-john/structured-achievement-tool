#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

FILE="US-003_DMARC_RECORD.md"
EXPECTED_RECORD="v=DMARC1; p=none; rua=mailto:dmarc-reports@logicalfront.net; pct=100"

if [ ! -f "$FILE" ]; then
    echo "Error: $FILE not found."
    exit 1
fi

if grep -qF "$EXPECTED_RECORD" "$FILE"; then
    echo "Verification successful: DMARC record found in $FILE."
    exit 0
else
    echo "Error: DMARC record not found or incorrect in $FILE."
    exit 1
fi
