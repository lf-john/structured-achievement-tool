"""Tests for proactive agency in health_check.py."""

import json
import os
from unittest.mock import patch

from src.health_check import (
    _create_maintenance_story,
    _hours_since,
    _load_proactive_state,
    _save_proactive_state,
    run_proactive_checks,
)


class TestHoursSince:
    def test_none_returns_infinity(self):
        assert _hours_since(None) == float("inf")

    def test_empty_returns_infinity(self):
        assert _hours_since("") == float("inf")

    def test_recent_timestamp(self):
        import datetime
        now = datetime.datetime.now().isoformat()
        assert _hours_since(now) < 1

    def test_old_timestamp(self):
        result = _hours_since("2020-01-01T00:00:00")
        assert result > 1000


class TestCreateMaintenanceStory:
    def test_creates_file(self, tmp_path):
        filepath = _create_maintenance_story(
            "Test Story",
            "Test description",
            output_dir=str(tmp_path),
        )
        assert os.path.exists(filepath)
        content = open(filepath).read()
        assert "Test Story" in content
        assert "Test description" in content
        assert "<Pending>" in content

    def test_includes_metadata(self, tmp_path):
        filepath = _create_maintenance_story(
            "Dep Check",
            "Check deps",
            story_type="maintenance",
            output_dir=str(tmp_path),
        )
        content = open(filepath).read()
        assert "maintenance" in content
        assert "Proactive Agency" in content


class TestProactiveState:
    def test_save_and_load(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        with patch("src.health_check.PROACTIVE_STATE_FILE", state_file):
            _save_proactive_state({"last_check": "2026-02-26T10:00:00"})
            loaded = _load_proactive_state()
            assert loaded["last_check"] == "2026-02-26T10:00:00"

    def test_load_missing_file(self, tmp_path):
        with patch("src.health_check.PROACTIVE_STATE_FILE", str(tmp_path / "nonexistent.json")):
            result = _load_proactive_state()
            assert result == {}


class TestRunProactiveChecks:
    def test_disabled_returns_empty(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "proactive_agency": {"enabled": False}
        }))
        with patch("src.health_check.PROJECT_PATH", str(tmp_path)):
            result = run_proactive_checks()
            assert result == []

    def test_creates_config_story_on_missing_config(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "proactive_agency": {
                "enabled": True,
                "config_validation_interval_hours": 0,
                "story_output_dir": str(tmp_path / "output"),
            }
        }))
        state_file = tmp_path / ".memory" / "proactive_state.json"
        os.makedirs(state_file.parent, exist_ok=True)

        # Remove config to trigger the check
        with patch("src.health_check.PROJECT_PATH", str(tmp_path)), \
             patch("src.health_check.PROACTIVE_STATE_FILE", str(state_file)), \
             patch("src.health_check.notify"):
            # Config exists but routing_rules_enabled is not set
            result = run_proactive_checks()
            # Should create at least one story since routing_rules_enabled is missing
            assert len(result) >= 1
