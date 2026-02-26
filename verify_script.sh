#!/bin/bash

# Path to the documentation file
DOC_FILE="docs/lead-import-guide.md"

# List of segments to verify
SEGMENTS=(
  "industry-healthcare"
  "industry-higher-ed"
  "industry-manufacturing"
  "geo-california"
  "geo-texas"
  "geo-new-york"
  "size-smb"
  "size-mid-market"
  "size-enterprise"
  "engaged-openers"
  "engaged-clickers"
  "cold-no-engagement"
  "icp-strong-fit"
  "icp-moderate-fit"
  "warmup-safe"
)

# Check if the documentation file exists
if [ ! -f "$DOC_FILE" ]; then
  echo "Error: Documentation file '$DOC_FILE' not found."
  exit 1
fi

# Check for each segment's presence in the document
for segment in "${SEGMENTS[@]}"; do
  if ! grep -q "$segment" "$DOC_FILE"; then
    echo "Error: Segment '$segment' not found in documentation."
    exit 1
  fi
done

echo "Verification successful: All segments are documented in '$DOC_FILE'."
exit 0
