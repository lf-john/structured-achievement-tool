#!/bin/bash
set -e
source venv/bin/activate
echo "Checking --no-resume flag..."
python src/daemon.py --help | grep -q "\-\-no-resume"
echo "Checking function definition in story_executor.py..."
grep -q "def resume_incomplete_workflows" src/execution/story_executor.py
echo "Checking daemon import..."
grep -q "from src.execution.story_executor import .*resume_incomplete_workflows" src/daemon.py
echo "All checks passed!"
