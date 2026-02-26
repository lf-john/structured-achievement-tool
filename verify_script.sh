#!/bin/bash
set -e

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found."
    exit 1
fi

# Ensure pytest is installed
pip install pytest --quiet

# Run tests
pytest tests/test_industry_classifier.py
