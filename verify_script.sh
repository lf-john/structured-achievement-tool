#!/bin/bash
set -e

FILE_PATH="lead-import-guide.md"

if [ ! -f "$FILE_PATH" ]; then
  echo "Error: File '$FILE_PATH' not found."
  exit 1
fi

# Check for key sections in the documentation using case-insensitive matching
grep -qi "Contacts > Import" "$FILE_PATH" || (echo "Missing section: Navigation instructions to 'Contacts > Import'" && exit 1)
grep -qi "upload" "$FILE_PATH" || (echo "Missing section: CSV upload instructions" && exit 1)
grep -qi "map" "$FILE_PATH" || (echo "Missing section: Column mapping guidance" && exit 1)
grep -qi "default value" "$FILE_PATH" || (echo "Missing section: Setting default values" && exit 1)
grep -qi "lead_source" "$FILE_PATH" || (echo "Missing example: 'lead_source' default value" && exit 1)
grep -qi "import_batch" "$FILE_PATH" || (echo "Missing section: 'import_batch' identifier" && exit 1)
grep -qi "monitor" "$FILE_PATH" || (echo "Missing section: Monitoring import progress" && exit 1)

echo "Verification successful: '$FILE_PATH' contains all required sections."
exit 0
