"""
SQLite State Manager

Provides key-value storage using SQLite database with JSON serialization.
"""

import sqlite3
import json
import os


class SQLiteStateManager:
    """Manages SQLite database storage for key-value pairs."""

    def __init__(self, db_path: str):
        """
        Initialize the state manager with a database path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Create the state table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.commit()
        conn.close()

    def set(self, key: str, value) -> None:
        """
        Store a key-value pair as JSON in the database.

        Args:
            key: The key to store
            value: The value to store (must be JSON-serializable)
        """
        json_value = json.dumps(value)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
            (key, json_value)
        )

        conn.commit()
        conn.close()

    def get(self, key: str):
        """
        Retrieve and parse JSON data for a given key.

        Args:
            key: The key to retrieve

        Returns:
            The parsed JSON data, or None if the key doesn't exist
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
        Remove a key from the database.

        Args:
            key: The key to delete
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM state WHERE key = ?", (key,))

        conn.commit()
        conn.close()
