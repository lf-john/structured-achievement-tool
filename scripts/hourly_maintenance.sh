#!/usr/bin/env bash
# SAT Hourly Maintenance — runs Claude Code to diagnose AND fix SAT issues
# Invoked by cron every hour. Uses git worktree for safe code changes.
# The point: fix things while the user sleeps.

set -uo pipefail
# Note: we intentionally do NOT use set -e because claude may exit non-zero
# (e.g., max turns) and we need the error detection block below to handle it.

SAT_DIR="$HOME/projects/structured-achievement-tool"
ISSUES_DIR="$HOME/GoogleDrive/DriveSyncFiles/sat-issues"
KNOWN_ISSUES_FILE="$HOME/.config/sat/known_issues.json"
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

# Initialize known-issues file if it doesn't exist
if [ ! -f "$KNOWN_ISSUES_FILE" ]; then
    echo '{}' > "$KNOWN_ISSUES_FILE"
fi

# Read known issues for dedup context
KNOWN_ISSUES_CONTENT=$(cat "$KNOWN_ISSUES_FILE" 2>/dev/null || echo '{}')

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

# Build the prompt with variable substitutions done inline via heredoc
# We use a mix: the parts needing variable expansion use unquoted heredoc,
# the static parts are literal strings. All concatenated.
PROMPT_TEXT="$(cat <<VARBLOCK
You are the SAT (Structured Achievement Tool) hourly maintenance agent. Your job is to
DIAGNOSE AND FIX issues. Do not just report problems — FIX THEM. The user is sleeping
and needs this to work.

Working directory (worktree for safe changes): $WORKTREE_DIR
Main SAT project: $SAT_DIR
Python venv: $SAT_DIR/venv/bin/activate
Current timestamp: $(TZ=America/Denver date -Iseconds)
VARBLOCK
)"

PROMPT_TEXT+='

======================================================================
SYSTEM ARCHITECTURE — READ THIS CAREFULLY
======================================================================

SAT is an autonomous task orchestration system. Users write Markdown task files in
Obsidian, which sync to Google Drive via rclone FUSE mount. The SAT daemon picks them
up, decomposes them into TDD-driven stories, executes them via Claude CLI in isolated
git worktrees, and writes results back to the task files.

### Data Flow
```
User writes .md file in Obsidian -> rclone syncs to ~/GoogleDrive/ ->
SAT daemon detects <Pending> tag -> Orchestrator classifies & decomposes ->
Stories execute in git worktrees via Claude CLI -> Results embedded in vector memory ->
Response written back to task file -> rclone syncs back to Obsidian
```

### Project Structure
```
~/projects/structured-achievement-tool/   (SAT_DIR — main project root)
|-- src/
|   |-- daemon.py              — Main daemon: watches for .md files with <Pending> tag
|   |-- monitor.py             — Queue monitor: 2-min cycle, retries <Failed> tasks
|   |-- orchestrator_v2.py     — Task classification, decomposition, delegation
|   |-- health_check.py        — 15-min health check (separate cron)
|   |-- core/
|   |   |-- story_agent.py     — Classifies task type, decomposes into stories
|   |   |-- logic_core.py      — Claude CLI wrapper for LLM calls
|   |   |-- phase_runner.py    — Executes phases via Claude/Gemini CLI
|   |   |-- langgraph_orchestrator.py — State machine: DESIGN->TDD_RED->CODE->TDD_GREEN->VERIFY->LEARN
|   |   |-- embedding_service.py     — Ollama nomic-embed-text embeddings
|   |   |-- vector_store.py          — sqlite-vec similarity search
|   |   |-- context_retriever.py     — RAG context injection
|   |-- monitoring/            — Metrics, dashboards
|   |-- web/                   — Web dashboard
|   |-- llm/                   — LLM routing, cost tracking
|-- tests/                     — Mirrors src/ structure; TDD-driven
|-- scripts/
|   |-- hourly_maintenance.sh  — THIS SCRIPT
|-- venv/                      — Python virtual environment
|-- .memory/
|   |-- vectors.db             — Vector memory (DO NOT DELETE)
|   |-- checkpoints.db         — Checkpoint system for resumable execution
|-- .worktrees/                — Git worktrees for isolated story execution
|-- logs/
    |-- health_check.log       — Health check output
```

### Services (systemd --user)
| Service              | What it does                                          |
|----------------------|-------------------------------------------------------|
| sat.service          | Main daemon — watches for tasks, executes stories     |
| sat-monitor.service  | Queue monitor — 2-min cycle, retries failures         |
| sat-web.service      | Web dashboard (optional, may not be running)          |

System-level service:
| ollama.service       | Local LLM inference (GPU, nomic-embed-text)           |

### Task File System
Task files live at: ~/GoogleDrive/DriveSyncFiles/sat-tasks/
Subdirectories: sat-enhancements/, marketing-automation/, other/

Tags (state machine — these appear in the .md file body):
- <Pending>  — Ready for processing (daemon picks up)
- <Working>  — Currently being processed by the daemon
- <Finished> — Completed successfully
- <Failed>   — Execution failed (monitor will retry)
- <Cancel>   — User requested cancellation
- # <Pending> — Response placeholder; user removes # to continue conversation

### Daemon Behavior (src/daemon.py)
- Polls every 5 seconds for .md files containing <Pending>
- Uses os.fsync() for Google Drive FUSE reliability
- Has 2 concurrent execution slots
- Transitions task: <Pending> -> <Working> -> <Finished> or <Failed>
- Executes stories in isolated git worktrees under .worktrees/
- Each story gets its own git branch and worktree
- Changes are committed in the worktree, then merged back to main

### Monitor Behavior (src/monitor.py)
- Runs on a 2-minute cycle
- Only processes TASK files (not response files)
- Detects stuck <Working> tasks (30-minute timeout) -> resets to <Failed>
- Retries <Failed> tasks automatically
- Handles <Failed> retry scheduling

### Human Stories and Approval Workflow — CRITICAL
- Any story that requires human input will have its checkpoint status set to 'waiting_for_human'
- You can check this by querying: sqlite3 .memory/checkpoints.db "SELECT task_id, status FROM checkpoints WHERE status = 'waiting_for_human'"
- Tasks with status='waiting_for_human' are NOT stuck. They are working as intended.
- DO NOT reset, retry, or report these tasks as failures.
- Report them separately as "Waiting for human response" — this is a normal, expected state.
- The approval signal files are at ~/GoogleDrive/DriveSyncFiles/sat-tasks/approvals/
- When a human responds, the status automatically returns to 'in_progress'

### Worktree Isolation Pattern
- Stories execute in .worktrees/<branch-name>/ directories
- Each story gets its own git branch and worktree
- Changes are committed in the worktree, then merged back to main
- Worktrees should be cleaned up after story completion

### Checkpoint System
- .memory/checkpoints.db tracks execution state for resumable tasks
- Schema: task_id TEXT, current_phase TEXT, completed_stories TEXT (JSON), pending_stories TEXT (JSON), timestamp TEXT, metadata TEXT, status TEXT
- Status values: 'in_progress' (normal execution), 'waiting_for_human' (paused for human input), 'completed', 'failed'
- Allows tasks to resume from last checkpoint after failures
- DO NOT delete or modify checkpoints.db directly — use the checkpoint queries to READ status only

### Key Log Locations
- Daemon logs:  journalctl --user -u sat.service
- Monitor logs: journalctl --user -u sat-monitor.service
- Health check: ~/projects/structured-achievement-tool/logs/health_check.log
- Hourly reports: ~/GoogleDrive/DriveSyncFiles/sat-issues/YYYY/MM/DD/HH.md

### How to Properly Restart Services
```
systemctl --user restart sat.service
systemctl --user restart sat-monitor.service
```
Wait 5 seconds after restart before checking status. The daemon needs a moment to
initialize its file watchers and execution slots.

### External Dependencies
- Ralph Pro (~/ralph-pro/): Node.js TDD execution engine
- Ollama: Local LLM inference (nomic-embed-text for embeddings, runs on RTX 3060 Ti)
- Google Drive: rclone FUSE mount at ~/GoogleDrive/ (systemd: rclone-gdrive.service)
- ntfy.sh: Push notifications to topic johnlane-claude-tasks

### Environment
- Python venv: ~/projects/structured-achievement-tool/venv/bin/activate
- Config: ~/.config/sat/env (systemd-format key=value, no export prefix)
- Known issues tracking: ~/.config/sat/known_issues.json

======================================================================
KNOWN ISSUES — DEDUPLICATION DATABASE
======================================================================

The following JSON contains issues that have already been reported in previous
maintenance runs. Use this for deduplication:

```json
'"$KNOWN_ISSUES_CONTENT"'
```

DEDUPLICATION RULES:
- Check the known-issues data above for previously reported issues.
- If an issue was already reported in the last 12 hours and its status has not
  changed, DO NOT report it again in the "Issues Found" section. Instead write
  a single line: "(N previously reported issues unchanged — skipped)"
- Only report NEW issues or issues whose STATUS HAS CHANGED (e.g., was open
  and is now fixed, or was fixed and has regressed).
- An issue is considered "the same" if it has the same root cause, even if the
  exact error message differs slightly.
- For issues that were previously open and are now resolved, report them as RESOLVED.

After completing your report, output a JSON block at the very end of your response
fenced with ```known-issues-update markers. This block must contain the FULL updated
known-issues JSON (not a diff). Structure:
```known-issues-update
{
  "issue_hash_string": {
    "description": "Brief description of the issue",
    "first_seen": "ISO timestamp of first occurrence",
    "last_seen": "ISO timestamp of this run",
    "status": "open or fixed",
    "times_reported": N
  }
}
```known-issues-update

Use descriptive hash keys like "sat_service_crashloop" or "ollama_connection_refused".
Preserve ALL existing entries from the input. Update last_seen and increment
times_reported for recurring issues. Set status to "fixed" for issues no longer present.
Add new entries for newly discovered issues.

======================================================================
COMMAND RULES — STRICTLY ENFORCED
======================================================================

### ALLOWED COMMANDS
- `systemctl --user restart sat.service`
- `systemctl --user restart sat-monitor.service`
- `systemctl --user restart sat-web.service`
- `sudo systemctl restart ollama`
- `systemctl --user status <service>` and `systemctl --user is-active <service>`
- `git worktree add` / `git worktree remove` (in the worktree pattern)
- `git worktree list`
- `git add`, `git commit` (in worktree ONLY, never on main branch directly)
- `git status`, `git log`, `git diff` (read-only, anywhere)
- Reading files: `cat`, `head`, `tail`, `less`
- Checking logs: `journalctl`
- Running tests: `pytest` (in worktree)
- Diagnostics: `find`, `ls`, `wc`, `df`, `free`, `ps`, `top -bn1`
- File search: `grep`, `rg`

### FORBIDDEN COMMANDS — NEVER USE THESE UNDER ANY CIRCUMSTANCES
- `git reset --hard`           (destroys uncommitted work)
- `git clean -f`               (destroys untracked files)
- `git checkout .`             (discards all changes)
- `git restore .`              (discards all changes)
- `git push --force`           (rewrites remote history)
- `rm -rf` on any project directory or data directory
- Modifying files directly on the main branch (always use worktree)
- Killing processes other than stuck Claude CLI instances
- Deleting .memory/vectors.db or .memory/checkpoints.db
- Deleting or modifying task files in sat-tasks/ (except resetting stuck tags)
- Any command that discards uncommitted changes
- Any command that deletes user data

If the working directory is dirty, REPORT IT but DO NOT try to clean it up.
The user will handle dirty working directories manually.

======================================================================
ROOT CAUSE PATTERNS TO FIX (if encountered in the worktree)
======================================================================

If you encounter these patterns, fix the underlying code IN THE WORKTREE:

1. **Generated test files left behind after story execution**
   Root cause: Story execution does not clean up generated test files during
   worktree teardown. Fix: Add cleanup logic to worktree teardown in the
   relevant story execution code (likely phase_runner.py or story_agent.py).

2. **Orphaned worktrees after story completion**
   Root cause: Daemon does not always clean up worktrees when a story finishes.
   Fix: Add worktree cleanup to the story completion handler in daemon.py
   or the relevant execution code. Use `git worktree remove <path> --force`.

3. **Unbounded retry loops (e.g., 242 retries of same failed task)**
   Root cause: Monitor (src/monitor.py) has no max-retry count.
   Fix: Add a max_retries counter (default 10) to monitor.py. After 10
   consecutive failures of the same task, stop retrying and leave it in
   <Failed> with an annotation like "Max retries (10) exceeded".

4. **Tasks with checkpoint status 'waiting_for_human'**
   These are NOT bugs. Check the checkpoint database:
   sqlite3 .memory/checkpoints.db "SELECT task_id, status FROM checkpoints WHERE status = 'waiting_for_human'"
   Report these as "Waiting for human response" — do not reset or fix them.

======================================================================
PHASE 1: DIAGNOSE
======================================================================

Run these diagnostic commands:
1. `systemctl --user is-active sat.service sat-monitor.service sat-web.service`
2. `systemctl is-active ollama.service`
3. `journalctl --user -u sat.service --since "1 hour ago" --no-pager -q 2>/dev/null | tail -50`
4. `journalctl --user -u sat-monitor.service --since "1 hour ago" --no-pager -q 2>/dev/null | tail -30`
5. `df -h / | tail -1 && free -h | grep Mem`
6. `sqlite3 .memory/checkpoints.db "SELECT task_id, status, current_phase FROM checkpoints" 2>/dev/null`
6. `find ~/GoogleDrive/DriveSyncFiles/sat-tasks/ -name "*.md" -newer /tmp/.sat-hour-marker 2>/dev/null | head -20`
7. `ls -la ~/projects/structured-achievement-tool/.worktrees/ 2>/dev/null | head -20`
8. `git -C ~/projects/structured-achievement-tool status --porcelain 2>/dev/null | head -10`
9. `git -C ~/projects/structured-achievement-tool worktree list 2>/dev/null`

======================================================================
PHASE 2: FIX (you MUST attempt fixes when appropriate)
======================================================================

**Service restarts** — do immediately if any service is down:
  `systemctl --user restart sat.service`
  `systemctl --user restart sat-monitor.service`
  `systemctl --user restart sat-web.service`
  `sudo systemctl restart ollama`

**Code fixes** — if you find recurring errors in the journal:
1. Read the relevant source file in the worktree
2. Fix the bug (import errors, schema mismatches, missing attributes, etc.)
3. Run tests:
   `cd '"$WORKTREE_DIR"' && source '"$SAT_DIR"'/venv/bin/activate && pytest tests/ -x -q 2>&1 | tail -20`
4. If tests pass, your changes will be automatically merged and services restarted

**Task fixes** — if tasks are stuck in <Working> for over 30 minutes:
1. First check: is the task in approvals/ or does filename contain _approval? If YES -> SKIP IT
2. Otherwise, reset to <Failed> so the monitor can retry

**Worktree cleanup** — if orphaned worktrees exist:
1. List worktrees: `git worktree list`
2. For any that are stale (no branch, broken, no running process), remove them:
   `git worktree remove <path> --force`
3. Do NOT remove worktrees that correspond to actively running stories

**DO NOT fix** (these are transient and resolve themselves):
- API rate limit (429) errors — just note them
- Network timeout errors — transient
- "Max turns reached" from claude CLI — expected behavior
- LLM response parsing errors (single-occurrence) — transient

======================================================================
OUTPUT FORMAT (use exactly these headings)
======================================================================

## Status
One-line: healthy / degraded / critical

## Services
| Service | Status | Action |
|---------|--------|--------|
| sat.service | active/inactive | restarted / none |
| sat-monitor.service | active/inactive | restarted / none |
| sat-web.service | active/inactive | restarted / none |
| ollama.service | active/inactive | restarted / none |

## Issues Found
For NEW issues: describe the issue, count of occurrences, severity.
For PREVIOUSLY REPORTED issues with no status change: "(N previously reported issues unchanged — skipped)"
For RESOLVED issues: "RESOLVED: <description>"

## Fixes Applied
For each fix: file path, what was wrong, what you changed.
If no fixes needed, write "System healthy — no fixes needed."

## Actions Taken
Everything you did: restarts, file edits, task resets, worktree cleanups.

Then output the known-issues-update JSON block as described in the deduplication section.
'

# Run Claude Code with the assembled prompt
env -u CLAUDECODE claude --print --dangerously-skip-permissions \
    --model sonnet \
    --max-turns 30 \
    "$PROMPT_TEXT" > "$REPORT_FILE" 2>&1

# Touch the hour marker for next run's "new files" check
touch /tmp/.sat-hour-marker

# Extract and update known-issues file from the report
if [ -f "$REPORT_FILE" ] && [ -s "$REPORT_FILE" ]; then
    # Extract the known-issues-update JSON block from the report
    UPDATED_ISSUES=$(sed -n '/^```known-issues-update$/,/^```known-issues-update$/{
        /^```known-issues-update$/d
        p
    }' "$REPORT_FILE" 2>/dev/null)
    if [ -n "$UPDATED_ISSUES" ]; then
        # Validate it is valid JSON before writing
        if echo "$UPDATED_ISSUES" | python3 -m json.tool > /dev/null 2>&1; then
            # Atomic rename: write to temp file, then mv (prevents partial writes)
            KNOWN_ISSUES_TMP="${KNOWN_ISSUES_FILE}.tmp.$$"
            echo "$UPDATED_ISSUES" > "$KNOWN_ISSUES_TMP"
            mv -f "$KNOWN_ISSUES_TMP" "$KNOWN_ISSUES_FILE"
            echo "Updated known-issues file: $KNOWN_ISSUES_FILE"
        else
            echo "Warning: known-issues-update block was not valid JSON, skipping update"
        fi
    fi

    # Strip the known-issues-update block from the report (machine data, not for human reading)
    sed -i '/^```known-issues-update$/,/^```known-issues-update$/d' "$REPORT_FILE" 2>/dev/null
fi

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
