#!/bin/bash

# Activate python environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "ERROR: Could not find venv/bin/activate" >&2
    exit 1
fi

# Generate the report
python src/generate_audit_report.py
if [ $? -ne 0 ]; then
    echo "ERROR: Report generation script failed" >&2
    exit 1
fi

# Check if the report file was created
DATE=$(date +%Y%m%d)
REPORT_FILE="audit_${DATE}.md"

if [ ! -f "$REPORT_FILE" ]; then
    echo "ERROR: Report file '$REPORT_FILE' was not created." >&2
    exit 1
fi

# Check for key content
if ! grep -q "SAT System Audit Report" "$REPORT_FILE" || ! grep -q "Timestamp" "$REPORT_FILE"; then
    echo "ERROR: Report file is missing expected content." >&2
    rm "$REPORT_FILE"
    exit 1
fi

echo "SUCCESS: Audit report generated and verified successfully."
rm "$REPORT_FILE"
exit 0
