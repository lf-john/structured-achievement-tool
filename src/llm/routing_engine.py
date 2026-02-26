"""
Complexity-Based LLM Routing Engine — The 4 Rules.

Selects the optimal LLM provider for each agent based on:
- Agent complexity rating (from the definitive plan)
- Model power ratings
- Preference: local → cheap cloud → expensive cloud

Config overrides via phase_models in config.json bypass these rules.
"""

import json
import os
import logging
import time
from typing import Optional, Tuple

from src.llm.providers import ProviderConfig, PROVIDERS, get_provider, is_provider_available

logger = logging.getLogger(__name__)


# Agent complexity ratings from 044_definitive_implementation_plan.md
AGENT_COMPLEXITY: dict[str, int] = {
    "design": 10,
    "architect": 10,
    "diagnoser": 10,
    "planner": 9,
    "verifier_arch": 9,
    "reproducer": 8,
    "plan": 7,
    "decomposer": 7,
    "reviewer": 7,
    "assessor": 6,
    "analyzer": 6,
    "mediator": 6,
    "coder": 6,          # Default; Decompose agent sets 5-8 per story
    "test_writer": 5,
    "synthesizer": 5,
    "reporter": 5,
    "validator": 5,
    "verifier_security": 4,
    "learner": 4,
    "executor": 4,
    "router": 4,
    "gatherer": 4,
    "verifier_lint": 3,
    "classifier": 3,
    "basic_info": 2,      # 1-3, Decompose decides
}

# Claude model names for Rule 1 identification
CLAUDE_MODELS = {"opus", "sonnet", "haiku"}

# Agents that require agentic providers (filesystem read/write capabilities).
# Ollama models are text-only and cannot be used for these agents.
AGENTIC_AGENTS = {
    "design", "architect", "planner", "coder", "test_writer",
    "executor", "reproducer", "verifier_arch", "verifier_security",
    "verifier_lint", "mediator",
}


class RoutingEngine:
    """Select the best LLM provider for an agent based on complexity rules."""

    # Cooldown period (seconds) after a 429 before retrying the same provider
    RATE_LIMIT_COOLDOWN = 120

    # Pause-all threshold: if this many distinct providers return 429 within
    # PAUSE_ALL_WINDOW seconds, all LLM calls are paused for PAUSE_ALL_DURATION.
    PAUSE_ALL_THRESHOLD = 2
    PAUSE_ALL_WINDOW = 60  # seconds
    PAUSE_ALL_DURATION = 120  # seconds

    def __init__(self, config_path: Optional[str] = None):
        self.config = {}
        self.phase_overrides = {}
        # Track rate-limited providers: {provider_name: timestamp_of_429}
        self._rate_limited: dict[str, float] = {}
        # Pause-all state
        self._paused_until: float = 0.0

        if config_path and os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.config = json.load(f)
            self.phase_overrides = self.config.get("phase_models", {})

    @property
    def is_paused(self) -> bool:
        """Return True if all LLM calls are paused due to rate limit cascade."""
        return time.monotonic() < self._paused_until

    def mark_rate_limited(self, provider_name: str):
        """Mark a provider as rate-limited. It will be deprioritized for RATE_LIMIT_COOLDOWN seconds.

        If multiple distinct providers hit 429 within PAUSE_ALL_WINDOW, triggers
        a global pause (Failure State 5: rate limit cascade).
        """
        now = time.monotonic()
        self._rate_limited[provider_name] = now
        logger.info(f"Provider {provider_name} marked rate-limited for {self.RATE_LIMIT_COOLDOWN}s")

        # Check for cascade: count providers that hit 429 within the window
        recent_count = sum(
            1 for ts in self._rate_limited.values()
            if now - ts < self.PAUSE_ALL_WINDOW
        )
        if recent_count >= self.PAUSE_ALL_THRESHOLD and not self.is_paused:
            self._paused_until = now + self.PAUSE_ALL_DURATION
            logger.warning(
                "Rate limit cascade: %d providers hit 429 within %ds. "
                "Pausing ALL LLM calls for %ds.",
                recent_count, self.PAUSE_ALL_WINDOW, self.PAUSE_ALL_DURATION,
            )

    def _is_rate_limited(self, provider_name: str) -> bool:
        """Check if a provider is currently in cooldown."""
        if provider_name not in self._rate_limited:
            return False
        elapsed = time.monotonic() - self._rate_limited[provider_name]
        if elapsed >= self.RATE_LIMIT_COOLDOWN:
            del self._rate_limited[provider_name]
            return False
        return True

    def get_complexity(self, agent_name: str, story_complexity: Optional[int] = None) -> int:
        """Get the complexity rating for an agent.

        For agents with variable complexity (coder, basic_info), use story_complexity.
        """
        if story_complexity is not None and agent_name in ("coder", "basic_info"):
            return story_complexity
        return AGENT_COMPLEXITY.get(agent_name, 5)

    def select(
        self,
        agent_name: str,
        story_complexity: Optional[int] = None,
        is_code_task: bool = False,
    ) -> ProviderConfig:
        """Select the best provider for an agent.

        Applies the 4 rules in order, then selects from eligible models
        preferring: local → cheap cloud → expensive cloud.

        Args:
            agent_name: Name of the agent (key in AGENT_COMPLEXITY)
            story_complexity: Override complexity for variable agents (coder, basic_info)
            is_code_task: If True, use code_power instead of power for comparison
        """
        # Pause-all gate (Failure State 5): wait out the cascade cooldown
        if self.is_paused:
            remaining = self._paused_until - time.monotonic()
            logger.warning(
                "LLM calls paused (rate limit cascade). %.0fs remaining. "
                "Returning fallback.", remaining,
            )
            default = self.config.get("default_primary", "sonnet")
            return get_provider(default)

        # Check config override first
        phase_key = agent_name.upper()
        if phase_key in self.phase_overrides:
            override_name = self.phase_overrides[phase_key]
            if override_name in PROVIDERS:
                logger.debug(f"Using config override for {agent_name}: {override_name}")
                return PROVIDERS[override_name]

        complexity = self.get_complexity(agent_name, story_complexity)

        # Complexity 1-2: Not LLM tasks
        if complexity <= 2:
            logger.debug(f"Agent {agent_name} complexity {complexity} <= 2: not an LLM task")
            return PROVIDERS["nemotron"]  # Fallback if caller insists

        eligible = []
        needs_agentic = agent_name in AGENTIC_AGENTS

        # Minimum adequate power: model must be within 1 level of the task complexity.
        # Without this, a power-6 model would be "eligible" for complexity-10 tasks
        # just because the cost rules allow it. The eligibility rules gate when
        # expensive models are ALLOWED; this gates when cheap models are ADEQUATE.
        min_adequate_power = max(complexity - 1, 1)

        for name, provider in PROVIDERS.items():
            power = provider.code_power if is_code_task else provider.power

            # Skip providers that aren't available (missing API keys, CLI tools)
            if not is_provider_available(provider):
                continue

            # Agentic phases require providers with filesystem access
            if needs_agentic and not provider.agentic:
                continue

            # Power adequacy check: model must be strong enough for the task
            if power < min_adequate_power:
                continue

            if provider.name in CLAUDE_MODELS:
                # Rule 1: Claude models eligible only when complexity >= power
                # (Don't waste expensive Claude on easy tasks)
                if complexity >= power:
                    eligible.append(provider)
            elif provider.local:
                # Rule 3: Local preferred when complexity <= 6 AND power >= complexity
                if complexity <= 6 and power >= complexity:
                    eligible.append(provider)
                # Rule 4: Nemotron preferred when complexity <= 3
                elif provider.name == "nemotron" and complexity <= 3:
                    eligible.append(provider)
            else:
                # Rule 2: Other commercial models eligible when complexity >= power - 2
                if complexity >= power - 2:
                    eligible.append(provider)

        if not eligible:
            # Fallback: use default from config
            default = self.config.get("default_primary", "sonnet")
            logger.warning(f"No eligible model for {agent_name} (complexity={complexity}), falling back to {default}")
            return get_provider(default)

        # Sort by preference: non-rate-limited first, local first, cheapest first, highest power first
        def sort_key(p: ProviderConfig):
            cost_order = {"free": 0, "minimal": 1, "low": 2, "medium": 3, "high": 4}
            power = p.code_power if is_code_task else p.power
            rate_limited = 1 if self._is_rate_limited(p.name) else 0
            return (
                rate_limited,                    # Non-rate-limited first
                0 if p.local else 1,             # Local first
                cost_order.get(p.cost_tier, 5),  # Cheapest first
                -power,                           # Highest power first (within same tier)
            )

        eligible.sort(key=sort_key)
        selected = eligible[0]
        if self._is_rate_limited(selected.name):
            logger.warning(f"All eligible providers rate-limited for {agent_name}, using {selected.name} anyway")
        else:
            logger.debug(f"Routing {agent_name} (complexity={complexity}) → {selected.name} (power={selected.power})")
        return selected

    def select_with_fallback(
        self,
        agent_name: str,
        story_complexity: Optional[int] = None,
        is_code_task: bool = False,
    ) -> Tuple[ProviderConfig, ProviderConfig]:
        """Select primary + fallback provider.

        Uses routing_preferences from config to select appropriate backups:
        - reasoning_backup for high-complexity agents (7+)
        - code_backup for code-producing agents
        - classification_backup for low-complexity agents (<=3)
        - default_backup as final fallback
        """
        primary = self.select(agent_name, story_complexity, is_code_task)
        complexity = self.get_complexity(agent_name, story_complexity)
        prefs = self.config.get("routing_preferences", {})

        # Select appropriate backup based on task characteristics
        if complexity >= 7:
            fallback_name = prefs.get("reasoning_backup", self.config.get("default_backup", "deepseek_r1"))
        elif is_code_task or agent_name in ("coder", "test_writer", "executor"):
            fallback_name = prefs.get("code_backup", self.config.get("default_backup", "qwen25_coder"))
        elif complexity <= 3:
            fallback_name = prefs.get("classification_backup", self.config.get("default_backup", "nemotron"))
        else:
            fallback_name = self.config.get("default_backup", "deepseek_r1")

        fallback = get_provider(fallback_name)

        # If primary and fallback are the same, try to find an alternative
        if primary.name == fallback.name:
            fallback = get_provider(self.config.get("default_primary", "sonnet"))

        return primary, fallback

    def select_all(
        self,
        agent_name: str,
        story_complexity: Optional[int] = None,
        is_code_task: bool = False,
    ) -> list[ProviderConfig]:
        """Return all eligible providers in priority order (best first).

        Same eligibility rules as select(), but returns the full sorted list
        so callers can cascade through providers on failure.
        """
        # Check config override first — if set, that's the only option
        phase_key = agent_name.upper()
        if phase_key in self.phase_overrides:
            override_name = self.phase_overrides[phase_key]
            if override_name in PROVIDERS:
                return [PROVIDERS[override_name]]

        complexity = self.get_complexity(agent_name, story_complexity)

        if complexity <= 2:
            return [PROVIDERS["nemotron"]]

        eligible = []
        needs_agentic = agent_name in AGENTIC_AGENTS

        min_adequate_power = max(complexity - 1, 1)

        for name, provider in PROVIDERS.items():
            power = provider.code_power if is_code_task else provider.power

            if not is_provider_available(provider):
                continue
            if needs_agentic and not provider.agentic:
                continue
            if power < min_adequate_power:
                continue

            if provider.name in CLAUDE_MODELS:
                if complexity >= power:
                    eligible.append(provider)
            elif provider.local:
                if complexity <= 6 and power >= complexity:
                    eligible.append(provider)
                elif provider.name == "nemotron" and complexity <= 3:
                    eligible.append(provider)
            else:
                if complexity >= power - 2:
                    eligible.append(provider)

        if not eligible:
            default = self.config.get("default_primary", "sonnet")
            return [get_provider(default)]

        def sort_key(p: ProviderConfig):
            cost_order = {"free": 0, "minimal": 1, "low": 2, "medium": 3, "high": 4}
            power = p.code_power if is_code_task else p.power
            rate_limited = 1 if self._is_rate_limited(p.name) else 0
            return (
                rate_limited,
                0 if p.local else 1,
                cost_order.get(p.cost_tier, 5),
                -power,
            )

        eligible.sort(key=sort_key)
        return eligible
