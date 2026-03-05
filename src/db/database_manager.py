"""
Database Manager — SQLite state management for SAT.

Tracks tasks, stories, events, error signatures, learnings, and notifications.
Uses WAL mode for concurrent read access (dashboard + daemon).
"""

import json
import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    prd_id TEXT,
    source_file TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE TABLE IF NOT EXISTS stories (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'Dev',
    status TEXT NOT NULL DEFAULT 'pending',
    complexity INTEGER DEFAULT 5,
    phase TEXT,
    depends_on TEXT DEFAULT '[]',
    worktree_path TEXT,
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 5,
    verification_agents TEXT DEFAULT '[]',
    acceptance_criteria TEXT DEFAULT '[]',
    outcome_verification INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','utc')),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT,
    task_id TEXT,
    event_type TEXT NOT NULL,
    phase TEXT,
    provider TEXT,
    detail TEXT,
    tokens_used INTEGER,
    cost_estimate REAL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE TABLE IF NOT EXISTS error_signatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_hash TEXT NOT NULL,
    error_pattern TEXT NOT NULL,
    fix_applied TEXT,
    success INTEGER DEFAULT 0,
    story_id TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    anti_patterns TEXT DEFAULT '[]',
    timestamp TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT,
    task_id TEXT,
    notification_type TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'ntfy',
    recipient TEXT,
    title TEXT,
    message TEXT,
    status TEXT NOT NULL DEFAULT 'sent',
    sent_at TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE TABLE IF NOT EXISTS prd_sessions (
    id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    phase INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    file_path TEXT,
    prd_content TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE INDEX IF NOT EXISTS idx_stories_task_id ON stories(task_id);
CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(status);
CREATE INDEX IF NOT EXISTS idx_events_story_id ON events(story_id);
CREATE INDEX IF NOT EXISTS idx_events_task_id ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_error_signatures_hash ON error_signatures(error_hash);
CREATE INDEX IF NOT EXISTS idx_notifications_task_id ON notifications(task_id);
CREATE INDEX IF NOT EXISTS idx_prd_sessions_project ON prd_sessions(project);

CREATE TABLE IF NOT EXISTS task_states (
    task_path TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    signal TEXT DEFAULT 'pending',
    updated_at TEXT NOT NULL DEFAULT (datetime('now','utc')),
    retry_count INTEGER DEFAULT 0,
    error_summary TEXT,
    last_worker TEXT,
    priority TEXT DEFAULT 'normal',
    project TEXT DEFAULT 'structured-achievement-tool',
    test_command TEXT,
    depends_on TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_task_states_status ON task_states(status);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    project_dir TEXT NOT NULL,
    test_dir TEXT,
    source_dir TEXT,
    config_file TEXT,
    git_repo TEXT,
    default_branch TEXT DEFAULT 'main',
    test_command TEXT DEFAULT 'pytest tests/ -v',
    worktree_base TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
"""

TASK_TRANSITIONS = {
    "pending": ("working", "cancelled"),
    "working": ("complete", "failed", "cancelled"),
    "cancelled": ("pending", "working", "failed", "complete", "cancelled"),
}

STORY_TRANSITIONS = {
    "pending": ("working", "blocked", "cancelled"),
    "blocked": ("pending", "working", "failed", "cancelled"),
    "working": ("working", "debug", "cancelled", "complete", "failed"),
    "failed": ("working", "failed", "cancelled"),
    "debug": ("working", "failed", "cancelled"),
    "complete": ("pending", "blocked", "working", "failed", "debug", "complete", "cancelled"),
}


class DatabaseManager:
    """SQLite state manager for SAT tasks, stories, and events."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.expanduser("~/projects/structured-achievement-tool"),
                ".memory", "sat.db",
            )
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _gen_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    # --- Tasks ---

    def create_task(self, project: str, title: str, source_file: str = None, prd_id: str = None) -> str:
        task_id = self._gen_id()
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks (id, project, title, status, prd_id, source_file, created_at, updated_at) "
                "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)",
                (task_id, project, title, prd_id, source_file, now, now),
            )
            self._log_event(conn, "task_created", task_id=task_id)
        return task_id

    def update_task_status(self, task_id: str, new_status: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                logger.error(f"Task {task_id} not found")
                return False
            old_status = row["status"]
            allowed = TASK_TRANSITIONS.get(old_status, ())
            if new_status not in allowed:
                logger.error(f"Invalid task transition {old_status} -> {new_status}")
                return False
            now = self._now()
            conn.execute(
                "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                (new_status, now, task_id),
            )
            self._log_event(conn, "task_status_change", task_id=task_id, detail=f"{old_status}->{new_status}")
        return True

    def get_task(self, task_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            return dict(row) if row else None

    def get_tasks_by_project(self, project: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM tasks WHERE project=? ORDER BY created_at DESC", (project,)).fetchall()
            return [dict(r) for r in rows]

    def get_active_tasks(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status IN ('pending', 'working') ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Stories ---

    def create_story(
        self, task_id: str, title: str, story_type: str = "development",
        complexity: int = 5, depends_on: list[str] = None,
        acceptance_criteria: list[str] = None,
        verification_agents: list[str] = None,
        outcome_verification: bool = False,
    ) -> str:
        story_id = self._gen_id()
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO stories (id, task_id, title, type, status, complexity, "
                "depends_on, acceptance_criteria, verification_agents, outcome_verification, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)",
                (
                    story_id, task_id, title, story_type, complexity,
                    json.dumps(depends_on or []),
                    json.dumps(acceptance_criteria or []),
                    json.dumps(verification_agents or []),
                    1 if outcome_verification else 0,
                    now, now,
                ),
            )
            self._log_event(conn, "story_created", story_id=story_id, task_id=task_id)
        return story_id

    def update_story_status(self, story_id: str, new_status: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT status, task_id FROM stories WHERE id=?", (story_id,)).fetchone()
            if not row:
                logger.error(f"Story {story_id} not found")
                return False
            old_status = row["status"]
            allowed = STORY_TRANSITIONS.get(old_status, ())
            if new_status not in allowed:
                logger.error(f"Invalid story transition {old_status} -> {new_status}")
                return False
            now = self._now()
            conn.execute(
                "UPDATE stories SET status=?, updated_at=? WHERE id=?",
                (new_status, now, story_id),
            )
            self._log_event(conn, "story_status_change", story_id=story_id, task_id=row["task_id"],
                            detail=f"{old_status}->{new_status}")
        return True

    def update_story_phase(self, story_id: str, phase: str):
        with self._connect() as conn:
            row = conn.execute("SELECT task_id FROM stories WHERE id=?", (story_id,)).fetchone()
            now = self._now()
            conn.execute("UPDATE stories SET phase=?, updated_at=? WHERE id=?", (phase, now, story_id))
            if row:
                self._log_event(conn, "phase_change", story_id=story_id, task_id=row["task_id"], phase=phase)

    def increment_story_attempt(self, story_id: str) -> int:
        with self._connect() as conn:
            conn.execute(
                "UPDATE stories SET attempt_count = attempt_count + 1, updated_at=? WHERE id=?",
                (self._now(), story_id),
            )
            row = conn.execute("SELECT attempt_count FROM stories WHERE id=?", (story_id,)).fetchone()
            return row["attempt_count"] if row else 0

    def set_story_worktree(self, story_id: str, worktree_path: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE stories SET worktree_path=?, updated_at=? WHERE id=?",
                (worktree_path, self._now(), story_id),
            )

    def get_story(self, story_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM stories WHERE id=?", (story_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            for field in ("depends_on", "acceptance_criteria", "verification_agents"):
                try:
                    d[field] = json.loads(d.get(field, "[]"))
                except (json.JSONDecodeError, TypeError):
                    d.setdefault(field, [])
            return d

    def get_stories_for_task(self, task_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM stories WHERE task_id=? ORDER BY created_at", (task_id,)
            ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                for field in ("depends_on", "acceptance_criteria", "verification_agents"):
                    try:
                        d[field] = json.loads(d.get(field, "[]"))
                    except (json.JSONDecodeError, TypeError):
                        d.setdefault(field, [])
                result.append(d)
            return result

    def get_ready_stories(self, task_id: str) -> list[dict]:
        stories = self.get_stories_for_task(task_id)
        ready = []
        for s in stories:
            if s["status"] == "pending":
                deps = s.get("depends_on", [])
                if all(
                    d.get("status") == "complete"
                    for d in stories
                    if d["id"] in deps
                ):
                    ready.append(s)
        return ready

    def get_stuck_stories(self, timeout_minutes: int = 30) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM stories WHERE status='working' "
                "AND updated_at < datetime('now', '-' || ? || ' minutes')",
                (timeout_minutes,),
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Events ---

    def _log_event(
        self, conn: sqlite3.Connection, event_type: str,
        story_id: str = None, task_id: str = None, phase: str = None,
        provider: str = None, detail: str = None,
        tokens_used: int = None, cost_estimate: float = None,
    ):
        conn.execute(
            "INSERT INTO events (story_id, task_id, event_type, phase, provider, detail, "
            "tokens_used, cost_estimate, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (story_id, task_id, event_type, phase, provider, detail,
             tokens_used, cost_estimate, self._now()),
        )

    def log_event(
        self, event_type: str, story_id: str = None, task_id: str = None,
        phase: str = None, provider: str = None, detail: str = None,
        tokens_used: int = None, cost_estimate: float = None,
    ):
        with self._connect() as conn:
            self._log_event(conn, event_type, story_id, task_id, phase,
                            provider, detail, tokens_used, cost_estimate)

    def get_recent_events(self, limit: int = 50, story_id: str = None, task_id: str = None) -> list[dict]:
        with self._connect() as conn:
            query = ["SELECT * FROM events"]
            params = []
            if story_id:
                query.append("WHERE story_id=?")
                params.append(story_id)
            elif task_id:
                query.append("WHERE task_id=?")
                params.append(task_id)
            query.append("ORDER BY timestamp DESC LIMIT ?")
            params.append(limit)
            rows = conn.execute(" ".join(query), params).fetchall()
            return [dict(r) for r in rows]

    # --- Error Signatures ---

    def store_error_signature(
        self, error_hash: str, error_pattern: str,
        fix_applied: str = None, success: bool = False, story_id: str = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO error_signatures (error_hash, error_pattern, fix_applied, success, story_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (error_hash, error_pattern, fix_applied, 1 if success else 0, story_id),
            )
            return cursor.lastrowid

    def lookup_error_signature(self, error_hash: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM error_signatures WHERE error_hash=? ORDER BY timestamp DESC LIMIT 1",
                (error_hash,),
            ).fetchone()
            return dict(row) if row else None

    # --- Learnings ---

    def store_learning(
        self, story_id: str, category: str, content: str,
        anti_patterns: list[str] = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO learnings (story_id, category, content, anti_patterns) VALUES (?, ?, ?, ?)",
                (story_id, category, content, json.dumps(anti_patterns or [])),
            )
            return cursor.lastrowid

    def get_recent_anti_patterns(self, limit: int = 10) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT anti_patterns FROM learnings WHERE anti_patterns != '[]' "
                "ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            patterns = []
            for row in rows:
                patterns.extend(json.loads(row["anti_patterns"]))
            return patterns

    # --- Notifications ---

    def log_notification(
        self, notification_type: str, channel: str, title: str, message: str,
        task_id: str = None, story_id: str = None, recipient: str = None,
        status: str = "sent",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO notifications (notification_type, channel, title, message, "
                "task_id, story_id, recipient, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (notification_type, channel, title, message, task_id, story_id, recipient, status),
            )
            return cursor.lastrowid

    # --- PRD Sessions ---

    def create_prd_session(self, project: str, file_path: str = None) -> str:
        session_id = self._gen_id()
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO prd_sessions (id, project, phase, status, file_path, created_at, updated_at) "
                "VALUES (?, ?, 1, 'active', ?, ?, ?)",
                (session_id, project, file_path, now, now),
            )
        return session_id

    def update_prd_session(
        self, session_id: str, phase: int = None,
        status: str = None, prd_content: str = None,
    ):
        with self._connect() as conn:
            updates = []
            params = []
            updates.append("updated_at=?")
            params.append(self._now())
            if phase is not None:
                updates.append("phase=?")
                params.append(phase)
            if status is not None:
                updates.append("status=?")
                params.append(status)
            if prd_content is not None:
                updates.append("prd_content=?")
                params.append(prd_content)
            params.append(session_id)
            conn.execute(
                f"UPDATE prd_sessions SET {', '.join(updates)} WHERE id=?",
                params,
            )

    def get_active_prd_session(self, project: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM prd_sessions WHERE project=? AND status='active' "
                "ORDER BY created_at DESC LIMIT 1",
                (project,),
            ).fetchone()
            return dict(row) if row else None

    # --- Summaries ---

    def get_task_summary(self, task_id: str) -> dict:
        task = self.get_task(task_id)
        stories = self.get_stories_for_task(task_id)
        return {
            "task": task,
            "total_stories": len(stories),
            "completed": sum(1 for s in stories if s["status"] == "complete"),
            "failed": sum(1 for s in stories if s["status"] == "failed"),
            "working": sum(1 for s in stories if s["status"] == "working"),
            "pending": sum(1 for s in stories if s["status"] == "pending"),
            "stories": stories,
        }

    # --- Task State Hub (Option D) ---
    # Moves state coordination off FUSE mount to SQLite for reliability.

    TASK_STATE_TRANSITIONS = {
        "pending": ("working", "cancelled"),
        "working": ("finished", "failed", "cancelled", "pending"),
        "failed": ("pending", "cancelled"),
        "finished": ("pending",),
        "cancelled": ("pending",),
    }

    def upsert_task_state(
        self, task_path: str, status: str, signal: str = "pending",
        error_summary: str = None, last_worker: str = None,
        priority: str = "normal", project: str = None,
        test_command: str = None, depends_on: list = None,
    ):
        """Insert or update a task's state in the hub.

        Called by daemon when it detects a new task file on FUSE, and on
        every state transition thereafter. The FUSE file tags are still
        written for Obsidian display, but the hub is the source of truth
        for coordination between daemon and monitor.
        """
        now = self._now()
        depends_on_json = json.dumps(depends_on) if depends_on else None
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO task_states (task_path, status, signal, updated_at, error_summary, last_worker, priority, project, test_command, depends_on) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(task_path) DO UPDATE SET "
                "status=excluded.status, signal=excluded.signal, updated_at=excluded.updated_at, "
                "error_summary=COALESCE(excluded.error_summary, task_states.error_summary), "
                "last_worker=COALESCE(excluded.last_worker, task_states.last_worker), "
                "priority=excluded.priority, "
                "project=COALESCE(excluded.project, task_states.project), "
                "test_command=COALESCE(excluded.test_command, task_states.test_command), "
                "depends_on=COALESCE(excluded.depends_on, task_states.depends_on)",
                (task_path, status, signal, now, error_summary, last_worker, priority, project, test_command, depends_on_json),
            )

    def transition_task_state(self, task_path: str, new_status: str, **kwargs) -> bool:
        """Atomically transition a task's state with validation.

        Returns True if transition succeeded, False if invalid.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM task_states WHERE task_path=?", (task_path,)
            ).fetchone()
            if not row:
                logger.warning(f"Task state not found for {task_path}, creating")
                self.upsert_task_state(task_path, new_status, **kwargs)
                return True
            old_status = row["status"]
            allowed = self.TASK_STATE_TRANSITIONS.get(old_status, ())
            if new_status not in allowed:
                logger.error(f"Invalid task state transition {old_status} -> {new_status} for {task_path}")
                return False
            now = self._now()
            updates = ["status=?", "updated_at=?"]
            params = [new_status, now]
            if kwargs.get("error_summary"):
                updates.append("error_summary=?")
                params.append(kwargs["error_summary"])
            if kwargs.get("signal"):
                updates.append("signal=?")
                params.append(kwargs["signal"])
            if kwargs.get("last_worker"):
                updates.append("last_worker=?")
                params.append(kwargs["last_worker"])
            params.append(task_path)
            conn.execute(
                f"UPDATE task_states SET {', '.join(updates)} WHERE task_path=?",
                params,
            )
            self._log_event(conn, "task_state_transition", detail=f"{old_status}->{new_status}: {task_path}")
        return True

    def increment_task_retry(self, task_path: str) -> int:
        """Increment retry count and return new value."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE task_states SET retry_count = retry_count + 1, updated_at=? WHERE task_path=?",
                (self._now(), task_path),
            )
            row = conn.execute(
                "SELECT retry_count FROM task_states WHERE task_path=?", (task_path,)
            ).fetchone()
            return row["retry_count"] if row else 0

    def get_task_state(self, task_path: str) -> dict | None:
        """Get the current state of a task from the hub."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_states WHERE task_path=?", (task_path,)
            ).fetchone()
            return dict(row) if row else None

    def get_tasks_by_state(self, status: str) -> list[dict]:
        """Get all tasks with a given status."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM task_states WHERE status=? "
                "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 WHEN 'low' THEN 2 END, updated_at",
                (status,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stuck_task_states(self, timeout_minutes: int = 30) -> list[dict]:
        """Get tasks stuck in 'working' state beyond the timeout."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM task_states WHERE status='working' "
                "AND updated_at < datetime('now', '-' || ? || ' minutes')",
                (timeout_minutes,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_failed_task_states(self, max_retries: int = 10) -> list[dict]:
        """Get failed tasks that haven't exceeded max retries."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM task_states WHERE status='failed' AND retry_count < ?",
                (max_retries,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_project_stories_by_state(self, project: str, statuses: list[str]) -> list[dict]:
        """Get all task_states for a project matching the given statuses."""
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in statuses)
            rows = conn.execute(
                f"SELECT * FROM task_states WHERE project=? AND status IN ({placeholders}) "
                "ORDER BY updated_at",
                [project] + statuses,
            ).fetchall()
            return [dict(r) for r in rows]

    def has_active_debug_story(self, project: str) -> bool:
        """Check if there's a pending or working debug/high-priority story for a project."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM task_states "
                "WHERE project=? AND priority='high' AND status IN ('pending', 'working')",
                (project,),
            ).fetchone()
            return row["c"] > 0

    def find_task_state_by_name(self, name: str) -> dict | None:
        """Find a task_state by basename match.

        Searches for task_paths whose basename matches the given name.
        Used for prerequisite resolution (depends_on stores basenames).
        """
        with self._connect() as conn:
            # Try exact path match first
            row = conn.execute(
                "SELECT * FROM task_states WHERE task_path=?", (name,)
            ).fetchone()
            if row:
                return dict(row)
            # Fall back to basename match (LIKE %/name)
            row = conn.execute(
                "SELECT * FROM task_states WHERE task_path LIKE ? ORDER BY updated_at DESC LIMIT 1",
                (f"%/{name}",),
            ).fetchone()
            if row:
                return dict(row)
            # Try partial match (name might be without extension)
            row = conn.execute(
                "SELECT * FROM task_states WHERE task_path LIKE ? ORDER BY updated_at DESC LIMIT 1",
                (f"%{name}%",),
            ).fetchone()
            return dict(row) if row else None

    def add_dependency_to_task(self, task_path: str, dependency: str) -> bool:
        """Add a dependency to a task's depends_on list.

        Used to dynamically add prerequisites (e.g., when a Debug story
        is created and queued project stories should wait for it).

        Args:
            task_path: The task to add the dependency to.
            dependency: The dependency identifier to add.

        Returns:
            True if the dependency was added.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT depends_on FROM task_states WHERE task_path=?", (task_path,)
            ).fetchone()
            if not row:
                return False
            try:
                current = json.loads(row["depends_on"] or "[]")
            except (json.JSONDecodeError, TypeError):
                current = []
            if dependency not in current:
                current.append(dependency)
                conn.execute(
                    "UPDATE task_states SET depends_on=?, updated_at=? WHERE task_path=?",
                    (json.dumps(current), self._now(), task_path),
                )
            return True

    def clear_task_state(self, task_path: str):
        """Remove a task from the state hub (e.g., when finished and acknowledged)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM task_states WHERE task_path=?", (task_path,))

    # --- Projects ---

    def create_project(
        self, name: str, project_dir: str, test_dir: str = None,
        source_dir: str = None, config_file: str = None,
        git_repo: str = None, default_branch: str = "main",
        test_command: str = "pytest tests/ -v",
        worktree_base: str = None,
    ) -> str:
        project_id = self._gen_id()
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, project_dir, test_dir, source_dir, "
                "config_file, git_repo, default_branch, test_command, worktree_base, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, name, project_dir, test_dir, source_dir,
                 config_file, git_repo, default_branch, test_command,
                 worktree_base, now, now),
            )
            self._log_event(conn, "project_created", detail=f"project={name}")
        return project_id

    def get_project(self, project_id_or_name: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id=? OR name=?",
                (project_id_or_name, project_id_or_name),
            ).fetchone()
            return dict(row) if row else None

    def get_all_projects(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY name"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_project(self, project_id: str, **kwargs):
        allowed = {"name", "project_dir", "test_dir", "source_dir",
                    "config_file", "git_repo", "default_branch",
                    "test_command", "worktree_base"}
        updates = ["updated_at=?"]
        params = [self._now()]
        for key, value in kwargs.items():
            if key not in allowed:
                raise ValueError(f"Invalid project field: {key}")
            updates.append(f"{key}=?")
            params.append(value)
        if len(updates) == 1:
            return  # nothing to update
        params.append(project_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE projects SET {', '.join(updates)} WHERE id=?",
                params,
            )

    def get_project_for_task(self, task_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT p.* FROM projects p "
                "JOIN tasks t ON t.project = p.name "
                "WHERE t.id=?",
                (task_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_system_status(self) -> dict:
        """Overall system status for monitoring."""
        with self._connect() as conn:
            active_tasks = conn.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE status IN ('pending', 'working')"
            ).fetchone()["c"]
            working_stories = conn.execute(
                "SELECT COUNT(*) as c FROM stories WHERE status='working'"
            ).fetchone()["c"]
            failed_stories = conn.execute(
                "SELECT COUNT(*) as c FROM stories WHERE status='failed'"
            ).fetchone()["c"]
            recent_events = conn.execute(
                "SELECT COUNT(*) as c FROM events WHERE timestamp > datetime('now', '-1 hour')"
            ).fetchone()["c"]
        return {
            "active_tasks": active_tasks,
            "working_stories": working_stories,
            "failed_stories": failed_stories,
            "events_last_hour": recent_events,
        }
