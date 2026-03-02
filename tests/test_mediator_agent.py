"""Tests for src.agents.mediator_agent — Smart trigger + intervention tracking."""

import json
import os
import tempfile
import pytest

from src.agents.mediator_agent import (
    categorize_files,
    should_trigger,
    save_intervention,
    get_intervention_stats,
    MediatorAgent,
)


class TestCategorizeFiles:
    def test_test_files(self):
        files = ["tests/test_foo.py", "src/main.py", "test_bar.spec.js"]
        test_files, code_files = categorize_files(files)
        assert "tests/test_foo.py" in test_files
        assert "test_bar.spec.js" in test_files
        assert "src/main.py" in code_files

    def test_empty_list(self):
        test_files, code_files = categorize_files([])
        assert test_files == []
        assert code_files == []

    def test_all_test_files(self):
        files = ["tests/test_a.py", "test/test_b.py", "foo.test.js"]
        test_files, code_files = categorize_files(files)
        assert len(test_files) == 3
        assert len(code_files) == 0


class TestShouldTrigger:
    def test_non_trigger_phase(self):
        result = should_trigger("DESIGN", ["file.py"])
        assert not result["should_trigger"]

    def test_no_modified_files(self):
        result = should_trigger("CODE", [])
        assert not result["should_trigger"]

    def test_tdd_red_code_files_trigger(self):
        # TDD_RED is in TRIGGER_PHASES — code files modified triggers mediator
        result = should_trigger("TDD_RED", ["src/main.py"])
        assert result["should_trigger"]
        assert result["violation"] == "code_in_test_phase"

    def test_tdd_red_test_files_only_no_trigger(self):
        # TDD_RED with only test files is expected behavior — no trigger
        result = should_trigger("TDD_RED", ["tests/test_main.py"])
        assert not result["should_trigger"]

    def test_code_test_file_triggers(self):
        result = should_trigger("CODE", ["tests/test_main.py"])
        assert result["should_trigger"]
        assert result["violation"] == "test_in_code_phase"

    def test_code_only_code_files_ok(self):
        result = should_trigger("CODE", ["src/main.py"])
        assert not result["should_trigger"]

    def test_verify_always_triggers(self):
        result = should_trigger("VERIFY", ["any_file.py"])
        assert result["should_trigger"]
        assert result["violation"] == "verify_changes"

    def test_fix_phase_triggers_on_test_files(self):
        result = should_trigger("FIX", ["tests/test_foo.py"])
        assert result["should_trigger"]


class TestInterventionTracking:
    def test_save_and_read(self, tmp_path):
        save_intervention(
            str(tmp_path), "US-001", "CODE",
            "test_in_code_phase", "REVERT", ["tests/test_x.py"]
        )
        save_intervention(
            str(tmp_path), "US-002", "VERIFY",
            "verify_changes", "ACCEPT", ["main.py"]
        )

        stats = get_intervention_stats(str(tmp_path))
        assert stats["total"] == 2
        assert stats["by_phase"]["CODE"] == 1
        assert stats["by_phase"]["VERIFY"] == 1
        assert stats["by_decision"]["REVERT"] == 1
        assert stats["by_decision"]["ACCEPT"] == 1

    def test_no_file_returns_empty_stats(self, tmp_path):
        stats = get_intervention_stats(str(tmp_path))
        assert stats["total"] == 0
        assert stats["by_phase"] == {}

    def test_jsonl_format(self, tmp_path):
        save_intervention(str(tmp_path), "US-001", "CODE", "v", "ACCEPT", [])
        tracker_file = os.path.join(str(tmp_path), "mediator-interventions.jsonl")
        with open(tracker_file) as f:
            entry = json.loads(f.readline())
        assert entry["storyId"] == "US-001"
        assert "timestamp" in entry


class TestMediatorAgent:
    def test_agent_properties(self):
        agent = MediatorAgent()
        assert agent.agent_name == "mediator"
