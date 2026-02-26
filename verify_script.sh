#!/bin/bash

set -e

FILE_PATH="marketing-automation/docs/mautic-rate-limits.md"

if [ ! -f "$FILE_PATH" ]; then
  echo "File not found: $FILE_PATH"
  exit 1
fi

# Check for Week 2 content
grep -q "Week 2" "$FILE_PATH"
grep -q "msg_limit=100" "$FILE_PATH"
grep -q "cron 1x/day" "$FILE_PATH"

# Check for Week 3 content
grep -q "Week 3" "$FILE_PATH"
grep -q "msg_limit=250" "$FILE_PATH"
grep -q "cron 2x/day" "$FILE_PATH"

# Check for Week 4 content
grep -q "Week 4" "$FILE_PATH"
grep -q "msg_limit=500" "$FILE_PATH"
grep -q "cron 4x/day" "$FILE_PATH"

echo "Verification successful: $FILE_PATH contains all required rate limit information."
exit 0
