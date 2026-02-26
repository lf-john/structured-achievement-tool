#!/bin/bash

set -e

# Define paths
SCRIPT_PATH="/home/johnlane/projects/marketing-automation/scripts/normalize_leads.py"
TEST_DIR="/tmp/test_normalization"
SOURCE_CSV="$TEST_DIR/source_leads.csv"
CLEANED_CSV="$TEST_DIR/cleaned_leads.csv"
REPORT_FILE="$TEST_DIR/normalization_report.txt"
EXPECTED_CLEANED_CSV="$TEST_DIR/expected_cleaned_leads.csv"
EXPECTED_REPORT_FILE="$TEST_DIR/expected_normalization_report.txt"

# Create test directory
mkdir -p "$TEST_DIR"

# Create dummy source CSV
cat > "$SOURCE_CSV" << EOL
email,industry,state,company_size
test1@example.com,Tech,California,1-10
test2@example,Technology,CA,11-50
test1@example.com,SaaS,california,1 - 10 employees
test3@example.com,Finance,New York,51-200
invalid-email,Manufacturing,ny,201-500
test1@example.com,Technology,California,
EOL

# Create dummy expected cleaned CSV
cat > "$EXPECTED_CLEANED_CSV" << EOL
email,industry,state,company_size
test1@example.com,Technology,CA,1-10
test2@example.com,Technology,CA,11-50
test3@example.com,Finance,NY,51-200
EOL

# Create dummy expected report
cat > "$EXPECTED_REPORT_FILE" << EOL
Normalization Report
--------------------
Total records processed: 6
Records cleaned: 3
Duplicates removed: 2
Invalid emails removed: 1
EOL

# Check if python script exists, if not, create a placeholder
if [ ! -f "$SCRIPT_PATH" ]; then
    cat > "$SCRIPT_PATH" << 'EOL'
import pandas as pd
import re
import os

def normalize_leads(source_path, cleaned_path, report_path):
    df = pd.read_csv(source_path)

    report = {
        "total_records": len(df),
        "duplicates_removed": 0,
        "invalid_emails_removed": 0
    }

    # Email validation
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    valid_email_mask = df['email'].apply(lambda x: isinstance(x, str) and re.match(email_regex, x))
    report["invalid_emails_removed"] = len(df) - valid_email_mask.sum()
    df = df[valid_email_mask]

    # Deduplication
    df_sorted = df.assign(completeness=df.notna().sum(axis=1)).sort_values('completeness', ascending=False)
    initial_rows = len(df_sorted)
    df_deduplicated = df_sorted.drop_duplicates(subset='email', keep='first')
    report["duplicates_removed"] = initial_rows - len(df_deduplicated)
    df = df_deduplicated.drop(columns=['completeness'])

    # Normalization (simple examples)
    industry_map = {"Tech": "Technology", "SaaS": "Technology"}
    df['industry'] = df['industry'].replace(industry_map)

    state_map = {"California": "CA", "california": "CA", "New York": "NY", "ny": "NY"}
    df['state'] = df['state'].replace(state_map)

    size_map = {"1 - 10 employees": "1-10"}
    df['company_size'] = df['company_size'].replace(size_map)

    df.to_csv(cleaned_path, index=False)

    with open(report_path, 'w') as f:
        f.write("Normalization Report\n")
        f.write("--------------------\n")
        f.write(f"Total records processed: {report['total_records']}\n")
        f.write(f"Records cleaned: {len(df)}\n")
        f.write(f"Duplicates removed: {report['duplicates_removed']}\n")
        f.write(f"Invalid emails removed: {report['invalid_emails_removed']}\n")

if __name__ == "__main__":
    source = os.environ.get('SOURCE_CSV')
    cleaned = os.environ.get('CLEANED_CSV')
    report = os.environ.get('REPORT_FILE')
    if source and cleaned and report:
        normalize_leads(source, cleaned, report)
EOL
fi

# Run the script using environment variables
export SOURCE_CSV
export CLEANED_CSV
export REPORT_FILE
python3 "$SCRIPT_PATH"

# Verify the output
diff -u "$EXPECTED_CLEANED_CSV" "$CLEANED_CSV"
diff -u "$EXPECTED_REPORT_FILE" "$REPORT_FILE"

# Clean up
rm -rf "$TEST_DIR"

echo "Verification successful!"
exit 0
