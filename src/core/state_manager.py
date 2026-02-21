"""
SQLite State Manager

A simple key-value state manager using SQLite for persistence.
Stores values as JSON strings.
"""

import sqlite3
import json
import os


class SQLiteStateManager:
    """Manages application state using SQLite database storage."""

    def __init__(self, db_path: str):
        """
        Initialize the state manager with a database path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self):
        """Create the state table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def set(self, key: str, value) -> None:
        """
        Store a key-value pair in the database.

        Args:
            key: The key to store
            value: The value to store (will be serialized to JSON)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        json_value = json.dumps(value)

        cursor.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
            (key, json_value)
        )

        conn.commit()
        conn.close()

    def get(self, key: str):
        """
        Retrieve a value from the database by key.

        Args:
            key: The key to retrieve

        Returns:
            The parsed JSON value, or None if the key doesn't exist
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM state WHERE key = ?", (key,))
        result = cursor.fetchone()

        conn.close()

        if result is None:
            return None

        return json.loads(result[0])

    def delete(self, key: str) -> None:
        """
        Delete a key from the database.

        Args:
            key: The key to delete
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM state WHERE key = ?", (key,))

        conn.commit()
        conn.close()
