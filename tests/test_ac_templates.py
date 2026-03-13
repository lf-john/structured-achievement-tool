"""Tests for src.agents.ac_templates."""

from src.agents.ac_templates import get_default_acs, merge_acs


class TestGetDefaultAcs:
    def test_returns_list_for_known_types(self):
        for t in ["development", "content", "research", "config", "maintenance", "review", "debug"]:
            acs = get_default_acs(t)
            assert isinstance(acs, list)
            assert len(acs) > 0

    def test_returns_empty_for_unknown_type(self):
        assert get_default_acs("unknown") == []

    def test_returns_copy(self):
        """Should not return the same list object."""
        a = get_default_acs("development")
        b = get_default_acs("development")
        assert a == b
        assert a is not b


class TestMergeAcs:
    def test_story_acs_only(self):
        assert merge_acs(["AC1", "AC2"], []) == ["AC1", "AC2"]

    def test_defaults_only(self):
        assert merge_acs([], ["D1", "D2"]) == ["D1", "D2"]

    def test_no_duplicates(self):
        result = merge_acs(["Common AC"], ["Common AC", "Extra"])
        assert len(result) == 2
        assert result[0] == "Common AC"
        assert result[1] == "Extra"

    def test_case_insensitive_dedup(self):
        result = merge_acs(["Tests Pass"], ["tests pass", "Other"])
        assert len(result) == 2

    def test_story_acs_first(self):
        result = merge_acs(["Story First"], ["Default"])
        assert result[0] == "Story First"
        assert result[1] == "Default"
