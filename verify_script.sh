#!/bin/bash
# This script verifies the GrafanaClient implementation by running its unit tests.
# It ensures that the client can be initialized, can handle authentication,
# and that its methods for dashboard operations work as expected, all without
# requiring a running Grafana instance.
# The script will exit with 0 on success and a non-zero value on failure.

# It is expected that you first create the following files:
# 1. src/monitoring/grafana_client.py
# 2. tests/test_grafana_client.py
# This script will fail if those files do not exist.

pytest tests/test_grafana_client.py -v
