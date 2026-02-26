#!/bin/bash

# This script verifies that the Mautic documentation file has been created
# and contains all the required sections.

FILE="MAUTIC_WARMUP_CONFIGURATION.md"
SUCCESS=true

if [ ! -f "$FILE" ]; then
  echo "Error: Documentation file '$FILE' not found."
  exit 1
fi

SECTIONS=(
  "Week 1"
  "Week 2"
  "Week 3"
  "Week 4"
  "How to Change Mautic Settings"
  "How to Adjust Mautic Cron Frequency"
)

for section in "${SECTIONS[@]}"; do
  if ! grep -q "$section" "$FILE"; then
    echo "Error: Section '$section' is missing from '$FILE'."
    SUCCESS=false
  fi
done

if [ "$SUCCESS" = true ]; then
  echo "Verification successful: '$FILE' contains all required sections."
  exit 0
else
  echo "Verification failed."
  exit 1
fi
