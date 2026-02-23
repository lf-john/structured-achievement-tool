"""
LLM Provider Registry — Model definitions with power ratings, CLI commands, and env vars.

Extends the original CLIRouter with complexity-based routing support.
All 11 models from the definitive implementation plan (044).
"""

import os
from typing import Dict, Optional
from pydantic import BaseModel
from enum import Enum


class CostTier(str, Enum):
    FREE = "free"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider/model."""
    name: str
    power: int  # Reasoning power rating (1-10)
    code_power: int  # Code generation power (1-10), defaults to power
    speed: int  # Speed rating (1-10)
    cost_tier: CostTier
    context_window: int  # In tokens (approximate)
    cli_command: str  # "claude", "gemini", or "ollama"
    model_id: str  # Model identifier for API calls
    settings_file: Optional[str] = None  # Path to Claude settings file (for GLM backends)
    env_vars: Dict[str, str] = {}
    local: bool = False  # True for Ollama models

    @property
    def is_claude(self) -> bool:
        return self.name in ("opus", "sonnet", "haiku")

    @property
    def is_local(self) -> bool:
        return self.local


# --- Provider Registry ---

PROVIDERS: Dict[str, ProviderConfig] = {
    "opus": ProviderConfig(
        name="opus",
        power=9, code_power=9, speed=3,
        cost_tier=CostTier.HIGH,
        context_window=1_000_000,
        cli_command="claude",
        model_id="claude-opus-4-6",
    ),
    "sonnet": ProviderConfig(
        name="sonnet",
        power=8, code_power=8, speed=5,
        cost_tier=CostTier.MEDIUM,
        context_window=1_000_000,
        cli_command="claude",
        model_id="claude-sonnet-4-6",
    ),
    "haiku": ProviderConfig(
        name="haiku",
        power=7, code_power=7, speed=8,
        cost_tier=CostTier.LOW,
        context_window=200_000,
        cli_command="claude",
        model_id="claude-haiku-4-5-20251001",
    ),
    "gemini_pro": ProviderConfig(
        name="gemini_pro",
        power=9, code_power=9, speed=5,
        cost_tier=CostTier.MEDIUM,
        context_window=1_000_000,
        cli_command="gemini",
        model_id="gemini-2.5-pro",
    ),
    "glm5": ProviderConfig(
        name="glm5",
        power=7, code_power=7, speed=5,
        cost_tier=CostTier.LOW,
        context_window=200_000,
        cli_command="claude",
        model_id="glm-5.0",
        env_vars={"ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"},
    ),
    "gemini_flash": ProviderConfig(
        name="gemini_flash",
        power=6, code_power=6, speed=9,
        cost_tier=CostTier.MINIMAL,
        context_window=1_000_000,
        cli_command="gemini",
        model_id="gemini-2.5-flash",
    ),
    "glm_flash": ProviderConfig(
        name="glm_flash",
        power=5, code_power=5, speed=8,
        cost_tier=CostTier.MINIMAL,
        context_window=32_000,
        cli_command="claude",
        model_id="glm-4.7-flash",
        env_vars={"ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"},
    ),
    "qwen3_8b": ProviderConfig(
        name="qwen3_8b",
        power=5, code_power=5, speed=3,
        cost_tier=CostTier.FREE,
        context_window=32_000,
        cli_command="ollama",
        model_id="qwen3:8b",
        local=True,
    ),
    "deepseek_r1": ProviderConfig(
        name="deepseek_r1",
        power=5, code_power=4, speed=2,
        cost_tier=CostTier.FREE,
        context_window=32_000,
        cli_command="ollama",
        model_id="deepseek-r1:8b",
        local=True,
    ),
    "qwen25_coder": ProviderConfig(
        name="qwen25_coder",
        power=4, code_power=6, speed=3,
        cost_tier=CostTier.FREE,
        context_window=32_000,
        cli_command="ollama",
        model_id="qwen2.5-coder:7b",
        local=True,
    ),
    "nemotron": ProviderConfig(
        name="nemotron",
        power=3, code_power=3, speed=4,
        cost_tier=CostTier.FREE,
        context_window=32_000,
        cli_command="ollama",
        model_id="nemotron-mini",
        local=True,
    ),
}


def get_provider(name: str) -> ProviderConfig:
    """Get a provider config by name."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]


def get_env_for_provider(provider: ProviderConfig) -> Dict[str, str]:
    """Build environment variables for a provider.

    Returns a copy of os.environ with provider-specific vars applied.
    Handles the ANTHROPIC_AUTH_TOKEN poisoning issue from Ralph Pro:
    non-GLM Claude backends must NOT have ANTHROPIC_AUTH_TOKEN set.
    """
    env = os.environ.copy()

    # Apply provider-specific env vars
    env.update(provider.env_vars)

    # For Claude-native backends, strip any existing ANTHROPIC_AUTH_TOKEN
    # that might have been set for GLM (this causes 401 errors)
    if provider.is_claude and "ANTHROPIC_AUTH_TOKEN" in env:
        del env["ANTHROPIC_AUTH_TOKEN"]

    # Strip CLAUDECODE env var to prevent nested session errors
    if "CLAUDECODE" in env:
        del env["CLAUDECODE"]

    return env


def is_provider_available(provider: ProviderConfig) -> bool:
    """Check if a provider's prerequisites are met (API keys, CLI tools)."""
    import shutil

    # Check CLI command exists
    if not shutil.which(provider.cli_command):
        return False

    # Gemini requires GEMINI_API_KEY
    if provider.cli_command == "gemini":
        if not os.environ.get("GEMINI_API_KEY"):
            return False

    # GLM models require ANTHROPIC_AUTH_TOKEN or specific env vars
    if provider.env_vars.get("ANTHROPIC_BASE_URL"):
        if not os.environ.get("ANTHROPIC_AUTH_TOKEN") and not os.environ.get("ANTHROPIC_API_KEY"):
            return False

    return True


def list_providers(local_only: bool = False, cloud_only: bool = False) -> list:
    """List available providers, optionally filtered."""
    result = []
    for p in PROVIDERS.values():
        if local_only and not p.local:
            continue
        if cloud_only and p.local:
            continue
        result.append(p)
    return result
