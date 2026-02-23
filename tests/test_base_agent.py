"""Tests for src.agents.base_agent — Abstract base LLM agent pipeline."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pydantic import BaseModel

from src.agents.base_agent import BaseAgent
from src.llm.response_parser import ClassifyResponse
from src.llm.cli_runner import CLIResult


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing."""

    @property
    def agent_name(self):
        return "classifier"

    @property
    def response_model(self):
        return ClassifyResponse


class TestBaseAgent:
    def test_get_provider(self):
        agent = ConcreteAgent()
        provider = agent.get_provider()
        assert provider is not None

    @pytest.mark.asyncio
    async def test_execute_success(self):
        agent = ConcreteAgent()

        mock_result = CLIResult(
            stdout='{"task_type": "development", "confidence": 0.9}',
            exit_code=0,
        )

        with patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=mock_result), \
             patch("src.agents.base_agent.build_prompt", return_value="test prompt"):
            result = await agent.execute(
                story={"id": "US-001"},
                phase="CLASSIFY",
                working_directory="/tmp",
            )

        assert isinstance(result, ClassifyResponse)
        assert result.task_type == "development"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_execute_retry_on_validation_failure(self):
        agent = ConcreteAgent()

        bad_result = CLIResult(stdout='{"invalid": "response"}', exit_code=0)
        good_result = CLIResult(
            stdout='{"task_type": "debug", "confidence": 0.7}',
            exit_code=0,
        )

        call_count = 0
        async def mock_invoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return bad_result
            return good_result

        with patch("src.agents.base_agent.cli_invoke", side_effect=mock_invoke), \
             patch("src.agents.base_agent.build_prompt", return_value="test prompt"):
            result = await agent.execute(
                story={"id": "US-001"},
                phase="CLASSIFY",
                working_directory="/tmp",
            )

        assert result.task_type == "debug"
        assert call_count == 2  # First attempt + retry

    @pytest.mark.asyncio
    async def test_execute_raises_after_double_failure(self):
        agent = ConcreteAgent()

        bad_result = CLIResult(stdout='not json at all', exit_code=0)

        with patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=bad_result), \
             patch("src.agents.base_agent.build_prompt", return_value="test prompt"):
            with pytest.raises(ValueError, match="Validation failed after retry"):
                await agent.execute(
                    story={"id": "US-001"},
                    phase="CLASSIFY",
                    working_directory="/tmp",
                )

    @pytest.mark.asyncio
    async def test_execute_raises_on_api_error(self):
        agent = ConcreteAgent()

        error_result = CLIResult(
            stdout="",
            stderr="API Error: 500",
            exit_code=1,
            is_api_error=True,
            api_error_code=500,
        )

        with patch("src.agents.base_agent.cli_invoke", new_callable=AsyncMock, return_value=error_result), \
             patch("src.agents.base_agent.build_prompt", return_value="test prompt"):
            with pytest.raises(RuntimeError, match="API error"):
                await agent.execute(
                    story={"id": "US-001"},
                    phase="CLASSIFY",
                    working_directory="/tmp",
                )
