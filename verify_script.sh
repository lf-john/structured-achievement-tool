#!/bin/bash
FILE_PATH="~/projects/marketing-automation/docs/crm-mautic-sync.md"

# Expand the tilde to the user's home directory
EVAL_FILE_PATH=$(eval echo "$FILE_PATH")

if [ -f "$EVAL_FILE_PATH" ] && [ -s "$EVAL_FILE_PATH" ]; then
  echo "Verification successful: $EVAL_FILE_PATH exists and is not empty."
  exit 0
else
  echo "Verification failed: $EVAL_FILE_PATH does not exist or is empty."
  exit 1
fi
