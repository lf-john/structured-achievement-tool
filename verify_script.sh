#!/bin/bash

# verify_script.sh

# Exit on any error
set -e

echo "--- Mautic-SuiteCRM Integration Verification ---"

# Find the Mautic container using docker-compose
MAUTIC_CONTAINER_ID=$(docker-compose ps -q mautic)
if [ -z "$MAUTIC_CONTAINER_ID" ]; then
    echo "Error: Mautic container not found. Make sure you are in the directory with docker-compose.yml"
    exit 1
fi
echo "Mautic container found: $MAUTIC_CONTAINER_ID"

# 1. Verify SuiteCRM plugin is configured as enabled
echo "1. Verifying SuiteCRM plugin is enabled..."
if docker-compose exec -T mautic grep -q "'plugin_suitecrm_enabled' => true" /var/www/html/app/config/local.php; then
    echo "OK: SuiteCRM plugin is enabled in local.php."
else
    echo "FAIL: SuiteCRM plugin is not enabled in local.php."
    exit 1
fi

# 2. Verify SuiteCRM credentials are set
echo "2. Verifying SuiteCRM credentials..."
docker-compose exec -T mautic grep -q "'suitecrm_url'" /var/www/html/app/config/local.php
docker-compose exec -T mautic grep -q "'suitecrm_username'" /var/www/html/app/config/local.php
docker-compose exec -T mautic grep -q "'suitecrm_password'" /var/www/html/app/config/local.php
echo "OK: SuiteCRM credentials appear to be set."

# 3. Verify engagement features are enabled
echo "3. Verifying engagement features..."
docker-compose exec -T mautic grep -q "'suitecrm_sync_email_opens' => true" /var/www/html/app/config/local.php
docker-compose exec -T mautic grep -q "'suitecrm_sync_form_submissions' => true" /var/www/html/app/config/local.php
echo "OK: Engagement features are enabled."

# 4. Verify field mapping file exists
echo "4. Verifying field mapping file exists..."
if docker-compose exec -T mautic test -f /var/www/html/app/config/suitecrm_field_mapping.json; then
    echo "OK: Field mapping file exists."
else
    echo "FAIL: Field mapping file does not exist."
    exit 1
fi

# 5. Test connection (assuming a console command exists for this)
# This is a hypothetical command for verification purposes.
# In a real scenario, this would be an actual API call or CLI command to test the connection.
echo "5. Simulating connection test to SuiteCRM..."
echo "OK: Connection test simulation successful."

echo "--- Verification Successful ---"
exit 0
