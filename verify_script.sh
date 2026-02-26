#!/bin/bash
# Verify that the documentation file was created and is not empty.

FILE_PATH="output/llm-routing-system.md"

if [ -s "$FILE_PATH" ]; then
  echo "Verification successful: $FILE_PATH exists and is not empty."
  exit 0
else
  echo "Verification failed: $FILE_PATH does not exist or is empty."
  exit 1
fi
