"""
LLM Provider Registry — Model definitions with power ratings, CLI commands, and env vars.

Extends the original CLIRouter with complexity-based routing support.
All 11 models from the definitive implementation plan (044).
"""

import os
from enum import Enum

from pydantic import BaseModel


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
    settings_file: str | None = None  # Path to Claude settings file (for GLM backends)
    env_vars: dict[str, str] = {}
    local: bool = False  # True for Ollama models
    agentic: bool = False  # True for CLIs that can read/write files (claude, gemini)

    @property
    def is_claude(self) -> bool:
        return self.name in ("opus", "sonnet", "haiku")

    @property
    def is_local(self) -> bool:
        return self.local


# --- Provider Registry ---

PROVIDERS: dict[str, ProviderConfig] = {
    "opus": ProviderConfig(
        name="opus",
        power=9,
        code_power=9,
        speed=3,
        cost_tier=CostTier.HIGH,
        context_window=1_000_000,
        cli_command="claude",
        model_id="claude-opus-4-6",
        agentic=True,
    ),
    "sonnet": ProviderConfig(
        name="sonnet",
        power=8,
        code_power=8,
        speed=5,
        cost_tier=CostTier.MEDIUM,
        context_window=1_000_000,
        cli_command="claude",
        model_id="claude-sonnet-4-6",
        agentic=True,
    ),
    "haiku": ProviderConfig(
        name="haiku",
        power=7,
        code_power=7,
        speed=8,
        cost_tier=CostTier.LOW,
        context_window=200_000,
        cli_command="claude",
        model_id="claude-haiku-4-5-20251001",
        agentic=True,
    ),
    "gemini_31_pro": ProviderConfig(
        name="gemini_31_pro",
        power=9,
        code_power=9,
        speed=5,
        cost_tier=CostTier.MEDIUM,
        context_window=1_000_000,
        cli_command="gemini",
        model_id="gemini-3.1-pro-preview",
        agentic=True,
    ),
    "gemini_pro": ProviderConfig(
        name="gemini_pro",
        power=9,
        code_power=9,
        speed=5,
        cost_tier=CostTier.MEDIUM,
        context_window=1_000_000,
        cli_command="gemini",
        model_id="gemini-2.5-pro",
        agentic=True,
    ),
    "glm5": ProviderConfig(
        name="glm5",
        power=7,
        code_power=7,
        speed=5,
        cost_tier=CostTier.LOW,
        context_window=200_000,
        cli_command="claude",
        model_id="glm-4.7",
        env_vars={"ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"},
        agentic=True,
    ),
    "gemini_flash": ProviderConfig(
        name="gemini_flash",
        power=7,
        code_power=7,
        speed=9,
        cost_tier=CostTier.MINIMAL,
        context_window=1_000_000,
        cli_command="gemini",
        model_id="gemini-3-flash-preview",
        agentic=True,
    ),
    "gemini_25_flash": ProviderConfig(
        name="gemini_25_flash",
        power=6,
        code_power=6,
        speed=9,
        cost_tier=CostTier.MINIMAL,
        context_window=1_000_000,
        cli_command="gemini",
        model_id="gemini-2.5-flash",
        agentic=True,
    ),
    "glm_flash": ProviderConfig(
        name="glm_flash",
        power=5,
        code_power=5,
        speed=8,
        cost_tier=CostTier.MINIMAL,
        context_window=32_000,
        cli_command="claude",
        model_id="glm-4.7-flash",
        env_vars={"ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"},
        agentic=True,
    ),
    "qwen3_8b": ProviderConfig(
        name="qwen3_8b",
        power=5,
        code_power=5,
        speed=3,
        cost_tier=CostTier.FREE,
        context_window=32_000,
        cli_command="ollama",
        model_id="qwen3:8b",
        local=True,
    ),
    "deepseek_r1": ProviderConfig(
        name="deepseek_r1",
        power=5,
        code_power=4,
        speed=2,
        cost_tier=CostTier.FREE,
        context_window=32_000,
        cli_command="ollama",
        model_id="deepseek-r1:8b",
        local=True,
    ),
    "qwen25_coder": ProviderConfig(
        name="qwen25_coder",
        power=4,
        code_power=6,
        speed=3,
        cost_tier=CostTier.FREE,
        context_window=32_000,
        cli_command="ollama",
        model_id="qwen2.5-coder:7b",
        local=True,
    ),
    "nemotron": ProviderConfig(
        name="nemotron",
        power=3,
        code_power=3,
        speed=4,
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


def get_env_for_provider(provider: ProviderConfig) -> dict[str, str]:
    """Build environment variables for a provider.

    Returns a copy of os.environ with provider-specific vars applied.

    Key behaviors:
    - GLM/z.ai proxy: Maps GLM_API_KEY → ANTHROPIC_API_KEY, sets ANTHROPIC_BASE_URL
    - Claude-native: Strips ANTHROPIC_API_KEY/BASE_URL/AUTH_TOKEN to use built-in OAuth
    - Gemini: GEMINI_API_KEY must be in environment
    - Ollama: No special env needed
    """
    env = os.environ.copy()

    # Apply provider-specific env vars (e.g., ANTHROPIC_BASE_URL for GLM)
    env.update(provider.env_vars)

    # For GLM/z.ai proxy: map GLM_API_KEY to ANTHROPIC_API_KEY
    if provider.env_vars.get("ANTHROPIC_BASE_URL"):
        glm_key = os.environ.get("GLM_API_KEY", "")
        if glm_key:
            env["ANTHROPIC_API_KEY"] = glm_key

    # For Claude-native backends: strip all proxy/auth vars to use built-in OAuth
    if provider.is_claude:
        for key in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
            env.pop(key, None)

    # Strip CLAUDECODE env var to prevent nested session errors
    env.pop("CLAUDECODE", None)

    return env


def is_provider_available(provider: ProviderConfig) -> bool:
    """Check if a provider's prerequisites are met (API keys, CLI tools).

    Claude-native models use `claude` CLI's built-in auth (no env vars needed).
    GLM models via z.ai proxy require ANTHROPIC_AUTH_TOKEN.
    Gemini models require GEMINI_API_KEY.
    Ollama models require the ollama CLI.
    """
    import shutil

    # Check CLI command exists
    if not shutil.which(provider.cli_command):
        return False

    # Gemini requires GEMINI_API_KEY
    if provider.cli_command == "gemini":
        if not os.environ.get("GEMINI_API_KEY"):
            return False

    # GLM/z.ai proxy models need GLM_API_KEY
    if provider.env_vars.get("ANTHROPIC_BASE_URL"):
        if not os.environ.get("GLM_API_KEY"):
            return False

    # Claude-native models: claude CLI handles auth internally
    # Ollama models: just need the CLI (no API keys)

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
