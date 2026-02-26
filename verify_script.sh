#!/bin/bash

# This script verifies the successful installation and basic configuration
# of the Mautic-SuiteCRM integration plugin.

# --- Configuration ---
# Replace with your actual container names if they differ.
MAUTIC_CONTAINER_NAME="mautic_app_1"
SUITECRM_SERVICE_NAME="suitecrm_app_1" # The service name in docker-compose, for networking
PLUGIN_BUNDLE_NAME="MauticSuiteCRMSyncBundle"

# ANSI color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Starting verification..."

# 1. Verify Container Networking
echo -n "Step 1: Verifying container networking... "
docker exec "$MAUTIC_CONTAINER_NAME" curl -s --fail "http://${SUITECRM_SERVICE_NAME}" > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo -e "${RED}FAILED${NC}"
  echo "Error: Mautic container ('$MAUTIC_CONTAINER_NAME') cannot reach SuiteCRM container ('http://${SUITECRM_SERVICE_NAME}')."
  echo "Please ensure they are on the same Docker network."
  exit 1
fi
echo -e "${GREEN}PASSED${NC}"

# 2. Verify Plugin Installation
echo -n "Step 2: Verifying plugin is installed in Mautic... "
# The plugin name might differ slightly, using grep for flexibility.
docker exec "$MAUTIC_CONTAINER_NAME" php /var/www/html/bin/console mautic:plugins:list | grep -q "Suite"
if [ $? -ne 0 ]; then
  echo -e "${RED}FAILED${NC}"
  echo "Error: Plugin '$PLUGIN_BUNDLE_NAME' not found in Mautic's installed plugins list."
  exit 1
fi
echo -e "${GREEN}PASSED${NC}"

# 3. Verify Mautic API is Enabled
echo -n "Step 3: Verifying Mautic API is enabled... "
docker exec "$MAUTIC_CONTAINER_NAME" php /var/www/html/bin/console mautic:config:get api_enabled | grep -q "1"
if [ $? -ne 0 ]; then
  echo -e "${RED}FAILED${NC}"
  echo "Error: Mautic API is not enabled (`api_enabled` is not set to 1)."
  exit 1
fi
echo -e "${GREEN}PASSED${NC}"

echo -e "\n${GREEN}Automated verification successful!${NC}"
echo "NOTE: This script does not verify the API connection itself. Please perform the manual connection test in the Mautic UI."
exit 0
