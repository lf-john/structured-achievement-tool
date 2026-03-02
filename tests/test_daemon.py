"""Tests for src/daemon.py utility functions.

Tests the key file-based state machine functions: has_tag, detect_signal,
mark_file_status, is_task_ready, get_latest_md_file, and PID lock management.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, mock_open, MagicMock

from src.daemon import (
    has_tag,
    detect_signal,
    mark_file_status,
    is_task_ready,
    get_latest_md_file,
    _acquire_pid_lock,
    _release_pid_lock,
    parse_task_priority,
    parse_task_project,
    parse_task_depends_on,
    _check_prerequisites_met,
    _detect_circular_deps,
    SIGNAL_TAGS,
    PRD_SIGNALS,
)


# ---------------------------------------------------------------------------
# has_tag
# ---------------------------------------------------------------------------

class TestHasTag:
    """Tests for has_tag(file_path, tag)."""

    def test_tag_present_on_own_line(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Title\n\n<Pending>\n\nSome body text.\n")
        assert has_tag(str(f), "<Pending>") is True

    def test_tag_absent(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Title\n\nSome body text.\n")
        assert has_tag(str(f), "<Pending>") is False

    def test_tag_with_leading_whitespace(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Title\n   <Working>\n")
        assert has_tag(str(f), "<Working>") is True

    def test_tag_with_trailing_whitespace(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Title\n<Finished>   \n")
        assert has_tag(str(f), "<Finished>") is True

    def test_tag_embedded_in_line_not_detected(self, tmp_path):
        """Tag must be on its own line, not embedded in other text."""
        f = tmp_path / "task.md"
        f.write_text("The status is <Pending> right now.\n")
        assert has_tag(str(f), "<Pending>") is False

    def test_nonexistent_file_returns_false(self):
        assert has_tag("/nonexistent/path/file.md", "<Pending>") is False

    def test_commented_tag_not_detected(self, tmp_path):
        """# <Pending> should NOT match <Pending>."""
        f = tmp_path / "task.md"
        f.write_text("# Title\n# <Pending>\nBody\n")
        assert has_tag(str(f), "<Pending>") is False

    def test_multiple_tags_detects_correct_one(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("<Working>\nSome text\n<Cancel>\n")
        assert has_tag(str(f), "<Cancel>") is True
        assert has_tag(str(f), "<Working>") is True
        assert has_tag(str(f), "<Finished>") is False

    def test_read_error_returns_false(self):
        with patch("builtins.open", side_effect=PermissionError("denied")):
            with patch("os.path.exists", return_value=True):
                assert has_tag("/some/file.md", "<Pending>") is False


# ---------------------------------------------------------------------------
# is_task_ready
# ---------------------------------------------------------------------------

class TestIsTaskReady:
    """Tests for is_task_ready(file_path) -- alias for has_tag(<Pending>)."""

    def test_ready_when_pending(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\n<Pending>\n")
        assert is_task_ready(str(f)) is True

    def test_not_ready_when_working(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\n<Working>\n")
        assert is_task_ready(str(f)) is False

    def test_not_ready_when_no_tag(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\nJust some notes.\n")
        assert is_task_ready(str(f)) is False

    def test_not_ready_when_commented_pending(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\n# <Pending>\n")
        assert is_task_ready(str(f)) is False


# ---------------------------------------------------------------------------
# detect_signal
# ---------------------------------------------------------------------------

class TestDetectSignal:
    """Tests for detect_signal(file_path)."""

    def test_pending_signal(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\n<Pending>\n")
        assert detect_signal(str(f)) == "pending"

    def test_plan_signal(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\n<Plan>\n")
        assert detect_signal(str(f)) == "plan"

    def test_plan1_signal(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\n<Plan 1>\n")
        assert detect_signal(str(f)) == "plan1"

    def test_prd_signal(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\n<PRD>\n")
        assert detect_signal(str(f)) == "prd"

    def test_phase2_signal(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\n<1>\n")
        assert detect_signal(str(f)) == "phase2"

    def test_phase3_signal_with_requirements(self, tmp_path):
        """<2> with _prd_requirements.md but no architecture -> phase3."""
        f = tmp_path / "task.md"
        f.write_text("# Task\n<2>\n")
        (tmp_path / "_prd_requirements.md").write_text("reqs")
        assert detect_signal(str(f)) == "phase3"

    def test_phase4_signal_with_architecture(self, tmp_path):
        """<2> with _prd_architecture.md -> phase4."""
        f = tmp_path / "task.md"
        f.write_text("# Task\n<2>\n")
        (tmp_path / "_prd_requirements.md").write_text("reqs")
        (tmp_path / "_prd_architecture.md").write_text("arch")
        assert detect_signal(str(f)) == "phase4"

    def test_phase3_fallback_no_progress_files(self, tmp_path):
        """<2> with no progress files falls back to phase3."""
        f = tmp_path / "task.md"
        f.write_text("# Task\n<2>\n")
        assert detect_signal(str(f)) == "phase3"

    def test_no_signal(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Task\nJust a plain file.\n")
        assert detect_signal(str(f)) is None

    def test_priority_pending_over_plan(self, tmp_path):
        """<Pending> is checked first, so it wins if both present."""
        f = tmp_path / "task.md"
        f.write_text("<Pending>\n<Plan>\n")
        assert detect_signal(str(f)) == "pending"

    def test_signal_tags_dict_completeness(self):
        """All signals returned by detect_signal should be in SIGNAL_TAGS."""
        expected_signals = {"pending", "plan", "plan1", "phase2", "phase3", "phase4", "prd"}
        assert set(SIGNAL_TAGS.keys()) == expected_signals

    def test_prd_signals_set(self):
        """PRD_SIGNALS should contain the phase-based signals."""
        assert PRD_SIGNALS == {"plan", "plan1", "phase2", "phase3", "phase4"}


# ---------------------------------------------------------------------------
# mark_file_status
# ---------------------------------------------------------------------------

class TestMarkFileStatus:
    """Tests for mark_file_status(file_path, old_tag, new_tag)."""

    def test_replaces_tag(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Title\n<Pending>\nBody\n")
        result = mark_file_status(str(f), "<Pending>", "<Working>")
        assert result is True
        assert "<Working>" in f.read_text()
        assert "<Pending>" not in f.read_text()

    def test_replaces_last_occurrence(self, tmp_path):
        """rsplit(old_tag, 1) means only the last occurrence is replaced."""
        f = tmp_path / "task.md"
        f.write_text("First <Pending> mention\nSecond <Pending> here\n")
        result = mark_file_status(str(f), "<Pending>", "<Working>")
        assert result is True
        content = f.read_text()
        assert content.count("<Pending>") == 1  # first one kept
        assert content.count("<Working>") == 1  # second one replaced

    def test_returns_false_when_tag_not_found(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Title\n<Finished>\nBody\n")
        result = mark_file_status(str(f), "<Pending>", "<Working>")
        assert result is False
        # File should be unchanged
        assert "<Finished>" in f.read_text()

    def test_preserves_surrounding_content(self, tmp_path):
        f = tmp_path / "task.md"
        original = "# My Task\n\nSome context here.\n\n<Pending>\n\n## Details\nMore text.\n"
        f.write_text(original)
        mark_file_status(str(f), "<Pending>", "<Working>")
        content = f.read_text()
        assert "# My Task" in content
        assert "Some context here." in content
        assert "## Details" in content
        assert "More text." in content

    def test_handles_read_error(self):
        with patch("builtins.open", side_effect=IOError("disk error")):
            result = mark_file_status("/bad/path.md", "<Pending>", "<Working>")
            assert result is False


# ---------------------------------------------------------------------------
# get_latest_md_file
# ---------------------------------------------------------------------------

class TestGetLatestMdFile:
    """Tests for get_latest_md_file(directory)."""

    def test_returns_alphabetically_last(self, tmp_path):
        (tmp_path / "001_first.md").write_text("a")
        (tmp_path / "002_second.md").write_text("b")
        (tmp_path / "003_third.md").write_text("c")
        result = get_latest_md_file(str(tmp_path))
        assert result == str(tmp_path / "003_third.md")

    def test_skips_underscore_prefixed(self, tmp_path):
        (tmp_path / "001_task.md").write_text("a")
        (tmp_path / "_prd_output.md").write_text("b")
        result = get_latest_md_file(str(tmp_path))
        assert result == str(tmp_path / "001_task.md")

    def test_skips_non_md_files(self, tmp_path):
        (tmp_path / "notes.txt").write_text("a")
        (tmp_path / "001_task.md").write_text("b")
        result = get_latest_md_file(str(tmp_path))
        assert result == str(tmp_path / "001_task.md")

    def test_returns_none_for_empty_dir(self, tmp_path):
        result = get_latest_md_file(str(tmp_path))
        assert result is None

    def test_returns_none_for_nonexistent_dir(self):
        result = get_latest_md_file("/nonexistent/directory")
        assert result is None

    def test_returns_none_when_only_underscore_files(self, tmp_path):
        (tmp_path / "_hidden.md").write_text("a")
        result = get_latest_md_file(str(tmp_path))
        assert result is None

    def test_ignores_subdirectories_with_md_names(self, tmp_path):
        """Directories ending in .md should not be returned."""
        subdir = tmp_path / "fake.md"
        subdir.mkdir()
        (tmp_path / "001_real.md").write_text("a")
        result = get_latest_md_file(str(tmp_path))
        assert result == str(tmp_path / "001_real.md")


# ---------------------------------------------------------------------------
# PID lock functions
# ---------------------------------------------------------------------------

class TestPidLock:
    """Tests for _acquire_pid_lock and _release_pid_lock."""

    def test_acquire_writes_pid_file(self, tmp_path):
        pid_file = str(tmp_path / "sat-daemon.pid")
        with patch("src.daemon.PID_FILE", pid_file):
            _acquire_pid_lock()
            assert os.path.exists(pid_file)
            with open(pid_file) as f:
                assert int(f.read().strip()) == os.getpid()

    def test_release_removes_pid_file(self, tmp_path):
        pid_file = str(tmp_path / "sat-daemon.pid")
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
        with patch("src.daemon.PID_FILE", pid_file):
            _release_pid_lock()
            assert not os.path.exists(pid_file)

    def test_release_ignores_other_pid(self, tmp_path):
        """Release should NOT delete the file if PID doesn't match."""
        pid_file = str(tmp_path / "sat-daemon.pid")
        with open(pid_file, "w") as f:
            f.write("99999999")
        with patch("src.daemon.PID_FILE", pid_file):
            _release_pid_lock()
            # File should still exist because PID doesn't match
            assert os.path.exists(pid_file)

    def test_acquire_removes_stale_pid(self, tmp_path):
        """Stale PID file (process not running) should be replaced."""
        pid_file = str(tmp_path / "sat-daemon.pid")
        with open(pid_file, "w") as f:
            f.write("99999999")  # PID that almost certainly doesn't exist
        with patch("src.daemon.PID_FILE", pid_file):
            # os.kill(99999999, 0) should raise ProcessLookupError
            _acquire_pid_lock()
            with open(pid_file) as f:
                assert int(f.read().strip()) == os.getpid()

    def test_acquire_exits_if_already_running(self, tmp_path):
        """If another daemon is running, _acquire_pid_lock should sys.exit(1)."""
        pid_file = str(tmp_path / "sat-daemon.pid")
        # Write our own PID -- os.kill(our_pid, 0) will succeed
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
        with patch("src.daemon.PID_FILE", pid_file):
            with pytest.raises(SystemExit) as exc_info:
                _acquire_pid_lock()
            assert exc_info.value.code == 1


class TestParseTaskProject:
    """Tests for parse_task_project(file_path)."""

    def test_directory_takes_priority_over_metadata(self, tmp_path):
        """Directory name is checked first — even if metadata says something else."""
        f = tmp_path / "sat-enhancements" / "001.md"
        f.parent.mkdir()
        f.write_text("<!-- project: my-cool-project -->\n# Title\n<Pending>\n")
        assert parse_task_project(str(f)) == "structured-achievement-tool"

    def test_infers_sat_from_directory(self, tmp_path):
        f = tmp_path / "sat-enhancements" / "001.md"
        f.parent.mkdir()
        f.write_text("# Title\n<Pending>\n")
        assert parse_task_project(str(f)) == "structured-achievement-tool"

    def test_passed_variable_used_for_unknown_dir(self, tmp_path):
        f = tmp_path / "other-project" / "001.md"
        f.parent.mkdir()
        f.write_text("# Title\n<Pending>\n")
        assert parse_task_project(str(f), passed_project="marketing") == "marketing"

    def test_metadata_used_as_last_resort(self, tmp_path):
        f = tmp_path / "unknown-dir" / "001.md"
        f.parent.mkdir()
        f.write_text("<!-- project: custom-project -->\n# Title\n<Pending>\n")
        assert parse_task_project(str(f)) == "custom-project"

    def test_falls_back_to_directory_name(self, tmp_path):
        f = tmp_path / "other-project" / "001.md"
        f.parent.mkdir()
        f.write_text("# Title\n<Pending>\n")
        assert parse_task_project(str(f)) == "other-project"


class TestParseTaskDependsOn:
    """Tests for parse_task_depends_on(file_path)."""

    def test_parses_single_dependency(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("<!-- depends_on: story_001.md -->\n# Title\n<Pending>\n")
        assert parse_task_depends_on(str(f)) == ["story_001.md"]

    def test_parses_multiple_dependencies(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("<!-- depends_on: a.md, b.md, c.md -->\n# Title\n<Pending>\n")
        assert parse_task_depends_on(str(f)) == ["a.md", "b.md", "c.md"]

    def test_returns_empty_when_none(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("# Title\n<Pending>\n")
        assert parse_task_depends_on(str(f)) == []


class TestPrerequisiteEnforcement:
    """Tests for prerequisite-based dependency checking."""

    def test_no_deps_means_met(self):
        db_manager = MagicMock()
        assert _check_prerequisites_met(db_manager, []) is True

    def test_finished_dep_is_met(self):
        db_manager = MagicMock()
        db_manager.find_task_state_by_name.return_value = {"status": "finished"}
        assert _check_prerequisites_met(db_manager, ["dep.md"]) is True

    def test_working_dep_is_not_met(self):
        db_manager = MagicMock()
        db_manager.find_task_state_by_name.return_value = {"status": "working"}
        assert _check_prerequisites_met(db_manager, ["dep.md"]) is False

    def test_pending_dep_is_not_met(self):
        db_manager = MagicMock()
        db_manager.find_task_state_by_name.return_value = {"status": "pending"}
        assert _check_prerequisites_met(db_manager, ["dep.md"]) is False

    def test_unknown_dep_treated_as_met(self):
        db_manager = MagicMock()
        db_manager.find_task_state_by_name.return_value = None
        assert _check_prerequisites_met(db_manager, ["gone.md"]) is True

    def test_mixed_deps(self):
        db_manager = MagicMock()
        db_manager.find_task_state_by_name.side_effect = [
            {"status": "finished"},
            {"status": "working"},
        ]
        assert _check_prerequisites_met(db_manager, ["done.md", "active.md"]) is False


class TestCircularDependencyDetection:
    """Tests for circular dependency detection using DAG executor."""

    def test_no_cycle_passes_through(self):
        db_manager = MagicMock()
        db_manager.find_task_state_by_name.return_value = {
            "task_path": "/path/a.md",
            "depends_on": "[]",
        }
        result = _detect_circular_deps(db_manager, "/path/b.md", ["a.md"])
        assert result == ["a.md"]

    def test_cycle_clears_deps(self):
        """A→B and B→A should detect a cycle and clear deps."""
        def _find(name):
            if "a.md" in name:
                return {"task_path": "/path/a.md", "depends_on": '["b.md"]'}
            if "b.md" in name:
                return {"task_path": "/path/b.md", "depends_on": '["a.md"]'}
            return None

        db_manager = MagicMock()
        db_manager.find_task_state_by_name.side_effect = _find
        result = _detect_circular_deps(db_manager, "/path/a.md", ["b.md"])
        assert result == []

    def test_empty_deps_passes(self):
        db_manager = MagicMock()
        result = _detect_circular_deps(db_manager, "/path/a.md", [])
        assert result == []


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
