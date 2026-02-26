#!/bin/bash
# verify_script.sh
# Verifies that the mautic:emails:send cron is set to run once per day.

# This regex checks for a cron schedule pattern that equates to once a day.
# It looks for two numbers (minute, hour) followed by three asterisks,
# and then the mautic:emails:send command.
ONCE_A_DAY_PATTERN="^[0-9]+[[:space:]]+[0-9]+[[:space:]]+\*[[:space:]]+\*[[:space:]]+\*[[:space:]]+.*mautic:emails:send"

# Execute grep inside the container.
# The command will exit with 0 if the pattern is found, and a non-zero value otherwise.
docker exec mautic-app grep -Eq "$ONCE_A_DAY_PATTERN" /etc/cron.d/mautic

if [ $? -eq 0 ]; then
  echo "Verification successful: Cron job 'mautic:emails:send' is configured to run once a day."
  exit 0
else
  echo "Verification failed: Cron job 'mautic:emails:send' is not configured correctly."
  docker exec mautic-app cat /etc/cron.d/mautic
  exit 1
fi
