"""Centralized path configuration for SAT.

All paths are derived from environment variables with sensible defaults.
Components should import from here instead of hardcoding paths.

Environment variables (set in ~/.config/sat/env, loaded by systemd):
    SAT_PROJECT_DIR  — Root of the SAT project (default: auto-detect from this file)
    SAT_TASKS_DIR    — Root of task files on Google Drive FUSE mount
    SAT_GDRIVE_ROOT  — Root of Google Drive DriveSyncFiles directory
"""

import os
from pathlib import Path

# --- Core paths ---

# Project root: prefer env var, fall back to auto-detection from this file's location
SAT_PROJECT_DIR = Path(os.environ.get(
    "SAT_PROJECT_DIR",
    str(Path(__file__).resolve().parent.parent.parent),
))

# Google Drive roots
SAT_GDRIVE_ROOT = Path(os.environ.get(
    "SAT_GDRIVE_ROOT",
    str(Path.home() / "GoogleDrive" / "DriveSyncFiles"),
))

SAT_TASKS_DIR = Path(os.environ.get(
    "SAT_TASKS_DIR",
    str(SAT_GDRIVE_ROOT / "sat-tasks"),
))

# --- Derived paths ---

# .memory directory for databases, state, journals
MEMORY_DIR = SAT_PROJECT_DIR / ".memory"

# Database files
SAT_DB = MEMORY_DIR / "sat.db"
CHECKPOINT_DB = MEMORY_DIR / "checkpoints.db"
VECTORS_DB = MEMORY_DIR / "vectors.db"
LLM_COST_DB = MEMORY_DIR / "llm_costs.db"

# Logs
LOG_DIR = SAT_PROJECT_DIR / "logs"
SAT_LOG = LOG_DIR / "sat.log"

# Audit and state
AUDIT_JOURNAL = MEMORY_DIR / "audit_journal.jsonl"
PROACTIVE_STATE = MEMORY_DIR / "proactive_state.json"
RETRY_COUNTS = MEMORY_DIR / "retry_counts.json"
RATE_LIMIT_STATE = MEMORY_DIR / "rate_limit_state.json"

# Config
CONFIG_JSON = SAT_PROJECT_DIR / "config.json"

# FUSE sentinel
FUSE_SENTINEL = SAT_TASKS_DIR / "CLAUDE.md"

# Task subdirectories watched by monitor
MONITOR_WATCH_DIRS = [
    SAT_TASKS_DIR / "sat-enhancements",
    SAT_TASKS_DIR / "marketing-automation",
    SAT_TASKS_DIR / "other",
    SAT_TASKS_DIR / "maintenance",
]

# Worktrees
WORKTREE_DIR = SAT_PROJECT_DIR / "worktrees"
