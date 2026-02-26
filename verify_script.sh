#!/bin/bash
set -e

FILE_PATH="docs/SES_SANDBOX_EXIT_PROCESS.md"

if [ ! -f "$FILE_PATH" ]; then
  echo "Error: File '$FILE_PATH' does not exist."
  exit 1
fi

if [ ! -s "$FILE_PATH" ]; then
  echo "Error: File '$FILE_PATH' is empty."
  exit 1
fi

echo "Verification successful: File '$FILE_PATH' exists and is not empty."
exit 0
