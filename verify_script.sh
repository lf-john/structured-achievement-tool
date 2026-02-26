#!/bin/bash
# Verification script for US-001

# The file to check
FILE="EMAIL_WARMUP_PLAN_logicalfront.net.md"

# 1. Check if the file exists
if [ ! -f "$FILE" ]; then
  echo "Error: Verification failed. File '$FILE' not found."
  exit 1
fi

# 2. Check if the file contains the main header
if ! grep -q "# 4-Week Email Warmup Schedule for logicalfront.net" "$FILE"; then
  echo "Error: Verification failed. Main header not found in '$FILE'."
  exit 1
fi

# 3. Check if the file contains the markdown table header
if ! grep -q "| Day | Max Send Volume | Target Audience Segment | Expected Bounce Rate Threshold |" "$FILE"; then
  echo "Error: Verification failed. Markdown table header not found in '$FILE'."
  exit 1
fi

# 4. Check if the file contains the final day's target
if ! grep -q "| 28 | 2500 | Segment C | < 5% |" "$FILE"; then
    echo "Error: Verification failed. Final day's target (2500) not found in '$FILE'."
    exit 1
fi


echo "Verification successful: '$FILE' exists and contains the required content."
exit 0
