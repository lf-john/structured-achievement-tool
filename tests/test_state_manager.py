"""
IMPLEMENTATION PLAN for US-001:

Components:
  - SQLiteStateManager: A class that manages SQLite database storage for key-value pairs
    * __init__(db_path): Initialize database connection and create state table
    * set(key, value): Store key-value pair as JSON in database
    * get(key): Retrieve and parse JSON data, return None if not found
    * delete(key): Remove a key from database

Test Cases:
  1. AC 1 (SQLiteStateManager class exists and takes a db_path) -> test_class_initialization
  2. AC 2 (set method stores dict as JSON data) -> test_set_and_get_dict
  3. AC 3 (get method retrieves and parses JSON, returning None if not found) -> test_get_nonexistent_key_returns_none
  4. AC 4 (delete method removes the key) -> test_delete_key

Edge Cases:
  - Overwriting existing keys
  - Complex nested data structures
  - Various JSON-serializable types (strings, numbers, booleans, lists, dicts)
  - Deleting non-existent key (should not raise error)
  - Empty database
"""

import pytest
import os
import tempfile
import json
from pathlib import Path

# Import the class that doesn't exist yet - this will cause import error
from src.core.state_manager import SQLiteStateManager


class TestSQLiteStateManagerInitialization:
    """Test acceptance criterion 1: SQLiteStateManager class exists and takes a db_path."""

    def test_class_initialization_with_db_path(self):
        """Test that SQLiteStateManager can be instantiated with a db_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            assert manager is not None
            # Verify database file was created
            assert os.path.exists(db_path)

    def test_initialization_creates_state_table(self):
        """Test that initialization creates the necessary state table."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            # Query the database to verify table exists
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if the state table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='state'"
            )
            result = cursor.fetchone()
            assert result is not None, "State table should be created"

            # Check table schema
            cursor.execute("PRAGMA table_info(state)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            assert "key" in columns, "Table should have 'key' column"
            assert "value" in columns, "Table should have 'value' column"
            assert columns["key"] == "TEXT", "Key column should be TEXT type"
            assert columns["value"] == "TEXT", "Value column should be TEXT type"

            conn.close()


class TestSetMethod:
    """Test acceptance criterion 2: set(key, value) method stores dict as JSON data."""

    def test_set_stores_simple_dict(self):
        """Test storing a simple dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            test_data = {"name": "Alice", "age": 30}
            manager.set("user:1", test_data)

            # Verify data was stored in database
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM state WHERE key = ?", ("user:1",))
            result = cursor.fetchone()
            assert result is not None

            # Verify it's valid JSON
            stored_data = json.loads(result[0])
            assert stored_data == test_data
            conn.close()

    def test_set_stores_nested_dict(self):
        """Test storing a nested dictionary structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            test_data = {
                "user": {
                    "name": "Bob",
                    "address": {
                        "street": "123 Main St",
                        "city": "Springfield"
                    }
                }
            }
            manager.set("user:2", test_data)

            # Retrieve and verify
            retrieved = manager.get("user:2")
            assert retrieved == test_data

    def test_set_stores_list(self):
        """Test storing a list as JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            test_data = [1, 2, 3, "four", {"five": 5}]
            manager.set("my_list", test_data)

            retrieved = manager.get("my_list")
            assert retrieved == test_data

    def test_set_stores_various_types(self):
        """Test storing various JSON-serializable types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            # Test string
            manager.set("string_key", "hello world")
            assert manager.get("string_key") == "hello world"

            # Test number
            manager.set("number_key", 42)
            assert manager.get("number_key") == 42

            # Test boolean
            manager.set("bool_key", True)
            assert manager.get("bool_key") is True

            # Test null
            manager.set("null_key", None)
            assert manager.get("null_key") is None

    def test_set_overwrites_existing_key(self):
        """Test that set overwrites existing key with new value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            # Set initial value
            manager.set("config", {"theme": "dark"})
            assert manager.get("config") == {"theme": "dark"}

            # Overwrite with new value
            manager.set("config", {"theme": "light", "fontSize": 14})
            assert manager.get("config") == {"theme": "light", "fontSize": 14}

            # Verify only one record exists
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM state WHERE key = ?", ("config",))
            count = cursor.fetchone()[0]
            assert count == 1, "Should only have one record after overwrite"
            conn.close()


class TestGetMethod:
    """Test acceptance criterion 3: get(key) method retrieves and parses JSON data, returning None if not found."""

    def test_get_retrieves_stored_data(self):
        """Test that get retrieves and parses JSON data correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            test_data = {"username": "testuser", "active": True}
            manager.set("session:abc", test_data)

            retrieved = manager.get("session:abc")
            assert retrieved == test_data
            assert isinstance(retrieved, dict)
            assert retrieved["username"] == "testuser"
            assert retrieved["active"] is True

    def test_get_returns_none_for_nonexistent_key(self):
        """Test that get returns None when key doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            result = manager.get("nonexistent:key")
            assert result is None

    def test_get_returns_none_in_empty_database(self):
        """Test that get returns None when database is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            result = manager.get("any_key")
            assert result is None

    def test_get_handles_multiple_keys(self):
        """Test that get correctly retrieves different keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            manager.set("key1", {"value": 1})
            manager.set("key2", {"value": 2})
            manager.set("key3", {"value": 3})

            assert manager.get("key1") == {"value": 1}
            assert manager.get("key2") == {"value": 2}
            assert manager.get("key3") == {"value": 3}
            assert manager.get("key4") is None


class TestDeleteMethod:
    """Test acceptance criterion 4: delete(key) method removes the key."""

    def test_delete_removes_existing_key(self):
        """Test that delete removes a key from storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            # Store a value
            manager.set("temp_key", {"data": "temporary"})
            assert manager.get("temp_key") is not None

            # Delete it
            manager.delete("temp_key")

            # Verify it's gone
            assert manager.get("temp_key") is None

    def test_delete_nonexistent_key_does_not_raise(self):
        """Test that deleting a non-existent key doesn't raise an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            # Should not raise an exception
            manager.delete("nonexistent_key")

            # Verify state is unchanged
            assert manager.get("nonexistent_key") is None

    def test_delete_one_key_preserves_others(self):
        """Test that deleting one key doesn't affect other keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            manager.set("key1", {"value": 1})
            manager.set("key2", {"value": 2})
            manager.set("key3", {"value": 3})

            # Delete only key2
            manager.delete("key2")

            # Verify key1 and key3 still exist
            assert manager.get("key1") == {"value": 1}
            assert manager.get("key2") is None
            assert manager.get("key3") == {"value": 3}

    def test_delete_all_keys(self):
        """Test deleting all keys results in empty database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            manager.set("key1", {"value": 1})
            manager.set("key2", {"value": 2})

            # Delete all
            manager.delete("key1")
            manager.delete("key2")

            # Verify all are gone
            assert manager.get("key1") is None
            assert manager.get("key2") is None

            # Verify database is empty
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM state")
            count = cursor.fetchone()[0]
            assert count == 0, "Database should be empty after deleting all keys"
            conn.close()


class TestIntegrationScenarios:
    """Integration tests combining multiple operations."""

    def test_full_crud_cycle(self):
        """Test a complete create-read-update-delete cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            # Create
            manager.set("user:100", {"name": "Charlie", "status": "active"})

            # Read
            user = manager.get("user:100")
            assert user["name"] == "Charlie"

            # Update
            manager.set("user:100", {"name": "Charlie", "status": "inactive"})
            user = manager.get("user:100")
            assert user["status"] == "inactive"

            # Delete
            manager.delete("user:100")
            assert manager.get("user:100") is None

    def test_persistence_across_instances(self):
        """Test that data persists across different manager instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # First instance writes data
            manager1 = SQLiteStateManager(db_path)
            manager1.set("persistent_key", {"value": "remains"})

            # Second instance reads data
            manager2 = SQLiteStateManager(db_path)
            retrieved = manager2.get("persistent_key")
            assert retrieved == {"value": "remains"}

    def test_large_data_storage(self):
        """Test storing and retrieving larger data structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = SQLiteStateManager(db_path)

            # Create a large data structure
            large_data = {
                "items": [{"id": i, "data": f"item_{i}"} for i in range(100)],
                "metadata": {
                    "created": "2024-01-01",
                    "tags": ["test", "large", "data"]
                }
            }

            manager.set("large_data", large_data)
            retrieved = manager.get("large_data")

            assert len(retrieved["items"]) == 100
            assert retrieved["items"][50]["id"] == 50
            assert retrieved["metadata"]["tags"] == ["test", "large", "data"]


# Track test failures for exit code
fail_count = 0


def pytest_configure(config):
    """Configure pytest to track failures."""
    global fail_count


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Called at end of test session to determine exit code."""
    global fail_count
    fail_count = 1 if exitstatus != 0 else 0


if __name__ == "__main__":
    # Run pytest programmatically and exit with appropriate code
    import sys
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)
