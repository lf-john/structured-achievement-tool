#!/bin/bash
#
# verify_script.sh
#
# Story: US-002 - Collect Disk Usage Metrics
# Description:
#   This script executes `df -h` to gather disk usage information for
#   all mounted filesystems and flags any mount over 80% usage.
#
# Verification:
#   This script serves as its own verification. It exits 0 on successful
#   execution, indicating that the check was performed. The output of
#   the script provides the required report.
#

set -euo pipefail

# --- Configuration ---
# Threshold for disk usage percentage.
readonly THRESHOLD=80

# --- Main Logic ---
main() {
    echo "--- Verifying Disk Usage Metrics Collection ---"
    echo "Description: Running 'df -h' and flagging filesystems with usage > ${THRESHOLD}%."
    echo "-------------------------------------------------"

    # Store the header
    df -h | head -n 1

    # Process the rest of the output with awk
    # The script returns exit code 0 if it runs correctly.
    # Warnings are printed to stderr for any filesystem over the threshold.
    df -h | tail -n +2 | awk -v threshold="${THRESHOLD}" '
    {
        # Print the full line for reporting all mounts
        print $0

        # Extract usage percentage, removing the % sign from the 5th column
        usage = int(substr($5, 1, length($5)-1))

        # Check if usage exceeds the threshold
        if (usage > threshold) {
            # Print a warning message to stderr
            printf "WARNING: Mount point '\''%s'\'' is at %s usage, exceeding the %d%% threshold.\n", $6, $5, threshold > "/dev/stderr"
        }
    }
    '
    
    # $? will hold the exit status of the last command in the pipe (awk) because of pipefail
    local awk_status=$?
    if [ ${awk_status} -ne 0 ]; then
        echo "Error during awk processing." >&2
        exit 1
    fi

    echo "-------------------------------------------------"
    echo "Verification complete. Disk usage reported."
    exit 0
}

# --- Execution ---
main "$@"
