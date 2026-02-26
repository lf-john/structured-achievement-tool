#!/bin/bash
# verify_script.sh: Verifies that key network ports are listening.

PORTS=(8080 8088 8090 9090 3001 11434)

echo "Verifying connectivity for ports: ${PORTS[*]}"

for port in "${PORTS[@]}"; do
  # Use 'ss -tuln' to get a list of listening TCP and UDP ports.
  # 'grep -q' searches quietly and exits with success if a match is found.
  # We search for ":<port>" to match the port number in the address column.
  if ss -tuln | grep -q ":${port}"; then
    echo "  - Port ${port}: OK"
  else
    echo "  - Port ${port}: FAILED (Not listening)"
    # Exit with an error code if any port is not found
    exit 1
  fi
done

echo "All ports are listening. Verification successful."
exit 0
