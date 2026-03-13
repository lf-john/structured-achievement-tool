"""Tests for story-level classification — verifies per-story classification
after decomposition, classifier override, and fallback behavior."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.classifier_agent import ClassifierAgent
from src.llm.cli_runner import CLIResult
from src.llm.response_parser import ClassifyResponse, DecomposeResponse, StorySchema

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_classify_response(task_type: str, confidence: float = 0.9) -> CLIResult:
    """Build a CLIResult containing a valid ClassifyResponse JSON."""
    return CLIResult(
        stdout=json.dumps(
            {
                "task_type": task_type,
                "confidence": confidence,
                "reasoning": f"classified as {task_type}",
            }
        ),
        exit_code=0,
    )


def _make_story(
    story_id: str,
    title: str,
    description: str,
    story_type: str = "development",
    acceptance_criteria: list[str] | None = None,
    output_path: str | None = None,
) -> StorySchema:
    return StorySchema(
        id=story_id,
        title=title,
        description=description,
        type=story_type,
        acceptanceCriteria=acceptance_criteria or [],
        output_path=output_path,
    )


# ---------------------------------------------------------------------------
# ClassifierAgent.classify_story unit tests
# ---------------------------------------------------------------------------


class TestClassifyStory:
    """Test the new classify_story method on ClassifierAgent."""

    @pytest.mark.asyncio
    async def test_classify_story_returns_response(self):
        """classify_story returns a valid ClassifyResponse."""
        agent = ClassifierAgent()
        mock_result = _make_classify_response("content")

        with (
            patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=mock_result),
            patch("src.agents.base_agent.build_prompt", return_value="prompt"),
        ):
            result = await agent.classify_story(
                story_id="S1",
                story_title="Write email template",
                story_description="Create an HTML email template for welcome sequence",
                acceptance_criteria=["Template renders in major email clients"],
                output_path="templates/welcome.html",
                suggested_type="development",
                working_directory="/tmp",
            )

        assert isinstance(result, ClassifyResponse)
        assert result.task_type == "content"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_classify_story_includes_story_details_in_description(self):
        """The composite description sent to the LLM contains story fields."""
        agent = ClassifierAgent()
        mock_result = _make_classify_response("content")
        captured_prompts = []

        def capture_build_prompt(**kwargs):
            captured_prompts.append(kwargs)
            return "prompt"

        with (
            patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=mock_result),
            patch("src.agents.base_agent.build_prompt", side_effect=capture_build_prompt),
        ):
            await agent.classify_story(
                story_id="S1",
                story_title="Write guide",
                story_description="Create a deployment guide",
                acceptance_criteria=["Covers Docker", "Covers systemd"],
                output_path="docs/deploy.md",
                suggested_type="development",
                working_directory="/tmp",
            )

        assert len(captured_prompts) == 1
        story_desc = captured_prompts[0]["story"]["description"]
        assert "Write guide" in story_desc
        assert "Create a deployment guide" in story_desc
        assert "Covers Docker" in story_desc
        assert "docs/deploy.md" in story_desc
        assert "development" in story_desc  # suggested type included as hint

    @pytest.mark.asyncio
    async def test_classify_story_without_optional_fields(self):
        """classify_story works when acceptance_criteria and output_path are empty/None."""
        agent = ClassifierAgent()
        mock_result = _make_classify_response("debug")

        with (
            patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=mock_result),
            patch("src.agents.base_agent.build_prompt", return_value="prompt"),
        ):
            result = await agent.classify_story(
                story_id="S2",
                story_title="Fix login bug",
                story_description="Users can't log in after password reset",
                acceptance_criteria=[],
                output_path=None,
                suggested_type="development",
                working_directory="/tmp",
            )

        assert result.task_type == "debug"


# ---------------------------------------------------------------------------
# Orchestrator integration: per-story classification after decomposition
# ---------------------------------------------------------------------------


class TestOrchestratorStoryClassification:
    """Test that the orchestrator classifies each story individually after decomposition."""

    def _make_orchestrator(self, tmp_path):
        """Create an OrchestratorV2 with mocked externals."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"execution": {"max_retries_per_story": 1}}))

        with patch("src.orchestrator_v2.EmbeddingService", side_effect=Exception("no ollama")):
            from src.orchestrator_v2 import OrchestratorV2

            return OrchestratorV2(str(tmp_path))

    @pytest.mark.asyncio
    async def test_mixed_story_types_get_correct_classification(self, tmp_path):
        """A task decomposed into content + dev stories gets per-story types."""
        orchestrator = self._make_orchestrator(tmp_path)

        # Create task file
        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        task_file = task_dir / "001_task.md"
        task_file.write_text("Build a feature and write its docs")

        # Mock task-level classify
        task_classify = ClassifyResponse(task_type="development", confidence=0.8, reasoning="mixed task")

        # Mock decomposition: two stories, both suggested as "development"
        decompose_result = DecomposeResponse(
            stories=[
                _make_story("S1", "Implement API", "Build REST endpoint", "development", ["Endpoint returns 200"]),
                _make_story(
                    "S2",
                    "Write user guide",
                    "Create markdown guide",
                    "development",
                    ["Guide covers all endpoints"],
                    "docs/guide.md",
                ),
            ]
        )

        # Mock per-story classification: S1 stays dev, S2 reclassified to content
        story_classifications = {
            "S1": ClassifyResponse(task_type="development", confidence=0.95, reasoning="code task"),
            "S2": ClassifyResponse(task_type="content", confidence=0.92, reasoning="document task"),
        }

        async def mock_classify_story(**kwargs):
            return story_classifications[kwargs["story_id"]]

        mock_classify_story_fn = AsyncMock(side_effect=mock_classify_story)

        # Mock execute_story to avoid actual execution
        mock_story_result = MagicMock()
        mock_story_result.success = True
        mock_story_result.story_id = "S1"
        mock_story_result.attempts = 1
        mock_story_result.reason = None
        mock_story_result.phase_outputs = []

        with (
            patch.object(orchestrator.classifier, "classify", new_callable=AsyncMock, return_value=task_classify),
            patch.object(orchestrator.story_agent, "decompose", new_callable=AsyncMock, return_value=decompose_result),
            patch.object(orchestrator.classifier, "classify_story", mock_classify_story_fn),
            patch("src.orchestrator_v2.execute_story", new_callable=AsyncMock, return_value=mock_story_result),
            patch("src.orchestrator_v2.init_checkpoint_db"),
            patch("src.orchestrator_v2.read_checkpoint", return_value=None),
            patch.object(orchestrator.notifier, "notify_task_start"),
            patch.object(orchestrator.notifier, "notify_task_complete"),
            patch("src.orchestrator_v2.validate_spec") as mock_validate,
        ):
            # Make spec validation pass
            mock_spec = MagicMock()
            mock_spec.errors = []
            mock_spec.warnings = []
            mock_spec.metadata = {}
            mock_validate.return_value = mock_spec

            # Patch _resolve_project_working_directory
            with patch.object(orchestrator, "_resolve_project_working_directory", return_value=str(tmp_path)):
                await orchestrator.process_task_file(str(task_file))

        # Verify classify_story was called for each story
        assert mock_classify_story_fn.call_count == 2

        # Verify the stories were updated with classifier results
        # S2 should have been reclassified from "development" to "content"
        assert decompose_result.stories[0].type == "development"
        assert decompose_result.stories[1].type == "content"

    @pytest.mark.asyncio
    async def test_classifier_override_when_decomposer_wrong(self, tmp_path):
        """Classifier overrides decomposer's suggested type."""
        orchestrator = self._make_orchestrator(tmp_path)

        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        task_file = task_dir / "001_task.md"
        task_file.write_text("Fix the broken login page")

        task_classify = ClassifyResponse(task_type="debug", confidence=0.7, reasoning="fix task")

        # Decomposer suggests "development" but classifier says "debug"
        decompose_result = DecomposeResponse(
            stories=[
                _make_story("S1", "Fix login handler", "Debug authentication failure", "development"),
            ]
        )

        story_classify = ClassifyResponse(task_type="debug", confidence=0.88, reasoning="fixing a bug")

        mock_classify_story_fn = AsyncMock(return_value=story_classify)

        mock_story_result = MagicMock()
        mock_story_result.success = True
        mock_story_result.story_id = "S1"
        mock_story_result.attempts = 1
        mock_story_result.reason = None
        mock_story_result.phase_outputs = []

        with (
            patch.object(orchestrator.classifier, "classify", new_callable=AsyncMock, return_value=task_classify),
            patch.object(orchestrator.story_agent, "decompose", new_callable=AsyncMock, return_value=decompose_result),
            patch.object(orchestrator.classifier, "classify_story", mock_classify_story_fn),
            patch("src.orchestrator_v2.execute_story", new_callable=AsyncMock, return_value=mock_story_result),
            patch("src.orchestrator_v2.init_checkpoint_db"),
            patch("src.orchestrator_v2.read_checkpoint", return_value=None),
            patch.object(orchestrator.notifier, "notify_task_start"),
            patch.object(orchestrator.notifier, "notify_task_complete"),
            patch("src.orchestrator_v2.validate_spec") as mock_validate,
        ):
            mock_spec = MagicMock()
            mock_spec.errors = []
            mock_spec.warnings = []
            mock_spec.metadata = {}
            mock_validate.return_value = mock_spec

            with patch.object(orchestrator, "_resolve_project_working_directory", return_value=str(tmp_path)):
                await orchestrator.process_task_file(str(task_file))

        # Story should be reclassified from "development" to "debug"
        assert decompose_result.stories[0].type == "debug"

    @pytest.mark.asyncio
    async def test_single_story_task_classified_correctly(self, tmp_path):
        """Single-story tasks still work with per-story classification."""
        orchestrator = self._make_orchestrator(tmp_path)

        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        task_file = task_dir / "001_task.md"
        task_file.write_text("Research cloud providers")

        task_classify = ClassifyResponse(task_type="research", confidence=0.85, reasoning="research task")

        decompose_result = DecomposeResponse(
            stories=[
                _make_story("S1", "Compare cloud providers", "Research AWS vs GCP vs Azure", "research"),
            ]
        )

        story_classify = ClassifyResponse(task_type="research", confidence=0.95, reasoning="research task")

        mock_classify_story_fn = AsyncMock(return_value=story_classify)

        mock_story_result = MagicMock()
        mock_story_result.success = True
        mock_story_result.story_id = "S1"
        mock_story_result.attempts = 1
        mock_story_result.reason = None
        mock_story_result.phase_outputs = []

        with (
            patch.object(orchestrator.classifier, "classify", new_callable=AsyncMock, return_value=task_classify),
            patch.object(orchestrator.story_agent, "decompose", new_callable=AsyncMock, return_value=decompose_result),
            patch.object(orchestrator.classifier, "classify_story", mock_classify_story_fn),
            patch("src.orchestrator_v2.execute_story", new_callable=AsyncMock, return_value=mock_story_result),
            patch("src.orchestrator_v2.init_checkpoint_db"),
            patch("src.orchestrator_v2.read_checkpoint", return_value=None),
            patch.object(orchestrator.notifier, "notify_task_start"),
            patch.object(orchestrator.notifier, "notify_task_complete"),
            patch("src.orchestrator_v2.validate_spec") as mock_validate,
        ):
            mock_spec = MagicMock()
            mock_spec.errors = []
            mock_spec.warnings = []
            mock_spec.metadata = {}
            mock_validate.return_value = mock_spec

            with patch.object(orchestrator, "_resolve_project_working_directory", return_value=str(tmp_path)):
                await orchestrator.process_task_file(str(task_file))

        # Verify classify_story called exactly once
        assert mock_classify_story_fn.call_count == 1
        # Type should remain "research"
        assert decompose_result.stories[0].type == "research"

    @pytest.mark.asyncio
    async def test_classification_failure_falls_back_to_suggested_type(self, tmp_path):
        """When classify_story raises, the decomposer's suggested type is kept."""
        orchestrator = self._make_orchestrator(tmp_path)

        task_dir = tmp_path / "test-task"
        task_dir.mkdir()
        task_file = task_dir / "001_task.md"
        task_file.write_text("Deploy the application")

        task_classify = ClassifyResponse(task_type="config", confidence=0.8, reasoning="config task")

        decompose_result = DecomposeResponse(
            stories=[
                _make_story("S1", "Write Dockerfile", "Create Dockerfile for app", "config"),
                _make_story("S2", "Write deploy script", "Create deployment script", "development"),
            ]
        )

        # First story classifies fine, second raises
        async def mock_classify_story(**kwargs):
            if kwargs["story_id"] == "S1":
                return ClassifyResponse(task_type="config", confidence=0.9, reasoning="ok")
            raise ValueError("LLM call failed")

        mock_classify_story_fn = AsyncMock(side_effect=mock_classify_story)

        mock_story_result = MagicMock()
        mock_story_result.success = True
        mock_story_result.story_id = "S1"
        mock_story_result.attempts = 1
        mock_story_result.reason = None
        mock_story_result.phase_outputs = []

        with (
            patch.object(orchestrator.classifier, "classify", new_callable=AsyncMock, return_value=task_classify),
            patch.object(orchestrator.story_agent, "decompose", new_callable=AsyncMock, return_value=decompose_result),
            patch.object(orchestrator.classifier, "classify_story", mock_classify_story_fn),
            patch("src.orchestrator_v2.execute_story", new_callable=AsyncMock, return_value=mock_story_result),
            patch("src.orchestrator_v2.init_checkpoint_db"),
            patch("src.orchestrator_v2.read_checkpoint", return_value=None),
            patch.object(orchestrator.notifier, "notify_task_start"),
            patch.object(orchestrator.notifier, "notify_task_complete"),
            patch("src.orchestrator_v2.validate_spec") as mock_validate,
        ):
            mock_spec = MagicMock()
            mock_spec.errors = []
            mock_spec.warnings = []
            mock_spec.metadata = {}
            mock_validate.return_value = mock_spec

            with patch.object(orchestrator, "_resolve_project_working_directory", return_value=str(tmp_path)):
                await orchestrator.process_task_file(str(task_file))

        # S1 classified successfully
        assert decompose_result.stories[0].type == "config"
        # S2 classification failed — keeps decomposer's suggested type "development"
        assert decompose_result.stories[1].type == "development"
