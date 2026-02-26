#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Verification Script for Mautic Configuration ---

# 1. Verify Mautic container is running
echo "1/4: Verifying 'mautic-app' container is running..."
if ! docker ps --filter "name=mautic-app" --filter "status=running" -q | grep -q .; then
    echo "Error: Container 'mautic-app' is not running." >&2
    exit 1
fi
echo "Success: 'mautic-app' is running."

# 2. Verify mailer_spool_type
# Assuming Mautic is installed in /var/www/html
CONFIG_PATH="/var/www/html/app/config/local.php"
echo "2/4: Verifying 'mailer_spool_type' is set to 'file'..."
SPOOL_TYPE_SETTING=$(docker exec mautic-app grep "'mailer_spool_type'" "$CONFIG_PATH")
if ! echo "$SPOOL_TYPE_SETTING" | grep -q "'file'"; then
    echo "Error: 'mailer_spool_type' is not set to 'file'. Found: $SPOOL_TYPE_SETTING" >&2
    exit 1
fi
echo "Success: 'mailer_spool_type' is correctly set to 'file'."

# 3. Verify mailer_spool_msg_limit
# Based on warming-up plans, a low limit is expected. Let's check for 100.
echo "3/4: Verifying 'mailer_spool_msg_limit' is set to 100..."
MSG_LIMIT_SETTING=$(docker exec mautic-app grep "'mailer_spool_msg_limit'" "$CONFIG_PATH")
if ! echo "$MSG_LIMIT_SETTING" | grep -q "100"; then
    echo "Error: 'mailer_spool_msg_limit' is not set to 100. Found: $MSG_LIMIT_SETTING" >&2
    exit 1
fi
echo "Success: 'mailer_spool_msg_limit' is correctly set to 100."


# 4. Verify cron job frequency
# For Week 1, the warmup schedule implies a conservative frequency.
# We'll verify it's set to run every 15 minutes.
echo "4/4: Verifying 'mautic:emails:send' cron job frequency (every 15 mins)..."
if ! crontab -l | grep -q "*/15 \* \* \* \* .*mautic:emails:send"; then
    echo "Error: Cron job 'mautic:emails:send' is not configured to run every 15 minutes." >&2
    echo "Current crontab:" >&2
    crontab -l >&2
    exit 1
fi
echo "Success: Cron job is configured correctly for Week 1."

echo "All verification checks passed successfully."
exit 0
