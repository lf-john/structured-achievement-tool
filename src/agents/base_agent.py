"""
Base Agent — Abstract base for all LLM-powered agents.

Pipeline: route → build prompt → invoke CLI → parse JSON → validate with Pydantic.
Auto-retries on JSON validation failure (once, with error feedback).
Implements hallucination reduction via constrained output + claim verification.
"""

import asyncio
import logging
import os
import tempfile
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional

from pydantic import BaseModel, ValidationError

from src.llm.providers import ProviderConfig
from src.llm.routing_engine import RoutingEngine
from src.llm.cli_runner import invoke as cli_invoke, CLIResult
from src.llm.prompt_builder import build_prompt
from src.llm.response_parser import extract_json, validate_response

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC):
    """Abstract base class for LLM agents.

    Subclasses must implement:
    - agent_name: property returning the agent's name (for routing)
    - response_model: property returning the Pydantic model for validation
    """

    def __init__(
        self,
        routing_engine: Optional[RoutingEngine] = None,
        config_path: Optional[str] = None,
    ):
        self.routing_engine = routing_engine or RoutingEngine(config_path)

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Agent name matching AGENT_COMPLEXITY keys (e.g., 'classifier', 'mediator')."""
        ...

    @property
    @abstractmethod
    def response_model(self) -> Type[BaseModel]:
        """Pydantic model class for validating the response."""
        ...

    def get_provider(
        self,
        story_complexity: Optional[int] = None,
        is_code_task: bool = False,
    ) -> ProviderConfig:
        """Get the routed provider for this agent."""
        return self.routing_engine.select(
            self.agent_name,
            story_complexity=story_complexity,
            is_code_task=is_code_task,
        )

    async def execute(
        self,
        story: dict,
        phase: str,
        working_directory: str,
        context: dict = None,
        story_complexity: Optional[int] = None,
        is_code_task: bool = False,
        template_dir: Optional[str] = None,
    ) -> BaseModel:
        """Execute the agent: route → prompt → invoke → parse → validate.

        On validation failure, retries once with the error message appended.

        Args:
            story: Story dict
            phase: Phase name for prompt building
            working_directory: Project working directory
            context: Additional context dict
            story_complexity: Override for variable-complexity agents
            is_code_task: Use code_power for routing
            template_dir: Override template directory

        Returns:
            Validated Pydantic model instance

        Raises:
            ValueError: If both attempts fail validation
            RuntimeError: If CLI invocation fails
        """
        provider = self.get_provider(story_complexity, is_code_task)

        # Build prompt
        prompt = build_prompt(
            story=story,
            phase=phase,
            working_directory=working_directory,
            context=context,
            template_dir=template_dir,
        )

        # First attempt
        result = await self._invoke(provider, prompt, working_directory)

        try:
            return self._parse_and_validate(result.stdout)
        except (ValueError, ValidationError) as first_error:
            logger.warning(f"{self.agent_name}: First attempt validation failed: {first_error}")

            # Retry with error feedback
            retry_prompt = (
                f"{prompt}\n\n"
                f"## IMPORTANT: Your previous response was invalid.\n"
                f"Error: {first_error}\n"
                f"Please output ONLY valid JSON matching the required schema."
            )

            retry_result = await self._invoke(provider, retry_prompt, working_directory)

            try:
                return self._parse_and_validate(retry_result.stdout)
            except (ValueError, ValidationError) as second_error:
                raise ValueError(
                    f"{self.agent_name}: Validation failed after retry. "
                    f"First: {first_error}. Second: {second_error}"
                )

    async def _invoke(
        self,
        provider: ProviderConfig,
        prompt: str,
        working_directory: str,
    ) -> CLIResult:
        """Invoke the LLM via CLI.

        For large prompts, writes to a temp file to avoid shell argument limits.
        """
        # Use temp file for prompts > 10KB (shell arg limits)
        if len(prompt) > 10_000:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, dir=working_directory
            ) as f:
                f.write(prompt)
                prompt_file = f.name

            try:
                result = await cli_invoke(
                    provider=provider,
                    prompt_file=prompt_file,
                    working_directory=working_directory,
                )
            finally:
                os.unlink(prompt_file)
        else:
            result = await cli_invoke(
                provider=provider,
                prompt=prompt,
                working_directory=working_directory,
            )

        if result.is_api_error:
            raise RuntimeError(
                f"API error from {provider.name}: code={result.api_error_code}, "
                f"stderr={result.stderr[:500]}"
            )

        if result.is_environmental:
            raise RuntimeError(
                f"Environmental error from {provider.name}: {result.stderr[:500]}"
            )

        if result.exit_code != 0 and not result.stdout.strip():
            raise RuntimeError(
                f"CLI failed for {provider.name}: exit_code={result.exit_code}, "
                f"stderr={result.stderr[:500]}"
            )

        return result

    def _parse_and_validate(self, text: str) -> BaseModel:
        """Extract JSON and validate against the response model."""
        data = extract_json(text)
        return validate_response(data, self.response_model)
