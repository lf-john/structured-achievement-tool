#!/bin/bash
set -e

FILE="US-011_DESIGN.md"

if [ ! -f "$FILE" ]; then
    echo "Verification failed: Design document $FILE not found."
    exit 1
fi

grep -q "Batching" "$FILE" || (echo "Verification failed: 'Batching' section missing." && exit 1)
grep -q "Resumability" "$FILE" || (echo "Verification failed: 'Resumability' section missing." && exit 1)
grep -q "Progress Tracking" "$FILE" || (echo "Verification failed: 'Progress Tracking' section missing." && exit 1)
grep -q "Background Processing" "$FILE" || (echo "Verification failed: 'Background Processing' section missing." && exit 1)


echo "Verification successful: Design document is valid and contains all required sections."
exit 0
