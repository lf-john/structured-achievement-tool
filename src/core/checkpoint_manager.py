"""
CheckpointManager for storing and retrieving workflow checkpoints.

This module manages workflow checkpoint data in SQLite databases,
providing schema validation, error handling, and data integrity checks.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# Standard status values for checkpoint tracking
STATUS_IN_PROGRESS = "in_progress"
STATUS_WAITING_FOR_HUMAN = "waiting_for_human"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class Checkpoint:
    """
    Dataclass representing a workflow checkpoint.

    Stores information about a task's progress in the workflow system,
    including phase status, completed and pending stories, timestamps, and metadata.
    """

    def __init__(
        self,
        task_id: str,
        current_phase: str,
        completed_stories: List[str],
        pending_stories: List[str],
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = STATUS_IN_PROGRESS,
    ):
        """
        Initialize a Checkpoint.

        Args:
            task_id: Unique identifier for the task.
            current_phase: Current phase of the workflow (e.g., "TDD_GREEN").
            completed_stories: List of completed story identifiers.
            pending_stories: List of pending story identifiers.
            timestamp: ISO format timestamp. If None, uses current time.
            metadata: Optional dictionary of additional metadata.

        Raises:
            ValueError: If task_id or current_phase is empty.
        """
        if not task_id or not isinstance(task_id, str):
            raise ValueError("task_id must be a non-empty string")

        if not current_phase or not isinstance(current_phase, str):
            raise ValueError("current_phase must be a non-empty string")

        self.task_id = task_id
        self.current_phase = current_phase
        self.completed_stories = completed_stories if completed_stories else []
        self.pending_stories = pending_stories if pending_stories else []
        self.timestamp = timestamp or datetime.utcnow().isoformat()
        self.metadata = metadata if metadata else {}
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        """Convert checkpoint to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "current_phase": self.current_phase,
            "completed_stories": self.completed_stories,
            "pending_stories": self.pending_stories,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create Checkpoint from dictionary."""
        return cls(
            task_id=data.get("task_id", ""),
            current_phase=data.get("current_phase", ""),
            completed_stories=data.get("completed_stories", []),
            pending_stories=data.get("pending_stories", []),
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
            status=data.get("status", STATUS_IN_PROGRESS),
        )

    def __eq__(self, other):
        """Check equality with another Checkpoint."""
        if not isinstance(other, Checkpoint):
            return False
        return (
            self.task_id == other.task_id and
            self.current_phase == other.current_phase and
            self.completed_stories == other.completed_stories and
            self.pending_stories == other.pending_stories and
            self.timestamp == other.timestamp and
            self.metadata == other.metadata and
            self.status == other.status
        )

    def __repr__(self):
        """String representation."""
        return f"Checkpoint(task_id={self.task_id}, phase={self.current_phase}, status={self.status})"

    def __getitem__(self, key):
        """Allow subscript access to checkpoint fields."""
        return self.to_dict()[key]

    def __setitem__(self, key, value):
        """Allow setting checkpoint fields via subscript notation."""
        if key == "task_id":
            self.task_id = value
        elif key == "current_phase":
            self.current_phase = value
        elif key == "completed_stories":
            self.completed_stories = value
        elif key == "pending_stories":
            self.pending_stories = value
        elif key == "timestamp":
            self.timestamp = value
        elif key == "metadata":
            self.metadata = value
        elif key == "status":
            self.status = value
        else:
            raise KeyError(f"Invalid checkpoint field: {key}")

    def __contains__(self, key):
        """Support 'in' operator for checkpoint fields."""
        return key in self.to_dict()


def init_db(db_path: str):
    """
    Initialize the checkpoints database with proper schema.

    Creates the checkpoints table with indices for efficient querying.

    Args:
        db_path: Path to the SQLite database file.

    Raises:
        sqlite3.Error: If database initialization fails.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=OFF")

        cursor = conn.cursor()

        # Check if existing checkpoints table has wrong schema (LangGraph's thread_id schema)
        try:
            cursor.execute("SELECT task_id FROM checkpoints LIMIT 0")
        except sqlite3.OperationalError:
            # Table exists but has wrong schema — drop and recreate
            try:
                cursor.execute("SELECT thread_id FROM checkpoints LIMIT 0")
                logger.warning(f"Dropping checkpoints table with wrong schema (LangGraph) at {db_path}")
                cursor.execute("DROP TABLE checkpoints")
            except sqlite3.OperationalError:
                pass  # Table doesn't exist at all, which is fine

        # Create checkpoints table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                task_id TEXT PRIMARY KEY,
                current_phase TEXT NOT NULL,
                completed_stories TEXT NOT NULL,
                pending_stories TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'in_progress'
            )
        """)

        # Migration: add status column if missing (existing databases)
        try:
            cursor.execute("SELECT status FROM checkpoints LIMIT 0")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE checkpoints ADD COLUMN status TEXT NOT NULL DEFAULT 'in_progress'")

        # Create index on current_phase for efficient filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_phase
            ON checkpoints(current_phase)
        """)

        # Create index on timestamp for chronological queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_timestamp
            ON checkpoints(timestamp)
        """)

        conn.commit()
        conn.close()
        logger.info(f"Initialized checkpoints database at {db_path}")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize checkpoints database: {e}")
        raise


def write_checkpoint(db_path: str, checkpoint: Checkpoint):
    """
    Save a checkpoint to the database.

    Args:
        db_path: Path to the SQLite database file.
        checkpoint: Checkpoint object to save.

    Raises:
        sqlite3.Error: If checkpoint cannot be written.
        ValueError: If checkpoint data is invalid.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Validate checkpoint
        if not checkpoint.task_id:
            raise ValueError("Cannot save checkpoint with empty task_id")

        if not checkpoint.current_phase:
            raise ValueError("Cannot save checkpoint with empty current_phase")

        # Serialize data for storage
        completed_stories_json = json.dumps(checkpoint.completed_stories)
        pending_stories_json = json.dumps(checkpoint.pending_stories)
        metadata_json = json.dumps(checkpoint.metadata)

        # Upsert checkpoint (insert or replace)
        cursor.execute("""
            INSERT INTO checkpoints (
                task_id, current_phase, completed_stories,
                pending_stories, timestamp, metadata, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                current_phase = excluded.current_phase,
                completed_stories = excluded.completed_stories,
                pending_stories = excluded.pending_stories,
                timestamp = excluded.timestamp,
                metadata = excluded.metadata,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
        """, (
            checkpoint.task_id,
            checkpoint.current_phase,
            completed_stories_json,
            pending_stories_json,
            checkpoint.timestamp,
            metadata_json,
            checkpoint.status,
        ))

        conn.commit()
        logger.debug(f"Saved checkpoint for task {checkpoint.task_id}")
    except sqlite3.Error as e:
        logger.error(f"Failed to write checkpoint: {e}")
        raise
    finally:
        if conn:
            conn.close()


def read_checkpoint(db_path: str, task_id: str) -> Optional[Checkpoint]:
    """
    Retrieve a checkpoint from the database.

    Args:
        db_path: Path to the SQLite database file.
        task_id: The task identifier to retrieve.

    Returns:
        Checkpoint object if found, None otherwise.

    Raises:
        sqlite3.Error: If checkpoint cannot be read.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT task_id, current_phase, completed_stories,
                   pending_stories, timestamp, metadata, status
            FROM checkpoints
            WHERE task_id = ?
        """, (task_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.debug(f"No checkpoint found for task {task_id}")
            return None

        # Parse JSON fields
        task_id, current_phase, completed_stories_json, pending_stories_json, timestamp, metadata_json, status = row
        completed_stories = json.loads(completed_stories_json) if completed_stories_json else []
        pending_stories = json.loads(pending_stories_json) if pending_stories_json else []
        metadata = json.loads(metadata_json) if metadata_json else {}

        return Checkpoint(
            task_id=task_id,
            current_phase=current_phase,
            completed_stories=completed_stories,
            pending_stories=pending_stories,
            timestamp=timestamp,
            metadata=metadata,
            status=status or STATUS_IN_PROGRESS,
        )
    except sqlite3.Error as e:
        logger.error(f"Failed to read checkpoint: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode checkpoint data: {e}")
        raise


def list_checkpoints(db_path: str) -> List[Checkpoint]:
    """
    Retrieve all checkpoints from the database.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of all checkpoint objects.

    Raises:
        sqlite3.Error: If checkpoints cannot be read.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT task_id, current_phase, completed_stories,
                   pending_stories, timestamp, metadata, status
            FROM checkpoints
            ORDER BY timestamp DESC
        """)

        checkpoints = []
        for row in cursor.fetchall():
            task_id, current_phase, completed_stories_json, pending_stories_json, timestamp, metadata_json, status = row
            completed_stories = json.loads(completed_stories_json) if completed_stories_json else []
            pending_stories = json.loads(pending_stories_json) if pending_stories_json else []
            metadata = json.loads(metadata_json) if metadata_json else {}

            checkpoints.append(Checkpoint(
                task_id=task_id,
                current_phase=current_phase,
                completed_stories=completed_stories,
                pending_stories=pending_stories,
                timestamp=timestamp,
                metadata=metadata,
                status=status or STATUS_IN_PROGRESS,
            ))

        conn.close()
        return checkpoints
    except sqlite3.Error as e:
        logger.error(f"Failed to list checkpoints: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode checkpoint data: {e}")
        raise


def delete_checkpoint(db_path: str, task_id: str) -> bool:
    """
    Delete a checkpoint from the database.

    Args:
        db_path: Path to the SQLite database file.
        task_id: The task identifier to delete.

    Returns:
        True if checkpoint was deleted, False if not found.

    Raises:
        sqlite3.Error: If deletion fails.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM checkpoints WHERE task_id = ?", (task_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            logger.debug(f"Deleted checkpoint for task {task_id}")
        return deleted
    except sqlite3.Error as e:
        logger.error(f"Failed to delete checkpoint: {e}")
        raise


def update_phase(db_path: str, task_id: str, new_phase: str):
    """
    Update only the current phase of a checkpoint.

    This is a convenience function for updating the phase without
    modifying other checkpoint fields.

    Args:
        db_path: Path to the SQLite database file.
        task_id: The task identifier.
        new_phase: The new phase value.

    Raises:
        ValueError: If task_id or new_phase is invalid.
        sqlite3.Error: If update fails.
    """
    if not task_id or not new_phase:
        raise ValueError("task_id and new_phase must be non-empty")

    try:
        existing = read_checkpoint(db_path, task_id)
        if not existing:
            raise ValueError(f"No checkpoint found for task {task_id}")

        existing.current_phase = new_phase
        write_checkpoint(db_path, existing)
    except sqlite3.Error as e:
        logger.error(f"Failed to update phase: {e}")
        raise


def resume_incomplete_workflows(db_path: str) -> int:
    """
    Resume incomplete workflows from checkpoints.

    Reads all checkpoints with phases other than "LEARN" (completed phase)
    and logs them for monitoring. Does not automatically resume tasks.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Number of incomplete workflows found and logged.

    Raises:
        sqlite3.Error: If checkpoints cannot be read.
    """
    try:
        checkpoints = list_checkpoints(db_path)
        incomplete_count = 0

        for checkpoint in checkpoints:
            # Exclude checkpoints in the LEARN phase (completed state)
            if checkpoint.current_phase != "LEARN":
                incomplete_count += 1
                logger.info(
                    f"Found incomplete workflow: {checkpoint.task_id} "
                    f"(phase={checkpoint.current_phase}, "
                    f"completed={len(checkpoint.completed_stories)}, "
                    f"pending={len(checkpoint.pending_stories)})"
                )

        if incomplete_count > 0:
            logger.info(f"Resume check complete: {incomplete_count} incomplete workflow(s) found")
        else:
            logger.info("Resume check complete: No incomplete workflows found")

        return incomplete_count
    except sqlite3.Error as e:
        logger.error(f"Failed to read checkpoints for resume: {e}")
        raise
