"""
Multiple LLM Invoker — Higher-level task execution with failover and health tracking.

Phase 2 item 2.13: Extends Ollama models from embeddings-only to being usable as
task executors for low-complexity tasks.

Wraps the routing engine + CLI runner and adds:
- execute_with_provider() — invoke a prompt against a specific provider
- execute_with_routing() — let the routing engine pick, with automatic failover
- execute_local_first() — try local Ollama first, fall back to cloud
- Provider health tracking (mark unhealthy after N consecutive failures, auto-recover)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from src.llm.providers import ProviderConfig, get_provider, list_providers
from src.llm.cli_runner import CLIResult, invoke
from src.llm.routing_engine import RoutingEngine

logger = logging.getLogger(__name__)

# Health tracking defaults
DEFAULT_FAILURE_THRESHOLD = 3  # Mark unhealthy after this many consecutive failures
DEFAULT_COOLDOWN_SECONDS = 300  # 5 minutes before auto-recovery attempt


@dataclass
class ProviderHealth:
    """In-memory health state for a single provider."""
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    total_invocations: int = 0
    total_failures: int = 0
    is_healthy: bool = True


@dataclass
class InvocationResult:
    """Result of a multi-invoker execution, wrapping CLIResult with metadata."""
    cli_result: CLIResult
    provider_name: str
    was_failover: bool = False
    failover_from: Optional[str] = None
    attempts: int = 1

    @property
    def success(self) -> bool:
        return (
            self.cli_result.exit_code == 0
            and not self.cli_result.is_api_error
            and not self.cli_result.is_environmental
        )

    @property
    def stdout(self) -> str:
        return self.cli_result.stdout

    @property
    def stderr(self) -> str:
        return self.cli_result.stderr


class MultiInvoker:
    """Execute LLM tasks across providers with failover and health tracking.

    Uses the existing RoutingEngine for provider selection and cli_runner.invoke()
    for all actual LLM calls. This is a thin orchestration wrapper, not a new
    routing system.
    """

    def __init__(
        self,
        routing_engine: Optional[RoutingEngine] = None,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    ):
        self.routing_engine = routing_engine or RoutingEngine()
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._health: dict[str, ProviderHealth] = {}

    def _get_health(self, provider_name: str) -> ProviderHealth:
        """Get or create health state for a provider."""
        if provider_name not in self._health:
            self._health[provider_name] = ProviderHealth()
        return self._health[provider_name]

    def is_provider_healthy(self, provider_name: str) -> bool:
        """Check if a provider is considered healthy.

        Unhealthy providers auto-recover after the cooldown period.
        """
        health = self._get_health(provider_name)
        if health.is_healthy:
            return True

        # Auto-recover after cooldown
        elapsed = time.monotonic() - health.last_failure_time
        if elapsed >= self.cooldown_seconds:
            logger.info(
                f"Provider {provider_name} auto-recovered after "
                f"{elapsed:.0f}s cooldown"
            )
            health.is_healthy = True
            health.consecutive_failures = 0
            return True

        return False

    def _record_success(self, provider_name: str):
        """Record a successful invocation."""
        health = self._get_health(provider_name)
        health.consecutive_failures = 0
        health.last_success_time = time.monotonic()
        health.total_invocations += 1
        health.is_healthy = True

    def _record_failure(self, provider_name: str):
        """Record a failed invocation. May mark provider unhealthy."""
        health = self._get_health(provider_name)
        health.consecutive_failures += 1
        health.last_failure_time = time.monotonic()
        health.total_invocations += 1
        health.total_failures += 1

        if health.consecutive_failures >= self.failure_threshold:
            health.is_healthy = False
            logger.warning(
                f"Provider {provider_name} marked unhealthy after "
                f"{health.consecutive_failures} consecutive failures"
            )

    def get_health_summary(self) -> dict[str, dict]:
        """Return health summary for all tracked providers."""
        summary = {}
        for name, health in self._health.items():
            summary[name] = {
                "healthy": self.is_provider_healthy(name),
                "consecutive_failures": health.consecutive_failures,
                "total_invocations": health.total_invocations,
                "total_failures": health.total_failures,
            }
        return summary

    def _is_result_failure(self, result: CLIResult) -> bool:
        """Determine if a CLIResult represents a failure."""
        return (
            result.exit_code != 0
            or result.is_api_error
            or result.is_environmental
        )

    async def execute_with_provider(
        self,
        provider_name: str,
        prompt: str,
        working_directory: Optional[str] = None,
        timeout: int = 600,
    ) -> InvocationResult:
        """Invoke a prompt against a specific provider.

        Args:
            provider_name: Name of the provider (key in PROVIDERS registry)
            prompt: The prompt text to send
            working_directory: CWD for the subprocess
            timeout: Timeout in seconds

        Returns:
            InvocationResult with the CLI result and metadata
        """
        provider = get_provider(provider_name)

        cli_result = await invoke(
            provider=provider,
            prompt=prompt,
            working_directory=working_directory,
            timeout=timeout,
        )

        if self._is_result_failure(cli_result):
            self._record_failure(provider_name)
        else:
            self._record_success(provider_name)

        return InvocationResult(
            cli_result=cli_result,
            provider_name=provider_name,
        )

    async def execute_with_routing(
        self,
        agent_name: str,
        prompt: str,
        story_complexity: Optional[int] = None,
        is_code_task: bool = False,
        working_directory: Optional[str] = None,
        timeout: int = 600,
        max_attempts: int = 2,
    ) -> InvocationResult:
        """Let the routing engine pick a provider, with automatic failover.

        Uses RoutingEngine.select_with_fallback() to get primary and fallback
        providers. If the primary fails, automatically retries with the fallback.

        Skips providers marked unhealthy (unless no healthy alternatives exist).

        Args:
            agent_name: Agent name for routing (key in AGENT_COMPLEXITY)
            prompt: The prompt text to send
            story_complexity: Override complexity for variable agents
            is_code_task: If True, use code_power for routing
            working_directory: CWD for the subprocess
            timeout: Timeout in seconds
            max_attempts: Maximum number of providers to try (default 2)

        Returns:
            InvocationResult, potentially with failover metadata
        """
        primary, fallback = self.routing_engine.select_with_fallback(
            agent_name=agent_name,
            story_complexity=story_complexity,
            is_code_task=is_code_task,
        )

        # Build ordered candidate list: primary, then fallback
        candidates = [primary]
        if fallback.name != primary.name:
            candidates.append(fallback)

        # Prefer healthy providers but don't exclude all if none are healthy
        healthy_candidates = [
            c for c in candidates if self.is_provider_healthy(c.name)
        ]
        if healthy_candidates:
            candidates = healthy_candidates + [
                c for c in candidates if c not in healthy_candidates
            ]

        first_provider_name = None
        attempts = 0

        for provider in candidates[:max_attempts]:
            attempts += 1

            cli_result = await invoke(
                provider=provider,
                prompt=prompt,
                working_directory=working_directory,
                timeout=timeout,
            )

            if first_provider_name is None:
                first_provider_name = provider.name

            if not self._is_result_failure(cli_result):
                self._record_success(provider.name)
                return InvocationResult(
                    cli_result=cli_result,
                    provider_name=provider.name,
                    was_failover=(provider.name != first_provider_name),
                    failover_from=first_provider_name if provider.name != first_provider_name else None,
                    attempts=attempts,
                )

            # Record failure and try next
            self._record_failure(provider.name)
            logger.warning(
                f"Provider {provider.name} failed for {agent_name}, "
                f"trying next candidate"
            )

        # All candidates exhausted — return last result
        return InvocationResult(
            cli_result=cli_result,
            provider_name=provider.name,
            was_failover=(provider.name != first_provider_name),
            failover_from=first_provider_name if provider.name != first_provider_name else None,
            attempts=attempts,
        )

    async def execute_local_first(
        self,
        prompt: str,
        working_directory: Optional[str] = None,
        timeout: int = 600,
        preferred_local: Optional[str] = None,
        cloud_fallback: str = "gemini_flash",
    ) -> InvocationResult:
        """Try local Ollama first, fall back to cloud only if local fails.

        Ideal for low-complexity tasks where cost savings matter.

        Args:
            prompt: The prompt text to send
            working_directory: CWD for the subprocess
            timeout: Timeout in seconds
            preferred_local: Specific local model name (default: best healthy local)
            cloud_fallback: Cloud provider to fall back to (default: gemini_flash)

        Returns:
            InvocationResult, potentially with failover metadata
        """
        # Select local provider
        if preferred_local:
            local_provider = get_provider(preferred_local)
        else:
            local_provider = self._select_best_healthy_local()

        if local_provider is None:
            # No local providers available at all — go straight to cloud
            logger.warning("No local providers available, going directly to cloud")
            result = await self.execute_with_provider(
                provider_name=cloud_fallback,
                prompt=prompt,
                working_directory=working_directory,
                timeout=timeout,
            )
            result.was_failover = True
            result.failover_from = "local"
            return result

        # Try local first
        cli_result = await invoke(
            provider=local_provider,
            prompt=prompt,
            working_directory=working_directory,
            timeout=timeout,
        )

        if not self._is_result_failure(cli_result):
            self._record_success(local_provider.name)
            return InvocationResult(
                cli_result=cli_result,
                provider_name=local_provider.name,
            )

        # Local failed — record and fall back to cloud
        self._record_failure(local_provider.name)
        logger.info(
            f"Local provider {local_provider.name} failed, "
            f"falling back to cloud ({cloud_fallback})"
        )

        cloud_result = await self.execute_with_provider(
            provider_name=cloud_fallback,
            prompt=prompt,
            working_directory=working_directory,
            timeout=timeout,
        )

        return InvocationResult(
            cli_result=cloud_result.cli_result,
            provider_name=cloud_fallback,
            was_failover=True,
            failover_from=local_provider.name,
            attempts=2,
        )

    def _select_best_healthy_local(self) -> Optional[ProviderConfig]:
        """Select the best healthy local provider by power rating."""
        local_providers = list_providers(local_only=True)

        # Filter to healthy providers
        healthy = [
            p for p in local_providers
            if self.is_provider_healthy(p.name)
        ]

        if not healthy:
            # All unhealthy — return highest-power local anyway (let caller decide)
            if local_providers:
                local_providers.sort(key=lambda p: -p.power)
                return local_providers[0]
            return None

        # Sort by power descending
        healthy.sort(key=lambda p: -p.power)
        return healthy[0]

    def reset_health(self, provider_name: Optional[str] = None):
        """Reset health state for a provider or all providers.

        Args:
            provider_name: If provided, reset only this provider. Otherwise reset all.
        """
        if provider_name:
            if provider_name in self._health:
                self._health[provider_name] = ProviderHealth()
        else:
            self._health.clear()
