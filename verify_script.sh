#!/bin/bash
# verify_script.sh

# This script verifies the health of the Docker containers by running the docker_health_check.py script.
# It expects docker_health_check.py to be in the same directory.
# The docker_health_check.py script will exit with 0 on success and 1 on failure.

if [ ! -f ./docker_health_check.py ]; then
    echo "ERROR: docker_health_check.py not found."
    exit 1
fi

# Ensure python is available
if ! command -v python3 &> /dev/null
then
    echo "python3 could not be found"
    exit 1
fi

# Run the health check script
python3 ./docker_health_check.py
