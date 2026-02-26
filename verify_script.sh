#!/bin/bash
# This script verifies the Mautic sending limit configuration.

set -e

# Find the mautic-app container ID
CONTAINER_ID=$(docker ps --filter "name=mautic-app" -q)

if [ -z "$CONTAINER_ID" ]; then
    echo "Error: The 'mautic-app' container is not running." >&2
    exit 1
fi

echo "Found mautic-app container with ID: $CONTAINER_ID"

# Check for 'mailer_spool_type' => 'file'
if docker exec "$CONTAINER_ID" grep -q "'mailer_spool_type' *=> *'file'" /var/www/html/config/local.php; then
    echo "✅ Verification PASSED: 'mailer_spool_type' is set to 'file'."
else
    echo "❌ Verification FAILED: 'mailer_spool_type' is not set to 'file'." >&2
    exit 1
fi

# Check for 'mailer_spool_msg_limit' => 50
if docker exec "$CONTAINER_ID" grep -q "'mailer_spool_msg_limit' *=> *50" /var/www/html/config/local.php; then
    echo "✅ Verification PASSED: 'mailer_spool_msg_limit' is set to 50."
else
    echo "❌ Verification FAILED: 'mailer_spool_msg_limit' is not set to 50." >&2
    exit 1
fi

echo "All verification checks passed successfully."
exit 0
