"""
Daemon module for managing long-running background processes.
"""

import time
import json
import threading


class Daemon:
    """A class that manages a long-running background process."""

    def __init__(self, config_path=None):
        """
        Initialize the Daemon with optional configuration file path.

        Args:
            config_path: Optional path to a JSON configuration file.
        """
        self._running = False
        self._stop_event = threading.Event()
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self):
        """
        Load configuration from file or use defaults.

        Returns:
            dict: Configuration dictionary with defaults or loaded values.
        """
        default_config = {
            "interval": 1
        }

        if self.config_path is None:
            return default_config

        try:
            from pathlib import Path
            config_file = Path(self.config_path)

            if not config_file.exists():
                return default_config

            with open(config_file, 'r') as f:
                loaded_config = json.load(f)

            # Merge with defaults to ensure all required keys exist
            default_config.update(loaded_config)
            return default_config

        except (json.JSONDecodeError, IOError, OSError):
            # Handle invalid JSON or file read errors gracefully
            return default_config

    def run(self):
        """Start the infinite loop that keeps the daemon alive."""
        self._running = True
        self._stop_event.clear()

        interval = self.config.get("interval", 1)

        while self._running and not self._stop_event.is_set():
            time.sleep(interval)

    def stop(self):
        """Gracefully stop the daemon."""
        self._running = False
        self._stop_event.set()
