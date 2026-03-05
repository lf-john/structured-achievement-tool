"""Tests for src.workflows.content_workflow and src.workflows.content_models."""

import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch

from src.workflows.content_workflow import (
    ContentWorkflow,
    mechanical_verify_node,
    mechanical_verify_decision,
    agentic_verify_decision,
    _parse_range,
    _detect_output_path,
    _extract_plan_data,
    MAX_VERIFY_RETRIES,
)
from src.workflows.content_models import (
    DocType,
    Group1Rule,
    Group2Quality,
    get_rules_for_doc_type,
    get_qualities_for_doc_type,
    format_group1_for_prompt,
    format_group2_for_prompt,
)


class TestParseRange:
    def test_simple_range(self):
        assert _parse_range("500-2000") == (500, 2000)

    def test_gte(self):
        assert _parse_range(">=3") == (3, float("inf"))

    def test_lte(self):
        assert _parse_range("<=100") == (0, 100)

    def test_exact(self):
        assert _parse_range("500") == (500, 500)

    def test_empty(self):
        assert _parse_range("") == (0, float("inf"))

    def test_none(self):
        assert _parse_range(None) == (0, float("inf"))

    def test_invalid(self):
        assert _parse_range("abc") == (0, float("inf"))


class TestMechanicalVerifyDecision:
    def test_pass_routes_to_agentic(self):
        state = {"verify_passed": True, "phase_retry_count": 0}
        assert mechanical_verify_decision(state) == "agentic_verify"

    def test_fail_routes_to_write(self):
        state = {"verify_passed": False, "phase_retry_count": 1}
        assert mechanical_verify_decision(state) == "write"

    def test_fail_at_retry_limit_skips_to_agentic(self):
        state = {"verify_passed": False, "phase_retry_count": MAX_VERIFY_RETRIES}
        assert mechanical_verify_decision(state) == "agentic_verify"


class TestAgenticVerifyDecision:
    def test_pass_routes_to_learn(self):
        state = {"verify_passed": True, "phase_retry_count": 0}
        assert agentic_verify_decision(state) == "learn"

    def test_fail_routes_to_write(self):
        state = {"verify_passed": False, "phase_retry_count": 1}
        assert agentic_verify_decision(state) == "write"

    def test_fail_at_retry_limit_routes_to_learn(self):
        state = {"verify_passed": False, "phase_retry_count": MAX_VERIFY_RETRIES}
        assert agentic_verify_decision(state) == "learn"


class TestMechanicalVerifyNode:
    def _make_state(self, content, doc_type="technical"):
        """Create a state with a temp file containing content."""
        tmpdir = tempfile.mkdtemp()
        output_path = os.path.join(tmpdir, "output.md")
        with open(output_path, "w") as f:
            f.write(content)
        return {
            "story": {"id": "S1", "doc_type": doc_type, "output_path": output_path},
            "working_directory": tmpdir,
            "current_phase": "",
            "phase_outputs": [],
        }

    def test_passes_valid_document(self):
        content = "# Introduction\n\nThis is a test document with enough words.\n\n"
        content += "## Section One\n\nLorem ipsum dolor sit amet. " * 50
        content += "\n\n```python\nprint('hello')\n```\n"
        content += "\n\n## Section Two\n\nMore content here.\n"
        content += "\n### Sub One\n\nDetails.\n### Sub Two\n\nMore details.\n### Sub Three\n\nEven more.\n"
        state = self._make_state(content, "technical")
        result = mechanical_verify_node(state)
        assert result["verify_passed"] is True

    def test_fails_on_missing_file(self):
        state = {
            "story": {"id": "S1", "output_path": "/nonexistent/path.md"},
            "working_directory": "/tmp",
            "current_phase": "",
            "phase_outputs": [],
        }
        result = mechanical_verify_node(state)
        assert result["verify_passed"] is False
        assert "not found" in result.get("failure_context", "")

    def test_fails_on_placeholders(self):
        content = "# Title\n\n## S1\n\n### Sub1\n### Sub2\n### Sub3\n\n"
        content += "Hello {{PLACEHOLDER}} world. " * 100
        state = self._make_state(content)
        result = mechanical_verify_node(state)
        assert result["verify_passed"] is False
        assert "placeholder" in result.get("failure_context", "").lower()

    def test_fails_on_merge_markers(self):
        content = "# Title\n\n## S1\n\n### Sub1\n### Sub2\n### Sub3\n\n"
        content += "Normal text. " * 100
        content += "\n<<<<<<< HEAD\nconflict\n=======\nother\n>>>>>>> branch\n"
        state = self._make_state(content)
        result = mechanical_verify_node(state)
        assert result["verify_passed"] is False
        assert "merge" in result.get("failure_context", "").lower()

    def test_uses_doc_type_word_count(self):
        """Marketing docs have word_count 200-1500, so 10 words should fail."""
        content = "# Title\n\n## S1\n\n### Sub1\n### Sub2\n### Sub3\n\nToo short."
        state = self._make_state(content, "marketing")
        result = mechanical_verify_node(state)
        assert result["verify_passed"] is False
        assert "word count" in result.get("failure_context", "").lower()

    def test_increments_retry_count_on_failure(self):
        state = {
            "story": {"id": "S1", "output_path": "/nonexistent.md"},
            "working_directory": "/tmp",
            "current_phase": "",
            "phase_outputs": [],
            "phase_retry_count": 1,
        }
        result = mechanical_verify_node(state)
        assert result["phase_retry_count"] == 2


class TestDetectOutputPath:
    def test_extracts_from_json_output(self):
        state = {
            "phase_outputs": [
                {"phase": "WRITE", "output": '{"output_path": "docs/readme.md"}'}
            ]
        }
        assert _detect_output_path(state, "/project") == "docs/readme.md"

    def test_extracts_from_text_path(self):
        state = {
            "phase_outputs": [
                {"phase": "WRITE", "output": "Created file at docs/output.md done."}
            ]
        }
        assert _detect_output_path(state, "/project") == "docs/output.md"

    def test_returns_empty_when_no_write_output(self):
        state = {"phase_outputs": []}
        assert _detect_output_path(state, "/project") == ""


class TestDocTypeModels:
    def test_all_doc_types_exist(self):
        expected = {"technical", "marketing", "reference", "seo", "policy", "legal", "instructional"}
        actual = {dt.value for dt in DocType}
        assert expected == actual

    def test_get_rules_returns_list(self):
        rules = get_rules_for_doc_type("technical")
        assert isinstance(rules, list)
        assert len(rules) > 0
        assert all(isinstance(r, Group1Rule) for r in rules)

    def test_get_rules_applies_overrides(self):
        tech_rules = {r.name: r for r in get_rules_for_doc_type("technical")}
        marketing_rules = {r.name: r for r in get_rules_for_doc_type("marketing")}
        # Technical requires code blocks >=1, marketing doesn't
        assert tech_rules["code_blocks"].value == ">=1"
        assert marketing_rules["emojis"].value == "optional"

    def test_get_qualities_returns_list(self):
        qualities = get_qualities_for_doc_type("marketing")
        assert isinstance(qualities, list)
        assert len(qualities) > 0
        assert all(isinstance(q, Group2Quality) for q in qualities)

    def test_marketing_enables_persuasiveness(self):
        qualities = {q.name: q for q in get_qualities_for_doc_type("marketing")}
        assert qualities["persuasiveness"].enabled is True
        assert qualities["brand_voice"].enabled is True

    def test_technical_disables_persuasiveness(self):
        qualities = {q.name: q for q in get_qualities_for_doc_type("technical")}
        assert qualities["persuasiveness"].enabled is False

    def test_legal_type_rules(self):
        rules = {r.name: r for r in get_rules_for_doc_type("legal")}
        assert rules["emojis"].value == "none"
        assert rules["code_blocks"].value == "none"
        assert rules["heading_count"].value == ">=3"
        assert rules["word_count"].value == "500-10000"

    def test_format_group1_for_prompt(self):
        rules = get_rules_for_doc_type("technical")
        text = format_group1_for_prompt(rules)
        assert "word_count" in text
        assert "heading_count" in text

    def test_format_group2_for_prompt(self):
        qualities = get_qualities_for_doc_type("marketing")
        text = format_group2_for_prompt(qualities)
        assert "tone" in text
        assert "persuasiveness" in text

    def test_unknown_doc_type_uses_defaults(self):
        """Unknown doc type should return default rules without overrides."""
        rules = get_rules_for_doc_type("unknown_type")
        assert isinstance(rules, list)
        assert len(rules) > 0


class TestContentWorkflowGraph:
    def test_has_all_nodes(self):
        workflow = ContentWorkflow(routing_engine=MagicMock())
        graph = workflow.build_graph()
        node_names = set(graph.nodes.keys())
        expected = {"plan", "write", "mechanical_verify", "agentic_verify", "learn"}
        assert expected == node_names

    def test_compiles_without_error(self):
        workflow = ContentWorkflow(routing_engine=MagicMock())
        compiled = workflow.compile()
        assert compiled is not None

    def test_entry_point_is_plan(self):
        workflow = ContentWorkflow(routing_engine=MagicMock())
        graph = workflow.build_graph()
        assert "plan" in graph.nodes

    def test_pass_routes_to_agentic(self):
        assert mechanical_verify_decision({"verify_passed": True}) == "agentic_verify"

    def test_agentic_pass_routes_to_learn(self):
        assert agentic_verify_decision({"verify_passed": True}) == "learn"
