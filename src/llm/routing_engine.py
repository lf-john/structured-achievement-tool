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


class RoutingEngine:
    """Select the best LLM provider for an agent based on complexity rules."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = {}
        self.phase_overrides = {}

        if config_path and os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.config = json.load(f)
            self.phase_overrides = self.config.get("phase_models", {})

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

            # Power adequacy check: model must be strong enough for the task
            if power < min_adequate_power:
                continue

            if provider.name in CLAUDE_MODELS:
                # Rule 1: Claude models eligible only when complexity >= power
                # (Don't waste expensive Claude on easy tasks)
                if complexity >= power:
                    eligible.append(provider)
            elif provider.local:
                # Rule 3: Local preferred when complexity <= 6 AND power > complexity
                if complexity <= 6 and power > complexity:
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

        # Sort by preference: local first, then by cost (cheapest first), then by power (highest first)
        def sort_key(p: ProviderConfig):
            cost_order = {"free": 0, "minimal": 1, "low": 2, "medium": 3, "high": 4}
            power = p.code_power if is_code_task else p.power
            return (
                0 if p.local else 1,           # Local first
                cost_order.get(p.cost_tier, 5), # Cheapest first
                -power,                          # Highest power first (within same tier)
            )

        eligible.sort(key=sort_key)
        selected = eligible[0]
        logger.debug(f"Routing {agent_name} (complexity={complexity}) → {selected.name} (power={selected.power})")
        return selected

    def select_with_fallback(
        self,
        agent_name: str,
        story_complexity: Optional[int] = None,
        is_code_task: bool = False,
    ) -> Tuple[ProviderConfig, ProviderConfig]:
        """Select primary + fallback provider."""
        primary = self.select(agent_name, story_complexity, is_code_task)

        # Fallback: next best eligible that isn't the primary
        fallback_name = self.config.get("default_backup", "glm5")
        fallback = get_provider(fallback_name)

        # If primary and fallback are the same, try to find an alternative
        if primary.name == fallback.name:
            fallback = get_provider(self.config.get("default_primary", "sonnet"))

        return primary, fallback
