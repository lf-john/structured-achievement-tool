#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define the path for the runner script
RUNNER_SCRIPT="run_icp_matcher.py"
WORKFLOW_DIR="src/workflows"
WORKFLOW_MODULE="icp_matching_workflow.py"
CONFIG_DIR="config"
CONFIG_FILE="icp_criteria.json"

# Check if the virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "ERROR: Python virtual environment is not activated."
    echo "Please activate it with 'source .venv/bin/activate' before running this script."
    exit 1
fi

echo "Running verification for ICP Matcher Workflow..."

# 1. Create dummy input data for the test run
cat > company_data.json << EOL
{
  "name": "Innovate Inc.",
  "description": "A leading provider of AI-driven solutions for the enterprise market, focusing on workflow automation and data analytics.",
  "industry": "Technology",
  "size": 500
}
EOL

# 2. Run the ICP Matcher workflow with the sample data
echo "Executing the workflow..."
# The python script will print the JSON result to stdout
output=$(python $RUNNER_SCRIPT company_data.json)

# 3. Verify the output
echo "Verifying the output..."
echo "Output received: $output"

# Check if the output contains the required keys.
# Using python to parse JSON is more robust than using grep.
if echo "$output" | python -c "import sys, json; data = json.load(sys.stdin); assert 'score' in data; assert 'reasoning' in data; assert isinstance(data['score'], float)"; then
    echo "Verification successful: Output contains 'score' and 'reasoning' keys, and score is a float."
else
    echo "Verification failed: Output is not in the expected format."
    # Clean up and exit
    rm company_data.json
    exit 1
fi

# 4. Clean up the dummy file
rm company_data.json

echo "ICP Matcher Workflow verification complete and successful."
exit 0
