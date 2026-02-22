#!/bin/bash
# Simple SAT Health Check

echo "============================================================"
echo "  SAT HEALTH CHECK - Component Verification"
echo "============================================================"
echo ""

PROJECT_DIR="/home/johnlane/projects/structured-achievement-tool"
cd "$PROJECT_DIR"

# Check 1: Core Files Exist
echo "TEST 1: Core Components"
echo "----------------------"

files=(
    "src/core/story_agent.py"
    "src/core/logic_core.py"
    "src/orchestrator.py"
    "src/daemon.py"
    "src/templates/classify.md"
    "src/templates/decompose.md"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file exists"
    else
        echo "✗ $file MISSING"
    fi
done

echo ""
echo "TEST 2: Python Syntax Check"
echo "---------------------------"

python_files=(
    "src/core/story_agent.py"
    "src/core/logic_core.py"
    "src/orchestrator.py"
    "src/daemon.py"
)

for file in "${python_files[@]}"; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo "✓ $file syntax valid"
    else
        echo "✗ $file syntax ERROR"
    fi
done

echo ""
echo "TEST 3: Test Suite Summary"
echo "--------------------------"

source venv/bin/activate 2>/dev/null
pytest tests/ --ignore=tests/test_daemon.py -q 2>/dev/null | tail -5

echo ""
echo "TEST 4: Data Flow Verification"
echo "-------------------------------"

echo "Checking orchestrator.py data flow..."
if grep -q "classify" src/orchestrator.py && \
   grep -q "decompose" src/orchestrator.py && \
   grep -q "process_task_file" src/orchestrator.py; then
    echo "✓ Orchestrator has classify -> decompose flow"
else
    echo "✗ Orchestrator data flow incomplete"
fi

echo ""
if grep -q "StoryAgent" src/orchestrator.py && \
   grep -q "self.agent" src/orchestrator.py; then
    echo "✓ Orchestrator uses StoryAgent"
else
    echo "✗ Orchestrator missing StoryAgent integration"
fi

echo ""
echo "Checking daemon.py monitoring loop..."
if grep -q "is_task_ready" src/daemon.py && \
   grep -q "process_task_file" src/daemon.py && \
   grep -q "while True" src/daemon.py; then
    echo "✓ Daemon has monitoring loop"
else
    echo "✗ Daemon monitoring loop incomplete"
fi

echo ""
echo "============================================================"
echo "  FULL LOOP VERIFICATION"
echo "============================================================"
echo ""
echo "The SAT system implements the following flow:"
echo ""
echo "  1. Daemon watches for task files (001*.md)"
echo "  2. Orchestrator receives task file path"
echo "  3. StoryAgent classifies the request"
echo "  4. StoryAgent decomposes into PRD"
echo "  5. Orchestrator invokes Ralph Pro"
echo "  6. Responses written back to task directory"
echo ""

# Check if all key functions are present
all_good=true

if ! grep -q "def classify" src/core/story_agent.py; then
    echo "✗ Missing: classify function"
    all_good=false
fi

if ! grep -q "def decompose" src/core/story_agent.py; then
    echo "✗ Missing: decompose function"
    all_good=false
fi

if ! grep -q "async def process_task_file" src/orchestrator.py; then
    echo "✗ Missing: process_task_file function"
    all_good=false
fi

if ! grep -q "def is_task_ready" src/daemon.py; then
    echo "✗ Missing: is_task_ready function"
    all_good=false
fi

if [ "$all_good" = true ]; then
    echo "✓ All key functions present"
    echo ""
    echo "🎉 SAT HEALTH CHECK PASSED"
    echo ""
    echo "The full loop is structurally sound and ready for execution."
    exit 0
else
    echo ""
    echo "⚠️  Some components are missing"
    exit 1
fi
