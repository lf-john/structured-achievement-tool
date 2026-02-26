#!/bin/bash

set -e

FILE="DAILY_MONITORING_CHECKLIST.md"

if [ ! -f "$FILE" ]; then
    echo "Error: $FILE not found."
    exit 1
fi

# Verify key commands and metrics are in the checklist
grep -q "aws ses get-send-statistics" "$FILE" || (echo "Missing 'get-send-statistics' command"; exit 1)
grep -q "aws ses get-account-sending-enabled" "$FILE" || (echo "Missing 'get-account-sending-enabled' command"; exit 1)
grep -q "Mautic Email Queue" "$FILE" || (echo "Missing Mautic queue check section"; exit 1)
grep -q "BounceRate" "$FILE" || (echo "Missing BounceRate check"; exit 1)
grep -q "ComplaintRate" "$FILE" || (echo "Missing ComplaintRate check"; exit 1)

echo "Verification successful: $FILE contains all required checks."
exit 0
