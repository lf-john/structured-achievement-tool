#!/bin/bash
# verify_script.sh

set -e

errors=()

# 1. Check if python sync script exists and is executable
if [ ! -x "src/mautic_suitecrm_sync.py" ]; then
  errors+=("src/mautic_suitecrm_sync.py does not exist or is not executable.")
fi

# 2. Check if BATCH_SIZE is configured in the sync script
if ! grep -q "BATCH_SIZE = 1000" "src/mautic_suitecrm_sync.py"; then
  errors+=("BATCH_SIZE is not correctly configured in src/mautic_suitecrm_sync.py.")
fi

# 3. Check if crontab.txt exists and has the correct frequency
if [ ! -f "crontab.txt" ]; then
  errors+=("crontab.txt does not exist.")
elif ! grep -q "*/15 \* \* \* \* python3 .*/src/mautic_suitecrm_sync.py" "crontab.txt"; then
  errors+=("Sync frequency is not configured to 15 minutes in crontab.txt.")
fi

# 4. Check if documentation files exist
if [ ! -f "docs/INITIAL_SYNC_PROCESS.md" ]; then
  errors+=("docs/INITIAL_SYNC_PROCESS.md does not exist.")
fi

if [ ! -f "docs/DEDUPLICATION_STRATEGY.md" ]; then
  errors+=("docs/DEDUPLICATION_STRATEGY.md does not exist.")
fi

# 5. Report results
if [ ${#errors[@]} -ne 0 ]; then
  echo "Verification failed:"
  for error in "${errors[@]}"; do
    echo "- $error"
  done
  exit 1
fi

echo "Verification successful."
exit 0
