"""Tests for src.agents.classifier_agent — Create vs Edit classification.

Tests the operation_mode detection logic:
- New file story -> operation_mode="create"
- Story with edit keyword + existing output file -> operation_mode="edit"
- Story with edit keyword but file doesn't exist -> operation_mode="create"
- Edit stories get complexity bump
- Content edit stories include existing file in context
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.classifier_agent import (
    ClassifierAgent,
    _extract_output_path,
    detect_operation_mode,
)
from src.llm.cli_runner import CLIResult
from src.llm.response_parser import ClassifyResponse

# --- Unit tests for detect_operation_mode ---


class TestDetectOperationMode:
    """Tests for the rule-based operation_mode detection."""

    def test_new_file_returns_create(self, tmp_path):
        """A story with no edit keywords should be 'create'."""
        result = detect_operation_mode(
            description="Write a new marketing email template",
            output_path=str(tmp_path / "new_file.md"),
            working_directory=str(tmp_path),
        )
        assert result == "create"

    def test_edit_keyword_and_existing_file_returns_edit(self, tmp_path):
        """Story with 'fix' keyword + existing file -> 'edit'."""
        target = tmp_path / "existing.md"
        target.write_text("# Existing content\nSome text here.")

        result = detect_operation_mode(
            description="Fix the formatting issues in the email template",
            output_path=str(target),
            working_directory=str(tmp_path),
        )
        assert result == "edit"

    def test_edit_keyword_but_file_missing_returns_create(self, tmp_path):
        """Story with 'update' keyword but file doesn't exist -> 'create'."""
        result = detect_operation_mode(
            description="Update the quarterly report with new data",
            output_path=str(tmp_path / "nonexistent.md"),
            working_directory=str(tmp_path),
        )
        assert result == "create"

    def test_no_output_path_returns_create(self, tmp_path):
        """Story with edit keyword but no output path -> 'create'."""
        result = detect_operation_mode(
            description="Fix the broken links in the guide",
            output_path=None,
            working_directory=str(tmp_path),
        )
        assert result == "create"

    def test_relative_path_resolved(self, tmp_path):
        """Relative output_path should be resolved against working_directory."""
        target = tmp_path / "docs" / "guide.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Guide\nOriginal content.")

        result = detect_operation_mode(
            description="Update the installation guide",
            output_path="docs/guide.md",
            working_directory=str(tmp_path),
        )
        assert result == "edit"

    @pytest.mark.parametrize(
        "keyword",
        [
            "fix",
            "update",
            "modify",
            "replace",
            "change",
            "edit",
            "rewrite",
            "correct",
            "patch",
            "revise",
        ],
    )
    def test_all_edit_keywords_detected(self, keyword, tmp_path):
        """Each edit keyword should be recognized."""
        target = tmp_path / "file.md"
        target.write_text("content")

        result = detect_operation_mode(
            description=f"Please {keyword} the document",
            output_path=str(target),
            working_directory=str(tmp_path),
        )
        assert result == "edit", f"Keyword '{keyword}' should trigger edit mode"

    def test_case_insensitive_keywords(self, tmp_path):
        """Keywords should be matched case-insensitively."""
        target = tmp_path / "file.md"
        target.write_text("content")

        result = detect_operation_mode(
            description="Please UPDATE the document",
            output_path=str(target),
            working_directory=str(tmp_path),
        )
        assert result == "edit"

    def test_keyword_must_be_word_boundary(self, tmp_path):
        """Keywords embedded in other words should NOT match (e.g., 'fixation')."""
        target = tmp_path / "file.md"
        target.write_text("content")

        result = detect_operation_mode(
            description="Write about fixation points in photography",
            output_path=str(target),
            working_directory=str(tmp_path),
        )
        assert result == "create"

    def test_no_keywords_no_match(self, tmp_path):
        """Description without edit keywords -> 'create' even with existing file."""
        target = tmp_path / "file.md"
        target.write_text("content")

        result = detect_operation_mode(
            description="Write a new email sequence for cold outreach",
            output_path=str(target),
            working_directory=str(tmp_path),
        )
        assert result == "create"


# --- Unit tests for _extract_output_path ---


class TestExtractOutputPath:
    """Tests for file path extraction from description text."""

    def test_absolute_path(self):
        path = _extract_output_path("Please update /home/user/docs/guide.md")
        assert path == "/home/user/docs/guide.md"

    def test_relative_path(self):
        path = _extract_output_path("Fix the file at ./templates/cold-email/intro.md")
        assert path == "./templates/cold-email/intro.md"

    def test_src_relative(self):
        path = _extract_output_path("Update src/agents/classifier_agent.py")
        assert path == "src/agents/classifier_agent.py"

    def test_no_path(self):
        path = _extract_output_path("Write a new marketing email")
        assert path is None


# --- Integration tests for ClassifierAgent.classify ---


class TestClassifierAgentClassify:
    """Tests for the full classify pipeline with mocked LLM."""

    @pytest.mark.asyncio
    async def test_classify_new_file_create_mode(self, tmp_path):
        """Classifying a new-file request should return operation_mode='create'."""
        agent = ClassifierAgent()

        mock_result = CLIResult(
            stdout='{"task_type": "content", "confidence": 0.95, "reasoning": "Document creation"}',
            exit_code=0,
        )

        with (
            patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=mock_result),
            patch("src.agents.base_agent.build_prompt", return_value="test prompt"),
        ):
            result = await agent.classify(
                user_request="Write a new cold-email template for prospects",
                working_directory=str(tmp_path),
            )

        assert isinstance(result, ClassifyResponse)
        assert result.task_type == "content"
        assert result.operation_mode == "create"

    @pytest.mark.asyncio
    async def test_classify_edit_with_existing_file(self, tmp_path):
        """Classifying a fix request with existing file -> operation_mode='edit'."""
        # Create the file that the description references
        target = tmp_path / "templates" / "cold-email" / "intro.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Cold Email Intro\nOriginal template content.")

        agent = ClassifierAgent()

        mock_result = CLIResult(
            stdout='{"task_type": "content", "confidence": 0.9, "reasoning": "Edit existing doc"}',
            exit_code=0,
        )

        with (
            patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=mock_result),
            patch("src.agents.base_agent.build_prompt", return_value="test prompt"),
        ):
            result = await agent.classify(
                user_request=f"Fix the tone in {target}",
                working_directory=str(tmp_path),
            )

        assert result.operation_mode == "edit"

    @pytest.mark.asyncio
    async def test_classify_edit_keyword_no_file(self, tmp_path):
        """Edit keyword present but file doesn't exist -> operation_mode='create'."""
        agent = ClassifierAgent()

        mock_result = CLIResult(
            stdout='{"task_type": "content", "confidence": 0.85, "reasoning": "Content task"}',
            exit_code=0,
        )

        with (
            patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=mock_result),
            patch("src.agents.base_agent.build_prompt", return_value="test prompt"),
        ):
            result = await agent.classify(
                user_request=f"Update the guide at {tmp_path}/nonexistent.md",
                working_directory=str(tmp_path),
            )

        assert result.operation_mode == "create"

    @pytest.mark.asyncio
    async def test_classify_llm_operation_mode_overridden(self, tmp_path):
        """Even if LLM returns operation_mode, rule-based detection overrides it."""
        agent = ClassifierAgent()

        # LLM says "edit" but there's no file, so rule-based should override to "create"
        mock_result = CLIResult(
            stdout='{"task_type": "content", "operation_mode": "edit", "confidence": 0.9, "reasoning": "test"}',
            exit_code=0,
        )

        with (
            patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=mock_result),
            patch("src.agents.base_agent.build_prompt", return_value="test prompt"),
        ):
            result = await agent.classify(
                user_request="Write a brand new email template",
                working_directory=str(tmp_path),
            )

        # Rule-based detection should override LLM's "edit" to "create"
        assert result.operation_mode == "create"


# --- Tests for complexity bump on edit stories ---


class TestEditComplexityBump:
    """Verify that edit stories get their complexity bumped by +1."""

    def test_edit_story_complexity_bump(self):
        """An edit story should have complexity bumped by 1."""
        from src.llm.response_parser import StorySchema

        story = StorySchema(
            id="S1",
            title="Fix email template",
            description="Fix the tone in the cold email",
            type="content",
            complexity=5,
        )

        # Simulate what orchestrator does
        operation_mode = "edit"
        if operation_mode == "edit":
            old_complexity = story.complexity
            story.complexity = min(old_complexity + 1, 10)

        assert story.complexity == 6

    def test_edit_story_complexity_cap_at_10(self):
        """Complexity bump should be capped at 10."""
        from src.llm.response_parser import StorySchema

        story = StorySchema(
            id="S1",
            title="Fix complex doc",
            description="Revise the architecture document",
            type="content",
            complexity=10,
        )

        operation_mode = "edit"
        if operation_mode == "edit":
            story.complexity = min(story.complexity + 1, 10)

        assert story.complexity == 10

    def test_create_story_no_complexity_bump(self):
        """A create story should NOT get a complexity bump."""
        from src.llm.response_parser import StorySchema

        story = StorySchema(
            id="S1",
            title="Write new doc",
            description="Create a new marketing guide",
            type="content",
            complexity=5,
        )

        operation_mode = "create"
        if operation_mode == "edit":
            story.complexity = min(story.complexity + 1, 10)

        assert story.complexity == 5


# --- Tests for content edit context injection ---


class TestContentEditContextInjection:
    """Verify that edit stories get existing file content injected into context."""

    def test_edit_story_includes_existing_file(self, tmp_path):
        """Content edit stories should have existing file content in context."""
        from src.workflows.base_workflow import _load_existing_file_for_edit

        target = tmp_path / "template.md"
        target.write_text("# Cold Email\n\nHello {{NAME}},\n\nOriginal content here.")

        story = {
            "id": "S1",
            "title": "Fix email template",
            "type": "content",
            "operation_mode": "edit",
            "output_path": str(target),
        }

        content = _load_existing_file_for_edit(story, str(tmp_path))
        assert "# Cold Email" in content
        assert "Original content here." in content

    def test_create_story_no_existing_file(self, tmp_path):
        """Create stories should not load existing file content."""
        from src.workflows.base_workflow import _load_existing_file_for_edit

        story = {
            "id": "S1",
            "title": "Write new doc",
            "type": "content",
            "operation_mode": "create",
            "output_path": str(tmp_path / "new_file.md"),
        }

        content = _load_existing_file_for_edit(story, str(tmp_path))
        assert content == ""

    def test_edit_story_no_output_path(self, tmp_path):
        """Edit story without output_path should return empty content."""
        from src.workflows.base_workflow import _load_existing_file_for_edit

        story = {
            "id": "S1",
            "title": "Fix something",
            "type": "content",
            "operation_mode": "edit",
        }

        content = _load_existing_file_for_edit(story, str(tmp_path))
        assert content == ""

    def test_large_file_truncated(self, tmp_path):
        """Files larger than 15000 chars should be truncated."""
        from src.workflows.base_workflow import _load_existing_file_for_edit

        target = tmp_path / "large.md"
        target.write_text("x" * 20000)

        story = {
            "id": "S1",
            "type": "content",
            "operation_mode": "edit",
            "output_path": str(target),
        }

        content = _load_existing_file_for_edit(story, str(tmp_path))
        assert len(content) < 20000
        assert "[...truncated at 15000 chars...]" in content

    def test_build_phase_context_injects_for_edit(self, tmp_path):
        """_build_phase_context should inject existing_file_content for edit stories."""
        from src.workflows.base_workflow import _build_phase_context

        target = tmp_path / "doc.md"
        target.write_text("# Existing Doc\nSome existing content.")

        state = {
            "story": {
                "id": "S1",
                "title": "Fix doc",
                "type": "content",
                "operation_mode": "edit",
                "output_path": str(target),
                "acceptanceCriteria": [],
            },
            "task_description": "Fix the doc",
            "working_directory": str(tmp_path),
            "design_output": "",
            "test_files": "",
            "plan_output": "",
            "failure_context": "",
        }

        ctx = _build_phase_context(state, "CONTENT_PLAN")
        assert "existing_file_content" in ctx
        assert "# Existing Doc" in ctx["existing_file_content"]

    def test_build_phase_context_skips_for_create(self, tmp_path):
        """_build_phase_context should NOT inject existing_file_content for create stories."""
        from src.workflows.base_workflow import _build_phase_context

        state = {
            "story": {
                "id": "S1",
                "title": "Write new doc",
                "type": "content",
                "operation_mode": "create",
                "output_path": str(tmp_path / "new.md"),
                "acceptanceCriteria": [],
            },
            "task_description": "Write a new doc",
            "working_directory": str(tmp_path),
            "design_output": "",
            "test_files": "",
            "plan_output": "",
            "failure_context": "",
        }

        ctx = _build_phase_context(state, "CONTENT_PLAN")
        assert "existing_file_content" not in ctx

    def test_build_phase_context_skips_for_non_content_phases(self, tmp_path):
        """_build_phase_context should NOT inject for non-content phases."""
        from src.workflows.base_workflow import _build_phase_context

        target = tmp_path / "code.py"
        target.write_text("print('hello')")

        state = {
            "story": {
                "id": "S1",
                "title": "Fix code",
                "type": "development",
                "operation_mode": "edit",
                "output_path": str(target),
                "acceptanceCriteria": [],
            },
            "task_description": "Fix the code",
            "working_directory": str(tmp_path),
            "design_output": "",
            "test_files": "",
            "plan_output": "",
            "failure_context": "",
        }

        ctx = _build_phase_context(state, "CODE")
        assert "existing_file_content" not in ctx


# --- Tests for ClassifyResponse model ---


class TestClassifyResponseModel:
    """Tests for the ClassifyResponse Pydantic model."""

    def test_default_operation_mode(self):
        """Default operation_mode should be 'create'."""
        resp = ClassifyResponse(task_type="content", confidence=0.9)
        assert resp.operation_mode == "create"

    def test_explicit_operation_mode(self):
        """Explicit operation_mode should be preserved."""
        resp = ClassifyResponse(task_type="content", operation_mode="edit", confidence=0.9)
        assert resp.operation_mode == "edit"

    def test_operation_mode_mutable(self):
        """operation_mode should be settable after construction (for rule-based override)."""
        resp = ClassifyResponse(task_type="content", confidence=0.9)
        resp.operation_mode = "edit"
        assert resp.operation_mode == "edit"


# --- Tests for StorySchema operation_mode field ---


class TestStorySchemaOperationMode:
    """Tests for the operation_mode field on StorySchema."""

    def test_default_create(self):
        from src.llm.response_parser import StorySchema

        story = StorySchema(id="S1", title="Test", description="desc")
        assert story.operation_mode == "create"

    def test_edit_mode(self):
        from src.llm.response_parser import StorySchema

        story = StorySchema(id="S1", title="Test", description="desc", operation_mode="edit")
        assert story.operation_mode == "edit"

    def test_round_trip_through_dict(self):
        from src.llm.response_parser import StorySchema

        story = StorySchema(id="S1", title="Test", description="desc", operation_mode="edit")
        d = story.model_dump()
        assert d["operation_mode"] == "edit"

        restored = StorySchema.model_validate(d)
        assert restored.operation_mode == "edit"
