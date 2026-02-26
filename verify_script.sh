#!/bin/bash
# verify_script.sh

# This script verifies that the Grafana panel for story success/fail rates
# can be generated correctly.

# Set -e to exit immediately if a command exits with a non-zero status.
set -e

echo "INFO: Creating temporary panel generation script..."
# Create a temporary python script to generate the panel
cat > /tmp/build_panel.py << EOL
import json
from src.dashboard_builder import DashboardBuilder

def build_panel():
    """Builds the Grafana panel for story success/failure rates."""
    builder = DashboardBuilder()

    queries = [
        {
            "expr": "increase(sat_stories_succeeded_total[5m])",
            "legendFormat": "Succeeded",
        },
        {
            "expr": "increase(sat_stories_failed_total[5m])",
            "legendFormat": "Failed",
        }
    ]

    panel = builder.create_time_series_panel(
        title="Stories Success/Fail Rate",
        queries=queries,
        options={}
    )
    return panel

if __name__ == "__main__":
    panel_json = build_panel()
    print(json.dumps(panel_json, indent=2))
EOL

echo "INFO: Generating panel JSON..."
# Run the script and save its output
python3 /tmp/build_panel.py > /tmp/grafana_panel.json

echo "INFO: Verifying panel JSON is valid..."
# Check if the output is valid JSON
python3 -m json.tool /tmp/grafana_panel.json > /dev/null

echo "INFO: Verifying panel content..."
# Check for the title and metric names in the generated JSON
grep -q '"title": "Stories Success/Fail Rate"' /tmp/grafana_panel.json
grep -q 'sat_stories_succeeded_total' /tmp/grafana_panel.json
grep -q 'sat_stories_failed_total' /tmp/grafana_panel.json

echo "INFO: Cleaning up temporary files..."
rm /tmp/build_panel.py
rm /tmp/grafana_panel.json

echo "SUCCESS: Verification complete."
exit 0
