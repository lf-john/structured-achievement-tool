#!/bin/bash
# Verify that the rclone mount at ~/GoogleDrive is accessible

# Check if the directory exists
if [ ! -d "$HOME/GoogleDrive" ]; then
  echo "Error: Mount directory ~/GoogleDrive does not exist."
  exit 1
fi

# Attempt to list the contents of the directory
# Redirect output to /dev/null as we only care about the exit code
if ls "$HOME/GoogleDrive" > /dev/null 2>&1; then
  echo "Success: Rclone mount at ~/GoogleDrive is accessible."
  exit 0
else
  echo "Error: Failed to list contents of ~/GoogleDrive. Mount may be unhealthy."
  exit 1
fi
