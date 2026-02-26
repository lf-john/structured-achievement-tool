#!/bin/bash
# US-010 Verification Script
# This script runs the integration test for the Ollama fallback logic.
# It ensures that when Ollama is unavailable, tasks are retried,
# notifications are sent, and no fallback to other LLM providers occurs.

# Ensure python path includes the source
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run the specific test for this story.
# Note: The test file 'tests/test_us_010_ollama_fallback.py' will be created
# as part of the execution plan. This script assumes it exists.
if [ ! -f "tests/test_us_010_ollama_fallback.py" ]; then
    echo "ERROR: Test file tests/test_us_010_ollama_fallback.py not found."
    echo "Please run the implementation steps first."
    exit 1
fi

pytest tests/test_us_010_ollama_fallback.py -v
