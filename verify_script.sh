#!/bin/bash
# Verification script for US-001

# Exit immediately if a command exits with a non-zero status.
set -e

# Define the directory path
# Expand the tilde to the user's home directory
DIR_PATH="$HOME/projects/system-reports"

# Check if the directory exists
if [ -d "$DIR_PATH" ]; then
  echo "Verification successful: Directory '$DIR_PATH' exists."
  exit 0
else
  echo "Verification failed: Directory '$DIR_PATH' does not exist."
  exit 1
fi
