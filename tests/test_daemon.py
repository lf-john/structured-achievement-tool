"""
IMPLEMENTATION PLAN for US-001:

Components:
  - Daemon: A class that manages a long-running background process
    * __init__(config_path): Initialize with optional configuration file path
    * _load_config(): Load configuration from file (or use defaults)
    * run(): Start the infinite loop that keeps the daemon alive
    * stop(): Gracefully stop the daemon

Test Cases:
  1. AC 1 (Daemon class exists) -> test_class_initialization
  2. AC 2 (Daemon can be instantiated) -> test_can_be_instantiated
  3. AC 3 (Daemon reads configuration) -> test_loads_configuration
  4. AC 4 (Daemon runs infinite loop) -> test_run_starts_infinite_loop

Edge Cases:
  - Missing configuration file (should use defaults)
  - Invalid configuration format (should handle gracefully)
  - Empty configuration file (should use defaults)
  - Configuration with various data types (strings, numbers, booleans)
  - Stop signal during execution
"""

import pytest
import os
import tempfile
import time
import threading
from pathlib import Path

# Import the class that doesn't exist yet - this will cause import error
from src.daemon import Daemon


class TestDaemonClassExists:
    """Test acceptance criterion 1: Daemon class exists."""

    def test_daemon_class_is_defined(self):
        """Test that Daemon class can be imported."""
        # This test verifies the class exists in the module
        assert Daemon is not None
        assert hasattr(Daemon, '__init__')


class TestDaemonInstantiation:
    """Test acceptance criterion 2: Daemon can be instantiated."""

    def test_can_be_instantiated_without_config(self):
        """Test that Daemon can be instantiated without configuration."""
        daemon = Daemon()
        assert daemon is not None
        assert isinstance(daemon, Daemon)

    def test_can_be_instantiated_with_config_path(self):
        """Test that Daemon can be instantiated with a config path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            # Create a simple config file
            with open(config_path, 'w') as f:
                f.write('{"interval": 5}')

            daemon = Daemon(config_path=config_path)
            assert daemon is not None
            assert isinstance(daemon, Daemon)

    def test_instantiation_creates_daemon_object(self):
        """Test that instantiation creates a proper Daemon object."""
        daemon = Daemon()
        assert hasattr(daemon, 'run')
        assert callable(daemon.run)


class TestDaemonConfiguration:
    """Test acceptance criterion 3: Daemon reads configuration."""

    def test_loads_default_config_when_no_file(self):
        """Test that Daemon uses defaults when no config file provided."""
        daemon = Daemon()
        assert hasattr(daemon, 'config')
        assert daemon.config is not None
        # Should have default interval
        assert 'interval' in daemon.config or hasattr(daemon, 'interval')

    def test_loads_configuration_from_file(self):
        """Test that Daemon loads configuration from provided file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            test_config = {
                "interval": 10,
                "log_level": "debug",
                "max_retries": 3
            }
            import json
            with open(config_path, 'w') as f:
                json.dump(test_config, f)

            daemon = Daemon(config_path=config_path)
            assert daemon.config == test_config

    def test_handles_missing_config_file_gracefully(self):
        """Test that Daemon handles missing config file gracefully."""
        # Should not raise exception, should use defaults
        daemon = Daemon(config_path="/nonexistent/path/config.json")
        assert daemon is not None
        assert daemon.config is not None

    def test_handles_empty_config_file(self):
        """Test that Daemon handles empty config file with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            # Create empty file
            with open(config_path, 'w') as f:
                f.write("{}")

            daemon = Daemon(config_path=config_path)
            assert daemon is not None
            # Should still have some default configuration

    def test_handles_invalid_json_config(self):
        """Test that Daemon handles invalid JSON in config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            # Create invalid JSON file
            with open(config_path, 'w') as f:
                f.write("{ invalid json }")

            # Should not raise exception, should use defaults
            daemon = Daemon(config_path=config_path)
            assert daemon is not None
            assert daemon.config is not None

    def test_config_stores_various_types(self):
        """Test that configuration can handle various data types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            test_config = {
                "interval": 2,  # number
                "enabled": True,  # boolean
                "name": "test-daemon",  # string
                "tags": ["tag1", "tag2"],  # list
                "metadata": {"key": "value"}  # nested dict
            }
            import json
            with open(config_path, 'w') as f:
                json.dump(test_config, f)

            daemon = Daemon(config_path=config_path)
            assert daemon.config["interval"] == 2
            assert daemon.config["enabled"] is True
            assert daemon.config["name"] == "test-daemon"
            assert daemon.config["tags"] == ["tag1", "tag2"]
            assert daemon.config["metadata"]["key"] == "value"


class TestDaemonRunLoop:
    """Test acceptance criterion 4: Daemon runs an infinite loop."""

    def test_run_method_exists(self):
        """Test that run() method exists."""
        daemon = Daemon()
        assert hasattr(daemon, 'run')
        assert callable(daemon.run)

    def test_run_starts_infinite_loop(self):
        """Test that run() method starts the infinite loop."""
        daemon = Daemon()

        # Run daemon in a separate thread
        stop_event = threading.Event()
        daemon_thread = threading.Thread(
            target=lambda: (
                daemon.run() if not stop_event.is_set() else None
            )
        )
        daemon_thread.start()

        # Let it run briefly
        time.sleep(0.5)

        # The thread should still be alive (infinite loop)
        assert daemon_thread.is_alive()

        # Stop the daemon
        stop_event.set()
        if hasattr(daemon, 'stop'):
            daemon.stop()

        # Wait for thread to finish (with timeout)
        daemon_thread.join(timeout=2)

    def test_run_respects_config_interval(self):
        """Test that run() respects the configured interval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            import json
            with open(config_path, 'w') as f:
                json.dump({"interval": 0.1}, f)  # Very short interval for testing

            daemon = Daemon(config_path=config_path)
            assert daemon.config["interval"] == 0.1

    def test_stop_method_exists(self):
        """Test that stop() method exists for graceful shutdown."""
        daemon = Daemon()
        assert hasattr(daemon, 'stop')
        assert callable(daemon.stop)

    def test_can_stop_running_daemon(self):
        """Test that a running daemon can be stopped gracefully."""
        daemon = Daemon()

        # Run in thread
        daemon_thread = threading.Thread(target=daemon.run)
        daemon_thread.start()

        # Let it run
        time.sleep(0.2)

        # Stop it
        daemon.stop()
        daemon_thread.join(timeout=2)

        # Daemon should have stopped
        assert not daemon_thread.is_alive()


class TestDaemonIntegration:
    """Integration tests for Daemon behavior."""

    def test_full_lifecycle_start_stop(self):
        """Test complete daemon lifecycle: instantiate -> run -> stop."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            import json
            with open(config_path, 'w') as f:
                json.dump({"interval": 0.1}, f)

            # Instantiate
            daemon = Daemon(config_path=config_path)
            assert daemon is not None

            # Run in thread
            daemon_thread = threading.Thread(target=daemon.run)
            daemon_thread.start()
            assert daemon_thread.is_alive()

            # Stop
            daemon.stop()
            daemon_thread.join(timeout=2)
            assert not daemon_thread.is_alive()

    def test_multiple_daemon_instances(self):
        """Test that multiple daemon instances can coexist."""
        daemon1 = Daemon()
        daemon2 = Daemon()

        assert daemon1 is not daemon2
        assert isinstance(daemon1, Daemon)
        assert isinstance(daemon2, Daemon)

    def test_config_persistence_across_reinstantiation(self):
        """Test that config is correctly loaded on each instantiation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            test_config = {"interval": 5, "name": "test"}
            import json
            with open(config_path, 'w') as f:
                json.dump(test_config, f)

            # First instance
            daemon1 = Daemon(config_path=config_path)
            assert daemon1.config["interval"] == 5

            # Second instance with same config
            daemon2 = Daemon(config_path=config_path)
            assert daemon2.config["interval"] == 5
            assert daemon2.config["name"] == "test"


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
