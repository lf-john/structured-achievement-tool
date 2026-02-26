#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Verifying Directory Creation ---"
if [ -d "$HOME/projects/system-reports/" ]; then
    echo "OK: Directory ~/projects/system-reports/ exists."
else
    echo "FAIL: Directory ~/projects/system-reports/ does not exist."
    exit 1
fi

echo ""
echo "--- Verifying Python Module Files ---"
FILES_TO_CHECK=(
    "src/benchmarking/__init__.py"
    "src/benchmarking/data_models.py"
    "src/benchmarking/config.py"
    "src/benchmarking/ollama_client.py"
)

for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        echo "OK: File $file exists."
    else
        echo "FAIL: File $file does not exist."
        exit 1
    fi
done

echo ""
echo "--- Verifying Ollama API Connectivity ---"
# Use a short python script to test the client
cat << 'EOF' > verify_client.py
import sys
from src.benchmarking.ollama_client import OllamaClient

client = OllamaClient()
if client.is_available():
    print("OK: Ollama API is available.")
    sys.exit(0)
else:
    print(f"FAIL: Could not connect to Ollama API at {client.base_url}.")
    sys.exit(1)
EOF

python3 verify_client.py

# Cleanup the temp script
rm verify_client.py

echo ""
echo "--- Verification Successful ---"
exit 0
