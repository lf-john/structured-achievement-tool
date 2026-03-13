"""
Complexity-Based LLM Routing Engine — The 4 Rules.

Selects the optimal LLM provider for each agent based on:
- Agent complexity rating (from the definitive plan)
- Model power ratings
- Preference: local → cheap cloud → expensive cloud

Config overrides via phase_models in config.json bypass these rules.
"""

import json
import logging
import os
import subprocess
import time

from src.llm.providers import PROVIDERS, ProviderConfig, get_provider, is_provider_available

logger = logging.getLogger(__name__)


# Error categories for circuit breaker classification
class ErrorCategory:
    RATE_LIMIT = "rate_limit"  # 429 — existing handling
    TIMEOUT = "timeout"  # Process timeout
    SERVER_ERROR = "server_error"  # 500, 502, 503
    AUTH_ERROR = "auth_error"  # 401, 403
    CONNECTION = "connection"  # Connection refused, DNS failure
    UNKNOWN = "unknown"


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
    "coder": 6,  # Default; Decompose agent sets 5-8 per story
    "test_writer": 5,
    "synthesizer": 5,
    "reporter": 5,
    "validator": 5,
    "verifier_security": 4,
    "learner": 4,
    "executor": 4,
    "router": 4,
    "gatherer": 4,
    "critic": 7,
    "content_planner": 7,
    "content_writer": 6,
    "content_reviewer": 6,
    "verifier_lint": 3,
    "classifier": 3,
    "basic_info": 2,  # 1-3, Decompose decides
}

# Claude model names for Rule 1 identification
CLAUDE_MODELS = {"opus", "sonnet", "haiku"}

# Agents that require agentic providers (filesystem read/write capabilities).
# Ollama models are text-only and cannot be used for these agents.
AGENTIC_AGENTS = {
    "design",
    "architect",
    "planner",
    "coder",
    "test_writer",
    "executor",
    "reproducer",
    "verifier_arch",
    "verifier_security",
    "verifier_lint",
    "mediator",
}


class RoutingEngine:
    """Select the best LLM provider for an agent based on complexity rules."""

    # Cooldown period (seconds) after a 429 before attempting a health probe.
    # After cooldown expires, a single probe request is sent before fully resuming.
    RATE_LIMIT_COOLDOWN = 300  # 5 minutes

    # Gemini-specific cascade: ordered list of Gemini providers to try.
    # When one hits 429, try the next. If ALL hit 429, cooldown for 30 min.
    GEMINI_CASCADE = ["gemini_flash", "gemini_25_flash", "gemini_31_pro", "gemini_pro"]
    GEMINI_CASCADE_COOLDOWN = 1800  # 30 minutes when all Gemini models exhausted

    # Pause-all threshold: if this many distinct NON-GEMINI providers return 429
    # within PAUSE_ALL_WINDOW seconds, all LLM calls are paused.
    PAUSE_ALL_THRESHOLD = 2
    PAUSE_ALL_WINDOW = 60  # seconds
    PAUSE_ALL_DURATION = 120  # seconds

    # Circuit breaker cooldowns by provider class and error category
    CIRCUIT_BREAKER_THRESHOLD = 3  # Failures before circuit opens
    OLLAMA_CIRCUIT_COOLDOWN = 60  # 1 minute (Ollama restarts fast)
    CLOUD_CIRCUIT_COOLDOWN = 300  # 5 minutes
    AUTH_CIRCUIT_COOLDOWN = 1800  # 30 minutes (key probably revoked)

    def __init__(self, config_path: str | None = None):
        self.config = {}
        self.phase_overrides = {}
        # Track rate-limited providers: {provider_name: timestamp_of_429}
        self._rate_limited: dict[str, float] = {}
        # Providers awaiting health probe: cooldown expired but not yet confirmed healthy
        self._probe_pending: set[str] = set()
        # Pause-all state
        self._paused_until: float = 0.0
        # Generalized circuit breaker state
        # {provider_name: {"failures": int, "opened_at": float, "cooldown": float, "last_error": str}}
        self._circuit_state: dict[str, dict] = {}

        if config_path and os.path.exists(config_path):
            with open(config_path) as f:
                self.config = json.load(f)
            self.phase_overrides = self.config.get("phase_models", {})

    @property
    def is_paused(self) -> bool:
        """Return True if all LLM calls are paused due to rate limit cascade."""
        return time.monotonic() < self._paused_until

    def _is_gemini(self, provider_name: str) -> bool:
        """Check if a provider is a Gemini model."""
        return provider_name in self.GEMINI_CASCADE

    def _all_gemini_rate_limited(self) -> bool:
        """Check if all Gemini cascade providers are currently rate-limited."""
        now = time.monotonic()
        for name in self.GEMINI_CASCADE:
            if name not in self._rate_limited:
                return False
            if now - self._rate_limited[name] >= self.RATE_LIMIT_COOLDOWN:
                return False
        return True

    def mark_rate_limited(self, provider_name: str):
        """Mark a provider as rate-limited.

        Gemini cascade: when a Gemini provider hits 429, it gets a normal cooldown
        so the next Gemini provider in the cascade is tried. If ALL Gemini providers
        are rate-limited, all get a 30-minute cooldown.

        Non-Gemini: if enough non-Gemini providers hit 429 within PAUSE_ALL_WINDOW,
        triggers a global pause.
        """
        now = time.monotonic()
        self._rate_limited[provider_name] = now
        logger.info(f"Provider {provider_name} marked rate-limited for {self.RATE_LIMIT_COOLDOWN}s")

        # Gemini-specific cascade logic
        if self._is_gemini(provider_name):
            if self._all_gemini_rate_limited():
                # All 4 Gemini models exhausted — 30 min cooldown on all
                for name in self.GEMINI_CASCADE:
                    self._rate_limited[name] = now
                logger.warning(
                    "All Gemini models rate-limited. Putting ALL Gemini on %ds cooldown.",
                    self.GEMINI_CASCADE_COOLDOWN,
                )
            return  # Don't trigger pause-all for Gemini 429s

        # Non-Gemini cascade check
        recent_count = sum(
            1
            for name, ts in self._rate_limited.items()
            if now - ts < self.PAUSE_ALL_WINDOW and not self._is_gemini(name)
        )
        if recent_count >= self.PAUSE_ALL_THRESHOLD and not self.is_paused:
            self._paused_until = now + self.PAUSE_ALL_DURATION
            logger.warning(
                "Rate limit cascade: %d non-Gemini providers hit 429 within %ds. Pausing ALL LLM calls for %ds.",
                recent_count,
                self.PAUSE_ALL_WINDOW,
                self.PAUSE_ALL_DURATION,
            )

    def _is_rate_limited(self, provider_name: str) -> bool:
        """Check if a provider is currently in cooldown.

        Uses GEMINI_CASCADE_COOLDOWN for Gemini providers when all Gemini models
        are rate-limited, otherwise uses RATE_LIMIT_COOLDOWN.

        When cooldown expires, the provider enters "probe pending" state rather
        than being immediately available. Call mark_probe_success() after a
        successful request to fully clear the rate limit.
        """
        if provider_name not in self._rate_limited:
            return provider_name in self._probe_pending
        elapsed = time.monotonic() - self._rate_limited[provider_name]
        # Use longer cooldown when all Gemini models are exhausted
        if self._is_gemini(provider_name) and self._all_gemini_rate_limited():
            cooldown = self.GEMINI_CASCADE_COOLDOWN
        else:
            cooldown = self.RATE_LIMIT_COOLDOWN
        if elapsed >= cooldown:
            # Cooldown expired — move to probe-pending state
            del self._rate_limited[provider_name]
            self._probe_pending.add(provider_name)
            logger.info(f"Provider {provider_name} cooldown expired, awaiting health probe")
            return False  # Allow one request through as a probe
        return True

    def is_probe_pending(self, provider_name: str) -> bool:
        """Check if a provider is in probe-pending state (cooldown expired, not yet confirmed)."""
        return provider_name in self._probe_pending

    def mark_probe_success(self, provider_name: str):
        """Mark a provider's health probe as successful — fully resume traffic."""
        self._probe_pending.discard(provider_name)
        logger.info(f"Provider {provider_name} health probe succeeded, fully resumed")

    def mark_probe_failure(self, provider_name: str):
        """Mark a provider's health probe as failed — re-enter cooldown."""
        self._probe_pending.discard(provider_name)
        self._rate_limited[provider_name] = time.monotonic()
        logger.warning(
            f"Provider {provider_name} health probe failed, re-entering {self.RATE_LIMIT_COOLDOWN}s cooldown"
        )

    # --- Generalized Circuit Breaker (Enhancement #1 + #8) ---

    def mark_failure(self, provider_name: str, error_category: str = ErrorCategory.UNKNOWN):
        """Record a non-429 failure for a provider.

        After CIRCUIT_BREAKER_THRESHOLD consecutive failures, the provider
        enters "open circuit" state with a cooldown based on provider class
        and error category. For Ollama, attempts a restart before opening.
        """
        state = self._circuit_state.setdefault(
            provider_name,
            {
                "failures": 0,
                "opened_at": 0.0,
                "cooldown": 0.0,
                "last_error": "",
            },
        )
        state["failures"] += 1
        state["last_error"] = error_category

        if state["failures"] < self.CIRCUIT_BREAKER_THRESHOLD:
            logger.info(
                f"Provider {provider_name} failure {state['failures']}/{self.CIRCUIT_BREAKER_THRESHOLD} "
                f"(category={error_category})"
            )
            return

        # Threshold reached — determine cooldown by provider class + error type
        provider = PROVIDERS.get(provider_name)
        if provider and provider.local:
            # Ollama: attempt restart before opening circuit
            if self._attempt_ollama_restart():
                state["failures"] = 0
                logger.info(f"Ollama restarted successfully, resetting circuit for {provider_name}")
                return
            cooldown = self.OLLAMA_CIRCUIT_COOLDOWN
        elif error_category == ErrorCategory.AUTH_ERROR:
            cooldown = self.AUTH_CIRCUIT_COOLDOWN
        else:
            cooldown = self.CLOUD_CIRCUIT_COOLDOWN

        state["opened_at"] = time.monotonic()
        state["cooldown"] = cooldown
        logger.warning(
            f"Circuit breaker OPEN for {provider_name}: {state['failures']} failures "
            f"(category={error_category}), cooldown={cooldown}s"
        )

    def mark_success(self, provider_name: str):
        """Record a successful invocation — reset failure counter."""
        if provider_name in self._circuit_state:
            self._circuit_state[provider_name]["failures"] = 0
            self._circuit_state[provider_name]["opened_at"] = 0.0
        # Also clear probe pending if applicable
        self._probe_pending.discard(provider_name)

    def is_circuit_open(self, provider_name: str) -> bool:
        """Check if a provider's circuit breaker is open (should not be called)."""
        state = self._circuit_state.get(provider_name)
        if not state or state["opened_at"] == 0.0:
            return False
        elapsed = time.monotonic() - state["opened_at"]
        if elapsed >= state["cooldown"]:
            # Cooldown expired — enter half-open (allow one probe)
            state["opened_at"] = 0.0
            state["failures"] = 0
            self._probe_pending.add(provider_name)
            logger.info(f"Circuit breaker for {provider_name} cooldown expired, entering half-open")
            return False
        return True

    def _attempt_ollama_restart(self) -> bool:
        """Attempt to restart Ollama service. Returns True if restart succeeded."""
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "ollama"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("Ollama service restarted via circuit breaker")
                return True
            logger.warning(f"Ollama restart failed: {result.stderr}")
        except Exception as e:
            logger.warning(f"Ollama restart attempt failed: {e}")
        return False

    # --- Failure Escalation (Enhancement #9) ---

    def select_with_escalation(
        self,
        agent_name: str,
        attempt_number: int = 1,
        failure_is_persistent: bool = False,
        story_complexity: int | None = None,
        is_code_task: bool = False,
    ) -> ProviderConfig:
        """Select provider with automatic escalation on persistent failures.

        Only escalates for persistent (quality) failures, not transient
        (infrastructure) failures. Transient failures need circuit breaking,
        not a more powerful model.

        Escalation: +1 complexity per 2 persistent failures, capped at +3.
        """
        if failure_is_persistent and attempt_number > 1:
            escalation = min((attempt_number - 1) // 2, 3)
        else:
            escalation = 0

        effective_complexity = story_complexity
        if effective_complexity is not None and escalation > 0:
            effective_complexity = min(effective_complexity + escalation, 10)
            logger.info(
                f"Escalating {agent_name}: attempt={attempt_number}, "
                f"complexity {story_complexity} → {effective_complexity} (+{escalation})"
            )

        return self.select(agent_name, effective_complexity, is_code_task)

    def get_complexity(self, agent_name: str, story_complexity: int | None = None) -> int:
        """Get the complexity rating for an agent.

        For agents with variable complexity (coder, basic_info), use story_complexity.
        """
        if story_complexity is not None and agent_name in ("coder", "basic_info"):
            return story_complexity
        return AGENT_COMPLEXITY.get(agent_name, 5)

    def select(
        self,
        agent_name: str,
        story_complexity: int | None = None,
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
                "LLM calls paused (rate limit cascade). %.0fs remaining. Returning fallback.",
                remaining,
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

        for _name, provider in PROVIDERS.items():
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
                if (complexity <= 6 and power >= complexity) or (provider.name == "nemotron" and complexity <= 3):
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

        # Sort by preference: healthy first, non-rate-limited, local, cheapest, highest power
        def sort_key(p: ProviderConfig):
            cost_order = {"free": 0, "minimal": 1, "low": 2, "medium": 3, "high": 4}
            power = p.code_power if is_code_task else p.power
            circuit_open = 2 if self.is_circuit_open(p.name) else 0
            rate_limited = 1 if self._is_rate_limited(p.name) else 0
            return (
                circuit_open,  # Circuit-broken last
                rate_limited,  # Non-rate-limited first
                0 if p.local else 1,  # Local first
                cost_order.get(p.cost_tier, 5),  # Cheapest first
                -power,  # Highest power first (within same tier)
            )

        eligible.sort(key=sort_key)
        selected = eligible[0]
        if self.is_circuit_open(selected.name):
            logger.warning(f"All eligible providers circuit-broken for {agent_name}, using {selected.name} anyway")
        elif self._is_rate_limited(selected.name):
            logger.warning(f"All eligible providers rate-limited for {agent_name}, using {selected.name} anyway")
        else:
            logger.debug(f"Routing {agent_name} (complexity={complexity}) → {selected.name} (power={selected.power})")
        return selected

    def select_with_fallback(
        self,
        agent_name: str,
        story_complexity: int | None = None,
        is_code_task: bool = False,
    ) -> tuple[ProviderConfig, ProviderConfig]:
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
        story_complexity: int | None = None,
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

        for _name, provider in PROVIDERS.items():
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
                if (complexity <= 6 and power >= complexity) or (provider.name == "nemotron" and complexity <= 3):
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
