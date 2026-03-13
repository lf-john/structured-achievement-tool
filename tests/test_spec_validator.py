"""Tests for the spec validator pre-processing pipeline stage."""

import os
from unittest.mock import MagicMock, patch

from src.agents.spec_validator import validate_spec

# --- Fixtures ---

COMPLETE_SPEC = """\
# Task: Build the Widget

## Description
Build a new widget for the dashboard.

## Output
`~/projects/my-project/src/widget.py`

## Dependencies:
T21, T22

## Story Type:
development

## Acceptance Criteria
- [ ] Widget renders correctly
- [ ] Unit tests pass
- [ ] No lint errors
"""

MINIMAL_VALID_SPEC = """\
# Task: Quick Fix

## Output
`/tmp/fix.py`

- [ ] Fix applied
"""

NO_OUTPUT_SPEC = """\
# Task: Missing Output

## Description
A task with no output section.

- [ ] Something done
"""

EMPTY_OUTPUT_SPEC = """\
# Task: Empty Output

## Output

## Description
Output section is empty.
"""

NO_PATH_IN_OUTPUT_SPEC = """\
# Task: No Path

## Output
Just some text without a file path reference.
"""

NO_ACCEPTANCE_SPEC = """\
# Task: No Criteria

## Output
`/tmp/result.txt`

Just do the thing.
"""

UNMET_DEPS_SPEC = """\
# Task: Blocked

## Output
`/tmp/blocked.py`

## Dependencies:
T21, T22

- [ ] Done
"""

INVALID_STORY_TYPE_SPEC = """\
# Task: Bad Type

## Output
`/tmp/bad.py`

## Story Type:
banana

- [ ] Done
"""

NO_DEPS_SPEC = """\
# Task: Independent

## Output
`/tmp/independent.py`

- [ ] Done
"""

DEPS_NONE_SPEC = """\
# Task: No Deps Listed

## Output
`/tmp/nodeps.py`

## Dependencies:
None

- [ ] Done
"""


class TestCompleteSpec:
    """Task with complete spec should be valid."""

    def test_complete_spec_valid(self):
        db = MagicMock()
        db.find_task_state_by_name.return_value = {"status": "finished"}

        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(COMPLETE_SPEC, db_manager=db)

        assert result.valid is True
        assert result.errors == []
        assert result.metadata["output_path"] == os.path.expanduser("~/projects/my-project/src/widget.py")
        assert result.metadata["acceptance_criteria_count"] == 3
        assert result.metadata["story_type"] == "development"
        assert result.metadata["dependencies"] == ["T21", "T22"]
        assert result.metadata["has_existing_output"] is False


class TestMissingOutput:
    """Task missing output section should produce an error."""

    def test_no_output_section(self):
        result = validate_spec(NO_OUTPUT_SPEC)

        assert result.valid is False
        assert any("Missing '## Output'" in e for e in result.errors)

    def test_empty_output_section(self):
        result = validate_spec(EMPTY_OUTPUT_SPEC)

        assert result.valid is False
        assert any("empty" in e.lower() for e in result.errors)

    def test_output_without_path(self):
        result = validate_spec(NO_PATH_IN_OUTPUT_SPEC)

        assert result.valid is False
        assert any("file path" in e.lower() for e in result.errors)


class TestDependencyCheck:
    """Dependency validation against database."""

    def test_unmet_dependencies_error(self):
        db = MagicMock()

        # T21 is finished, T22 is still working
        def find_side_effect(name):
            if name == "T21":
                return {"status": "finished"}
            elif name == "T22":
                return {"status": "working"}
            return None

        db.find_task_state_by_name.side_effect = find_side_effect

        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(UNMET_DEPS_SPEC, db_manager=db)

        assert result.valid is False
        assert any("Unmet dependencies" in e for e in result.errors)
        assert any("T22" in e for e in result.errors)

    def test_all_deps_finished_valid(self):
        db = MagicMock()
        db.find_task_state_by_name.return_value = {"status": "finished"}

        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(UNMET_DEPS_SPEC, db_manager=db)

        assert result.valid is True
        assert result.errors == []

    def test_dep_not_found_in_database(self):
        db = MagicMock()
        db.find_task_state_by_name.return_value = None

        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(UNMET_DEPS_SPEC, db_manager=db)

        assert result.valid is False
        assert any("not found" in e for e in result.errors)

    def test_no_deps_section_is_fine(self):
        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(NO_DEPS_SPEC)

        assert result.valid is True
        assert result.metadata["dependencies"] == []

    def test_deps_none_is_fine(self):
        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(DEPS_NONE_SPEC)

        assert result.valid is True

    def test_deps_without_db_gives_warning(self):
        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(UNMET_DEPS_SPEC, db_manager=None)

        assert result.valid is True  # No error, just warning
        assert any("no database" in w.lower() for w in result.warnings)


class TestOutputFileExistence:
    """Output file existence check for create vs edit."""

    def test_existing_output_file_flagged(self):
        db = MagicMock()
        db.find_task_state_by_name.return_value = {"status": "finished"}

        with patch("src.agents.spec_validator.os.path.exists", return_value=True):
            result = validate_spec(COMPLETE_SPEC, db_manager=db)

        assert result.valid is True
        assert result.metadata["has_existing_output"] is True

    def test_nonexistent_output_file(self):
        db = MagicMock()
        db.find_task_state_by_name.return_value = {"status": "finished"}

        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(COMPLETE_SPEC, db_manager=db)

        assert result.valid is True
        assert result.metadata["has_existing_output"] is False


class TestStoryType:
    """Story type validation."""

    def test_invalid_story_type_warning(self):
        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(INVALID_STORY_TYPE_SPEC)

        assert result.valid is True  # Warning, not error
        assert any("banana" in w for w in result.warnings)
        assert result.metadata["story_type"] == "banana"

    def test_valid_story_type_no_warning(self):
        db = MagicMock()
        db.find_task_state_by_name.return_value = {"status": "finished"}

        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(COMPLETE_SPEC, db_manager=db)

        type_warnings = [w for w in result.warnings if "story type" in w.lower()]
        assert type_warnings == []
        assert result.metadata["story_type"] == "development"


class TestAcceptanceCriteria:
    """Acceptance criteria check."""

    def test_no_acceptance_criteria_warning(self):
        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(NO_ACCEPTANCE_SPEC)

        assert result.valid is True  # Warning, not error
        assert any("acceptance criteria" in w.lower() for w in result.warnings)
        assert result.metadata["acceptance_criteria_count"] == 0

    def test_has_acceptance_criteria(self):
        db = MagicMock()
        db.find_task_state_by_name.return_value = {"status": "finished"}

        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(COMPLETE_SPEC, db_manager=db)

        ac_warnings = [w for w in result.warnings if "acceptance criteria" in w.lower()]
        assert ac_warnings == []
        assert result.metadata["acceptance_criteria_count"] == 3


class TestMinimalSpec:
    """Minimal but valid spec."""

    def test_minimal_valid(self):
        with patch("src.agents.spec_validator.os.path.exists", return_value=False):
            result = validate_spec(MINIMAL_VALID_SPEC)

        assert result.valid is True
        assert result.metadata["output_path"] == "/tmp/fix.py"
        assert result.metadata["acceptance_criteria_count"] == 1
