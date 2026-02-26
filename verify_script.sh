#!/bin/bash

# This script verifies that the dashboard_builder can generate the queue depth panel.
# It creates a temporary Python script to call the necessary function and validate its output.

# Create a temporary verification Python script
cat > verify_panel.py << EOF
import json
from src.dashboard_builder import DashboardBuilder

# Check if the method exists before calling it
if not hasattr(DashboardBuilder, 'create_queue_depth_panel'):
    print("Error: 'create_queue_depth_panel' method not found in DashboardBuilder.")
    exit(1)

builder = DashboardBuilder()
panel = builder.create_queue_depth_panel()

# Check 1: Ensure panel is a dictionary
if not isinstance(panel, dict):
    print("Error: The generated panel is not a dictionary.")
    exit(1)

panel_json = json.dumps(panel)

# Check 2: Verify the panel title is correct
if '"title": "Queue Depth"' not in panel_json:
    print("Error: Panel title is not 'Queue Depth'.")
    exit(1)

# Check 3: Verify the correct metric expression is used
if '"expr": "sat_queue_depth"' not in panel_json:
    print("Error: Panel does not contain the 'sat_queue_depth' metric.")
    exit(1)

# Check 4: Verify the panel type is 'gauge'
if '"type": "gauge"' not in panel_json:
    print("Error: Panel type is not 'gauge'.")
    exit(1)

print("Verification successful: Panel JSON contains the correct title, metric, and type.")
exit(0)
EOF

# Make sure the src directory is in the python path
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Run the temporary Python script for verification
python3 verify_panel.py
EXIT_CODE=$?

# Clean up the temporary script
rm verify_panel.py

# Exit with the code from the verification script
exit $EXIT_CODE
