"""Tests for centralized path configuration."""

import os
from pathlib import Path
from unittest.mock import patch


class TestPathsDefaults:
    """Test that paths module provides sensible defaults."""

    def test_project_dir_is_valid(self):
        from src.core.paths import SAT_PROJECT_DIR

        assert SAT_PROJECT_DIR.exists()
        assert (SAT_PROJECT_DIR / "src").exists()

    def test_memory_dir_under_project(self):
        from src.core.paths import MEMORY_DIR, SAT_PROJECT_DIR

        assert MEMORY_DIR == SAT_PROJECT_DIR / ".memory"

    def test_database_paths_under_memory(self):
        from src.core.paths import CHECKPOINT_DB, LLM_COST_DB, MEMORY_DIR, SAT_DB, VECTORS_DB

        assert SAT_DB.parent == MEMORY_DIR
        assert CHECKPOINT_DB.parent == MEMORY_DIR
        assert VECTORS_DB.parent == MEMORY_DIR
        assert LLM_COST_DB.parent == MEMORY_DIR

    def test_config_json_under_project(self):
        from src.core.paths import CONFIG_JSON, SAT_PROJECT_DIR

        assert CONFIG_JSON == SAT_PROJECT_DIR / "config.json"

    def test_monitor_watch_dirs_are_paths(self):
        from src.core.paths import MONITOR_WATCH_DIRS, SAT_TASKS_DIR

        assert len(MONITOR_WATCH_DIRS) > 0
        for d in MONITOR_WATCH_DIRS:
            assert isinstance(d, Path)
            assert str(d).startswith(str(SAT_TASKS_DIR))

    def test_all_paths_are_path_objects(self):
        from src.core import paths

        for name in dir(paths):
            obj = getattr(paths, name)
            if isinstance(obj, Path):
                # Verify it's absolute
                assert obj.is_absolute(), f"{name} is not absolute: {obj}"


class TestPathsEnvOverride:
    """Test that environment variables override defaults."""

    def test_project_dir_env_override(self):
        with patch.dict(os.environ, {"SAT_PROJECT_DIR": "/tmp/test-sat"}):
            # Must reimport to pick up env change
            import importlib

            from src.core import paths

            importlib.reload(paths)
            assert Path("/tmp/test-sat") == paths.SAT_PROJECT_DIR
            # Restore
            importlib.reload(paths)

    def test_tasks_dir_env_override(self):
        with patch.dict(os.environ, {"SAT_TASKS_DIR": "/tmp/test-tasks"}):
            import importlib

            from src.core import paths

            importlib.reload(paths)
            assert Path("/tmp/test-tasks") == paths.SAT_TASKS_DIR
            # Restore
            importlib.reload(paths)

    def test_gdrive_root_env_override(self):
        with patch.dict(os.environ, {"SAT_GDRIVE_ROOT": "/tmp/gdrive"}):
            import importlib

            from src.core import paths

            importlib.reload(paths)
            assert Path("/tmp/gdrive") == paths.SAT_GDRIVE_ROOT
            # Restore
            importlib.reload(paths)
