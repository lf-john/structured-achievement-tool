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
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.llm.cli_runner import CLIResult
from src.llm.cli_runner import invoke as cli_invoke
from src.llm.prompt_builder import build_prompt
from src.llm.providers import ProviderConfig
from src.llm.response_parser import extract_json, validate_response
from src.llm.routing_engine import RoutingEngine

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
        routing_engine: RoutingEngine | None = None,
        config_path: str | None = None,
    ):
        self.routing_engine = routing_engine or RoutingEngine(config_path)

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Agent name matching AGENT_COMPLEXITY keys (e.g., 'classifier', 'mediator')."""
        ...

    @property
    @abstractmethod
    def response_model(self) -> type[BaseModel]:
        """Pydantic model class for validating the response."""
        ...

    def get_provider(
        self,
        story_complexity: int | None = None,
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
        story_complexity: int | None = None,
        is_code_task: bool = False,
        template_dir: str | None = None,
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
                    f"{self.agent_name}: Validation failed after retry. First: {first_error}. Second: {second_error}"
                )

    async def _invoke(
        self,
        provider: ProviderConfig,
        prompt: str,
        working_directory: str,
    ) -> CLIResult:
        """Invoke the LLM via CLI with full provider cascade on 429.

        On rate limit (429), marks the provider, waits with exponential backoff,
        and tries the next eligible provider. Cascades through all available
        providers before giving up.
        """
        providers = self.routing_engine.select_all(self.agent_name)
        # Ensure the initially-selected provider is tried first
        if provider.name not in [p.name for p in providers]:
            providers.insert(0, provider)

        backoff = 5  # Initial backoff in seconds
        tried = set()

        for candidate in providers:
            if candidate.name in tried:
                continue
            tried.add(candidate.name)

            if candidate.name != provider.name:
                logger.info(f"{self.agent_name}: trying {candidate.name}")

            result = await self._invoke_raw(candidate, prompt, working_directory)

            if result.is_api_error and result.api_error_code == 429:
                self.routing_engine.mark_rate_limited(candidate.name)
                logger.warning(
                    f"{self.agent_name}: {candidate.name} rate-limited (429), backoff {backoff}s before next provider"
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 120)
                continue

            # Non-429 result (success or other error) — return it
            if result.is_api_error:
                raise RuntimeError(
                    f"API error from {candidate.name}: code={result.api_error_code}, stderr={result.stderr[:500]}"
                )

            if result.is_environmental:
                raise RuntimeError(f"Environmental error from {candidate.name}: {result.stderr[:500]}")

            if result.exit_code != 0 and not result.stdout.strip():
                raise RuntimeError(
                    f"CLI failed for {candidate.name}: exit_code={result.exit_code}, stderr={result.stderr[:500]}"
                )

            return result

        # All providers exhausted — raise with last result info
        raise RuntimeError(
            f"All providers rate-limited for {self.agent_name}. Tried: {', '.join(tried)}. Last error: 429"
        )

    async def _invoke_raw(
        self,
        provider: ProviderConfig,
        prompt: str,
        working_directory: str,
    ) -> CLIResult:
        """Raw CLI invocation in non-agentic mode (prompt-response only).

        Agents are used for classify/decompose — simple text-in/JSON-out.
        No tool access needed, so agentic=False avoids burning API calls.
        """
        if len(prompt) > 10_000:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, dir=working_directory) as f:
                f.write(prompt)
                prompt_file = f.name

            try:
                return await cli_invoke(
                    provider=provider,
                    prompt_file=prompt_file,
                    working_directory=working_directory,
                    agentic=False,
                )
            finally:
                os.unlink(prompt_file)
        else:
            return await cli_invoke(
                provider=provider,
                prompt=prompt,
                working_directory=working_directory,
                agentic=False,
            )

    def _parse_and_validate(self, text: str) -> BaseModel:
        """Extract JSON and validate against the response model."""
        data = extract_json(text)
        return validate_response(data, self.response_model)
