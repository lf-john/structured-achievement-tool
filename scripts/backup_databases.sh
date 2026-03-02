#!/usr/bin/env bash
# Daily SQLite backup for SAT databases.
# Uses Python's sqlite3.backup() for safe, consistent copies.
# Keeps 7 days of backups, automatically prunes older ones.

set -euo pipefail

MEMORY_DIR="$HOME/projects/structured-achievement-tool/.memory"
BACKUP_DIR="$MEMORY_DIR/backups"
DATE=$(date +%Y-%m-%d)
KEEP_DAYS=7
PYTHON="$HOME/projects/structured-achievement-tool/venv/bin/python"

# Databases to back up
DBS=(
    "vectors.db"
    "sat.db"
    "checkpoints.db"
    "langgraph_checkpoints.db"
    "task_vectors.db"
)

mkdir -p "$BACKUP_DIR"

backed_up=0
skipped=0

for db in "${DBS[@]}"; do
    src="$MEMORY_DIR/$db"
    if [ ! -f "$src" ]; then
        skipped=$((skipped + 1))
        continue
    fi
    dest="$BACKUP_DIR/${db%.db}_${DATE}.db"
    # Use Python sqlite3.backup() for crash-safe copy
    $PYTHON -c "
import sqlite3
src = sqlite3.connect('$src')
dst = sqlite3.connect('$dest')
src.backup(dst)
dst.close()
src.close()
"
    backed_up=$((backed_up + 1))
done

# Back up known_issues.json (non-SQLite config file)
KNOWN_ISSUES="$HOME/.config/sat/known_issues.json"
if [ -f "$KNOWN_ISSUES" ]; then
    cp "$KNOWN_ISSUES" "$BACKUP_DIR/known_issues_${DATE}.json"
    backed_up=$((backed_up + 1))
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Backed up $backed_up items ($skipped skipped) to $BACKUP_DIR"

# Prune backups older than KEEP_DAYS
find "$BACKUP_DIR" \( -name "*.db" -o -name "*.json" \) -mtime +$KEEP_DAYS -delete 2>/dev/null || true

pruned=$(find "$BACKUP_DIR" \( -name "*.db" -o -name "*.json" \) | wc -l)
echo "$(date '+%Y-%m-%d %H:%M:%S') - $pruned backup files retained (keeping $KEEP_DAYS days)"
