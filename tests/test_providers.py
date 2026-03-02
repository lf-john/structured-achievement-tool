"""Tests for src.llm.providers — LLM provider registry and env handling."""

import os
import pytest
from unittest.mock import patch

from src.llm.providers import (
    PROVIDERS,
    ProviderConfig,
    CostTier,
    get_provider,
    get_env_for_provider,
    list_providers,
)


class TestProviderRegistry:
    def test_all_13_providers_registered(self):
        expected = {
            "opus", "sonnet", "haiku",
            "gemini_31_pro", "gemini_pro", "glm5", "gemini_flash", "gemini_25_flash", "glm_flash",
            "qwen3_8b", "deepseek_r1", "qwen25_coder", "nemotron",
        }
        assert set(PROVIDERS.keys()) == expected

    def test_power_ratings_are_valid(self):
        for name, p in PROVIDERS.items():
            assert 1 <= p.power <= 10, f"{name} power {p.power} out of range"
            assert 1 <= p.code_power <= 10, f"{name} code_power {p.code_power} out of range"

    def test_local_models_are_ollama(self):
        for name, p in PROVIDERS.items():
            if p.local:
                assert p.cli_command == "ollama", f"{name} is local but not ollama"

    def test_claude_models_identified(self):
        for name in ("opus", "sonnet", "haiku"):
            assert PROVIDERS[name].is_claude
        for name in ("gemini_pro", "qwen3_8b"):
            assert not PROVIDERS[name].is_claude


class TestGetProvider:
    def test_valid_provider(self):
        p = get_provider("sonnet")
        assert p.name == "sonnet"
        assert p.power == 8

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")


class TestGetEnvForProvider:
    @patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "bad_token", "CLAUDECODE": "yes"}, clear=False)
    def test_claude_strips_auth_token_and_claudecode(self):
        provider = get_provider("sonnet")
        env = get_env_for_provider(provider)
        assert "ANTHROPIC_AUTH_TOKEN" not in env
        assert "CLAUDECODE" not in env

    @patch.dict(os.environ, {"CLAUDECODE": "yes"}, clear=False)
    def test_glm_keeps_auth_but_strips_claudecode(self):
        provider = get_provider("glm5")
        env = get_env_for_provider(provider)
        assert "CLAUDECODE" not in env
        assert env.get("ANTHROPIC_BASE_URL") == "https://api.z.ai/api/anthropic"

    def test_local_provider_env(self):
        provider = get_provider("qwen3_8b")
        env = get_env_for_provider(provider)
        assert isinstance(env, dict)


class TestListProviders:
    def test_local_only(self):
        local = list_providers(local_only=True)
        assert all(p.local for p in local)
        assert len(local) == 4  # qwen3_8b, deepseek_r1, qwen25_coder, nemotron

    def test_cloud_only(self):
        cloud = list_providers(cloud_only=True)
        assert all(not p.local for p in cloud)
        assert len(cloud) == 9
