#!/bin/bash
# This script runs the health check.
# It requires a running Prometheus instance on localhost:9090.
# To make this self-contained and verifiable, we'll start a mock server.

# Check if port 9090 is available
if ! lsof -i:9090 > /dev/null; then
    # Mock a healthy Prometheus response
    mkdir -p api/v1
    echo '{
      "status": "success",
      "data": {
        "activeTargets": [
          {
            "scrapePool": "prometheus",
            "scrapeUrl": "http://localhost:9090/metrics",
            "health": "up"
          }
        ]
      }
    }' > api/v1/targets

    python3 -m http.server 9090 &
    MOCK_PID=$!
    # Give the server a moment to start, and suppress output
    sleep 1 > /dev/null 2>&1

    # Run the check
    python3 health_check.py
    RESULT=$?

    # Cleanup
    kill $MOCK_PID
    rm -rf api

    if [ $RESULT -eq 0 ]; then
        echo "Verification successful: health_check.py correctly identified healthy targets."
        exit 0
    else
        echo "Verification failed: health_check.py reported an issue with healthy targets."
        exit 1
    fi
else
    echo "Port 9090 is already in use. Assuming Prometheus is running and running check directly."
    python3 health_check.py
fi
