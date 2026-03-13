"""Tests for post-execution output file verification in story_executor.

Covers verify_output_files() and _extract_expected_paths().
"""

import os
import time
from unittest.mock import patch

from src.execution.story_executor import (
    _extract_expected_paths,
    verify_output_files,
)


class TestExtractExpectedPaths:
    """Test _extract_expected_paths helper."""

    def test_explicit_output_path(self):
        story = {"output_path": "/tmp/output.md"}
        paths = _extract_expected_paths(story)
        assert "/tmp/output.md" in paths

    def test_paths_from_acceptance_criteria(self):
        story = {
            "acceptanceCriteria": [
                "Create file src/utils/helper.py with validation logic",
                "Update /etc/config/app.yml with new settings",
            ],
        }
        paths = _extract_expected_paths(story)
        assert "src/utils/helper.py" in paths
        assert "/etc/config/app.yml" in paths

    def test_no_duplicates(self):
        story = {
            "output_path": "src/foo.py",
            "acceptanceCriteria": ["Output to src/foo.py"],
        }
        paths = _extract_expected_paths(story)
        assert paths.count("src/foo.py") == 1

    def test_empty_story(self):
        paths = _extract_expected_paths({})
        assert paths == []

    def test_relative_paths_detected(self):
        story = {
            "acceptanceCriteria": [
                "Write output to ./output/report.md",
            ],
        }
        paths = _extract_expected_paths(story)
        assert any("output/report.md" in p for p in paths)


class TestVerifyOutputFiles:
    """Test verify_output_files() with mocked filesystem."""

    def _make_story(self, story_type="development", output_path=None, ac=None):
        story = {
            "id": "US-001",
            "title": "Test Story",
            "type": story_type,
            "acceptanceCriteria": ac or [],
        }
        if output_path:
            story["output_path"] = output_path
        return story

    def test_output_file_exists_passes(self, tmp_path):
        """Output file exists, non-empty, recently modified -> passes."""
        outfile = tmp_path / "result.py"
        outfile.write_text("print('hello')")

        start = time.time() - 1  # started 1s ago
        story = self._make_story(output_path=str(outfile))

        result = verify_output_files(story, str(tmp_path), start)
        assert result.passed is True
        assert len(result.failures) == 0
        assert str(outfile) in result.checked_files

    def test_output_file_missing_fails(self, tmp_path):
        """Output file does not exist -> fails with clear message."""
        missing = str(tmp_path / "nonexistent.py")
        story = self._make_story(output_path=missing)

        result = verify_output_files(story, str(tmp_path), time.time() - 1)
        assert result.passed is False
        assert any("does not exist" in f for f in result.failures)

    def test_output_file_empty_fails(self, tmp_path):
        """Output file exists but is empty -> fails."""
        outfile = tmp_path / "empty.py"
        outfile.write_text("")

        story = self._make_story(output_path=str(outfile))
        result = verify_output_files(story, str(tmp_path), time.time() - 1)
        assert result.passed is False
        assert any("empty" in f.lower() for f in result.failures)

    def test_output_file_not_modified_during_execution_fails(self, tmp_path):
        """Output file exists but was not modified during this execution -> fails."""
        outfile = tmp_path / "stale.py"
        outfile.write_text("old content")

        # Set mtime to the past
        old_time = time.time() - 3600
        os.utime(str(outfile), (old_time, old_time))

        # Execution started after the file was last modified
        start = time.time()
        story = self._make_story(output_path=str(outfile))

        result = verify_output_files(story, str(tmp_path), start)
        assert result.passed is False
        assert any("not modified" in f for f in result.failures)

    def test_config_story_no_output_passes(self):
        """Config story with no expected file output -> passes (lenient)."""
        story = self._make_story(story_type="config")
        result = verify_output_files(story, "/tmp", time.time())
        assert result.passed is True

    def test_research_story_no_output_passes(self):
        """Research story with no expected paths -> passes (lenient)."""
        story = self._make_story(story_type="research")
        result = verify_output_files(story, "/tmp", time.time())
        assert result.passed is True

    def test_content_story_skipped(self):
        """Content stories skip output verification entirely (own gates)."""
        story = self._make_story(story_type="content", output_path="/tmp/missing.md")
        result = verify_output_files(story, "/tmp", time.time())
        assert result.passed is True

    def test_dev_story_no_expected_paths_passes(self):
        """Dev story with no file paths in AC or metadata -> passes (nothing to check)."""
        story = self._make_story(story_type="development", ac=["Implement the feature"])
        result = verify_output_files(story, "/tmp", time.time())
        assert result.passed is True

    def test_multiple_files_one_missing_fails(self, tmp_path):
        """Story with output_path pointing to missing file -> fails even if other files exist."""
        good = tmp_path / "good.py"
        good.write_text("content")
        missing = tmp_path / "missing.py"

        # Use the missing file as the explicit output_path
        story = self._make_story(output_path=str(missing))
        result = verify_output_files(story, str(tmp_path), time.time() - 1)
        assert result.passed is False
        assert any("does not exist" in f for f in result.failures)

    def test_relative_path_resolved(self, tmp_path):
        """Relative output_path is resolved against working_directory."""
        subdir = tmp_path / "src"
        subdir.mkdir()
        outfile = subdir / "module.py"
        outfile.write_text("code")

        story = self._make_story(output_path="src/module.py")
        result = verify_output_files(story, str(tmp_path), time.time() - 1)
        assert result.passed is True

    def test_config_story_with_explicit_path_verifies(self, tmp_path):
        """Config story WITH an explicit output_path still verifies it."""
        missing = str(tmp_path / "config.yml")
        story = self._make_story(story_type="config", output_path=missing)

        result = verify_output_files(story, str(tmp_path), time.time() - 1)
        assert result.passed is False
        assert any("does not exist" in f for f in result.failures)

    @patch("src.execution.story_executor.os.path.getsize", side_effect=OSError("Permission denied"))
    @patch("src.execution.story_executor.os.path.exists", return_value=True)
    def test_stat_error_fails(self, mock_exists, mock_getsize):
        """OSError from getsize -> fails gracefully."""
        story = self._make_story(output_path="/some/file.py")
        result = verify_output_files(story, "/", time.time() - 1)
        assert result.passed is False
        assert any("cannot stat" in f for f in result.failures)

    @patch("src.execution.story_executor.os.path.getmtime", side_effect=OSError("No access"))
    @patch("src.execution.story_executor.os.path.getsize", return_value=100)
    @patch("src.execution.story_executor.os.path.exists", return_value=True)
    def test_mtime_error_fails(self, mock_exists, mock_getsize, mock_getmtime):
        """OSError from getmtime -> fails gracefully."""
        story = self._make_story(output_path="/some/file.py")
        result = verify_output_files(story, "/", time.time() - 1)
        assert result.passed is False
        assert any("cannot get mtime" in f for f in result.failures)
