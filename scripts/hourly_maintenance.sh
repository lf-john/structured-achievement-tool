#!/usr/bin/env bash
# SAT Hourly Maintenance — runs Claude Code to diagnose AND fix SAT issues
# Invoked by cron every hour. Uses git worktree for safe code changes.
# The point: fix things while the user sleeps.

set -uo pipefail
# Note: we intentionally do NOT use set -e because claude may exit non-zero
# (e.g., max turns) and we need the error detection block below to handle it.

SAT_DIR="$HOME/projects/structured-achievement-tool"
ISSUES_DIR="$HOME/GoogleDrive/DriveSyncFiles/sat-issues"
YEAR=$(TZ=America/Denver date +%Y)
MONTH=$(TZ=America/Denver date +%m)
DAY=$(TZ=America/Denver date +%d)
HOUR=$(TZ=America/Denver date +%H)

REPORT_DIR="${ISSUES_DIR}/${YEAR}/${MONTH}/${DAY}"
REPORT_FILE="${REPORT_DIR}/${HOUR}.md"

# Create report directory
mkdir -p "$REPORT_DIR"

# Skip if a VALID report already exists (prevent double-runs).
# A valid report contains "## " — error reports don't.
if [ -f "$REPORT_FILE" ] && [ -s "$REPORT_FILE" ] && grep -q "^##" "$REPORT_FILE" 2>/dev/null; then
    echo "Report already exists: $REPORT_FILE"
    exit 0
fi
# Remove any prior error report so we can try again
[ -f "$REPORT_FILE" ] && rm -f "$REPORT_FILE"

# Source environment
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$HOME/projects/structured-achievement-tool/venv/bin:$PATH"
source "$HOME/.config/sat/env" 2>/dev/null || true

# Ensure systemd user session access for service management
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

cd "$SAT_DIR"

# Create a temporary git worktree for safe code changes
WORKTREE_DIR=$(mktemp -d "${SAT_DIR}/.worktrees/hourly-XXXXXX")
WORKTREE_BRANCH="hourly-fix-$(date +%Y%m%d%H%M)"
git worktree add "$WORKTREE_DIR" -b "$WORKTREE_BRANCH" HEAD 2>/dev/null

# If worktree creation failed, fall back to main dir (report-only)
if [ $? -ne 0 ]; then
    rmdir "$WORKTREE_DIR" 2>/dev/null
    WORKTREE_DIR="$SAT_DIR"
    WORKTREE_BRANCH=""
    echo "Warning: worktree creation failed, running in report-only mode"
fi

# Run Claude Code with maintenance + fix prompt
env -u CLAUDECODE claude --print --dangerously-skip-permissions \
    --model haiku \
    --max-turns 30 \
    "$(cat <<PROMPT
You are the SAT hourly maintenance agent. Your job is to DIAGNOSE AND FIX issues.
Do not just report problems — FIX THEM. The user is sleeping and needs this to work.

Working directory (worktree for safe changes): $WORKTREE_DIR
Main SAT project: $SAT_DIR
Python venv: $SAT_DIR/venv/bin/activate

## Phase 1: Diagnose

Run these commands:
1. \`systemctl --user is-active sat.service sat-monitor.service sat-web.service\`
2. \`systemctl is-active ollama.service\`
3. \`journalctl --user -u sat.service --since "1 hour ago" --no-pager -q 2>/dev/null | tail -50\`
4. \`df -h / | tail -1 && free -h | grep Mem\`
5. \`find ~/GoogleDrive/DriveSyncFiles/sat-tasks/ -name "*.md" -newer /tmp/.sat-hour-marker 2>/dev/null | head -20\`

## Phase 2: Fix (you MUST attempt fixes)

**Service restarts** — do immediately if any service is down:
\`systemctl --user restart sat.service\`
\`systemctl --user restart sat-monitor.service\`
\`systemctl --user restart sat-web.service\`
\`sudo systemctl restart ollama\`

**Code fixes** — if you find recurring errors in the journal:
1. Read the relevant source file: \`cat $WORKTREE_DIR/src/<path>\`
2. Fix the bug (import errors, schema mismatches, missing attributes, etc.)
3. Run tests: \`cd $WORKTREE_DIR && source $SAT_DIR/venv/bin/activate && pytest tests/ --ignore=tests/test_US_001_full_sat_loop_integration.py --ignore=tests/test_daemon.py -x -q 2>&1 | tail -20\`
4. If tests pass, your changes will be automatically merged and services restarted

**Task fixes** — if tasks are stuck in <Working> for over 30 minutes:
1. Reset them to <Failed> so the monitor can retry them

**DO NOT fix** (these are transient and resolve themselves):
- API rate limit (429) errors
- Network timeout errors
- "Max turns reached" from claude CLI
- LLM response parsing errors (single-occurrence)

## Output (use exactly these headings):

## Status
One-line: healthy / degraded / critical

## Services
| Service | Status | Action |
|---------|--------|--------|
| sat.service | active/inactive | restarted / none |

## Issues Found
List each error from journal with count of occurrences

## Fixes Applied
For each fix: file path, what was wrong, what you changed.
If no fixes needed, write "System healthy — no fixes needed."

## Actions Taken
Everything you did: restarts, file edits, task resets
PROMPT
)" > "$REPORT_FILE" 2>&1

# Touch the hour marker for next run's "new files" check
touch /tmp/.sat-hour-marker

# If worktree was used and has changes, try to merge them
if [ -n "$WORKTREE_BRANCH" ] && [ "$WORKTREE_DIR" != "$SAT_DIR" ]; then
    cd "$SAT_DIR"
    # Check if there are actual changes in the worktree
    CHANGES=$(cd "$WORKTREE_DIR" && git status --porcelain 2>/dev/null | head -1)
    if [ -n "$CHANGES" ]; then
        # Commit changes in worktree
        cd "$WORKTREE_DIR"
        git add -A
        git commit -m "hourly-maintenance: auto-fix $(date +%Y-%m-%d_%H:%M)" --no-verify 2>/dev/null
        cd "$SAT_DIR"
        # Merge the fix branch
        if git merge --no-edit "$WORKTREE_BRANCH" 2>/dev/null; then
            echo "Merged hourly fix from $WORKTREE_BRANCH"
            # Restart SAT to pick up changes
            systemctl --user restart sat.service 2>/dev/null
        else
            echo "Merge conflict — fix remains on branch $WORKTREE_BRANCH for manual review"
            git merge --abort 2>/dev/null
        fi
    fi
    # Clean up worktree
    git worktree remove "$WORKTREE_DIR" --force 2>/dev/null
    git branch -D "$WORKTREE_BRANCH" 2>/dev/null
fi

# If claude failed, produced empty output, or hit max turns, write error report
if [ ! -s "$REPORT_FILE" ] || grep -q "^Error:" "$REPORT_FILE" 2>/dev/null; then
    ERRMSG=""
    [ -s "$REPORT_FILE" ] && ERRMSG=$(cat "$REPORT_FILE")
    cat > "$REPORT_FILE" <<EOF
# SAT Maintenance Report — $(TZ=America/Denver date '+%Y-%m-%d %H:00 MT')

**Status**: Maintenance script failed — Claude Code did not produce a valid report.

**Error output**: ${ERRMSG:-"(no output)"}

Check: \`journalctl --user -u sat.service --since "1 hour ago"\`
EOF
fi

echo "Report written to: $REPORT_FILE"
