#!/bin/bash
set -e

# Services to check directly
services=("sat.service" "rclone-gdrive.service")

# Service patterns to check
service_patterns=("sat-monitor" "sat-web" "sat-tunnel")

all_ok=true

echo "Checking specific services..."
for service in "${services[@]}"; do
    if systemctl --user is-active --quiet "$service"; then
        echo "✅ $service is active."
    else
        echo "❌ $service is not active."
        all_ok=false
    fi
done

echo "Checking service patterns..."
for pattern in "${service_patterns[@]}"; do
    # Find services matching the pattern
    mapfile -t matching_services < <(systemctl --user list-units --type=service --all 2>/dev/null | awk "/$pattern/ {print \$1}")

    if [ ${#matching_services[@]} -eq 0 ]; then
        echo "ℹ️ No services found matching pattern: $pattern"
        continue
    fi

    for service in "${matching_services[@]}"; do
        if systemctl --user is-active --quiet "$service"; then
            echo "✅ $service is active."
        else
            echo "❌ $service is not active."
            all_ok=false
        fi
    done
done

if $all_ok; then
    echo "All checked services are running."
    exit 0
else
    echo "Some services are not running."
    exit 1
fi
