"""Tests for src.llm.prompt_builder — Template loading + progressive disclosure."""

import os
import tempfile

from src.llm.prompt_builder import (
    PHASE_CONTEXT,
    PHASE_TEMPLATES,
    _format_acceptance_criteria,
    build_prompt,
    load_template,
    substitute_placeholders,
)


class TestLoadTemplate:
    def test_loads_existing_template(self):
        template = load_template("CLASSIFY")
        assert template is not None
        assert len(template) > 0

    def test_returns_none_for_unknown_phase(self):
        template = load_template("NONEXISTENT_PHASE")
        assert template is None

    def test_custom_template_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a test template
            with open(os.path.join(tmpdir, "design.md"), "w") as f:
                f.write("Custom template: {{STORY_TITLE}}")

            template = load_template("DESIGN", template_dir=tmpdir)
            assert template == "Custom template: {{STORY_TITLE}}"


class TestSubstitutePlaceholders:
    def test_basic_substitution(self):
        template = "Hello {{NAME}}, you are {{AGE}} years old."
        result = substitute_placeholders(template, {"name": "Alice", "age": "30"})
        assert result == "Hello Alice, you are 30 years old."

    def test_missing_key_not_replaced(self):
        template = "{{PRESENT}} and {{MISSING}}"
        result = substitute_placeholders(template, {"present": "here"})
        assert "here" in result
        assert "{{MISSING}}" in result

    def test_none_value_becomes_empty(self):
        template = "Value: {{KEY}}"
        result = substitute_placeholders(template, {"key": None})
        assert result == "Value: "


class TestBuildPrompt:
    def setup_method(self):
        self.story = {
            "id": "US-001",
            "title": "Test Story",
            "description": "A test story for unit testing",
            "acceptanceCriteria": ["It should work", "It should be tested"],
        }

    def test_build_with_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "design.md"), "w") as f:
                f.write("Design for {{STORY_TITLE}}: {{STORY_DESCRIPTION}}")

            prompt = build_prompt(
                story=self.story,
                phase="DESIGN",
                working_directory=tmpdir,
                template_dir=tmpdir,
            )
            assert "Test Story" in prompt
            assert "A test story for unit testing" in prompt

    def test_inline_fallback_when_no_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # No templates in this dir
            prompt = build_prompt(
                story=self.story,
                phase="DESIGN",
                working_directory=tmpdir,
                template_dir=tmpdir,
            )
            # Should still produce something
            assert "Test Story" in prompt
            assert "DESIGN" in prompt

    def test_claude_md_injection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write CLAUDE.md
            with open(os.path.join(tmpdir, "CLAUDE.md"), "w") as f:
                f.write("Always use pytest for testing.")

            prompt = build_prompt(
                story=self.story,
                phase="DESIGN",
                working_directory=tmpdir,
                template_dir=tmpdir,
            )
            assert "Always use pytest" in prompt
            assert "Project Rules" in prompt

    def test_progressive_disclosure_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "code.md"), "w") as f:
                f.write("Code: {{DESIGN_OUTPUT}} {{TEST_FILES}} {{ACCEPTANCE_CRITERIA}}")

            context = {
                "design_output": "Architecture plan here",
                "test_files": "test_main.py",
                "rag_context": "This should NOT appear in CODE phase",
            }
            prompt = build_prompt(
                story=self.story,
                phase="CODE",
                working_directory=tmpdir,
                context=context,
                template_dir=tmpdir,
            )
            assert "Architecture plan here" in prompt
            assert "test_main.py" in prompt


class TestFormatAcceptanceCriteria:
    def test_empty_list(self):
        result = _format_acceptance_criteria([])
        assert "No acceptance criteria" in result

    def test_numbered_list(self):
        result = _format_acceptance_criteria(["First", "Second"])
        assert "1. First" in result
        assert "2. Second" in result


class TestPhaseTemplateMapping:
    def test_all_major_phases_mapped(self):
        for phase in ("DESIGN", "CODE", "VERIFY", "LEARN", "PLAN", "EXECUTE"):
            assert phase in PHASE_TEMPLATES

    def test_fix_uses_code_template(self):
        assert PHASE_TEMPLATES["FIX"] == "code.md"


class TestPhaseContextDisclosure:
    def test_design_gets_task_description(self):
        assert "task_description" in PHASE_CONTEXT["DESIGN"]

    def test_code_gets_design_and_tests(self):
        assert "design_output" in PHASE_CONTEXT["CODE"]
        assert "test_files" in PHASE_CONTEXT["CODE"]

    def test_verify_gets_diff_and_test_results(self):
        assert "diff" in PHASE_CONTEXT["VERIFY"]
        assert "test_results" in PHASE_CONTEXT["VERIFY"]

    def test_code_does_not_get_rag_context(self):
        assert "rag_context" not in PHASE_CONTEXT["CODE"]
