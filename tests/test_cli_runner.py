"""Tests for src.llm.cli_runner — Async subprocess LLM invocation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.cli_runner import (
    CLIResult,
    _build_command,
    _detect_api_error,
    invoke,
)
from src.llm.providers import get_provider


class TestDetectApiError:
    def test_api_error_with_code(self):
        is_error, code = _detect_api_error("", "API Error: 500")
        assert is_error
        assert code == 500

    def test_api_error_in_stdout(self):
        is_error, code = _detect_api_error("API Error: 500", "")
        assert is_error
        assert code == 500

    def test_auth_error(self):
        is_error, code = _detect_api_error("", "authentication_error: invalid key")
        assert is_error
        assert code == 401

    def test_rate_limit(self):
        is_error, code = _detect_api_error("", "rate limit exceeded")
        assert is_error
        assert code == 429

    def test_rate_limit_in_stderr_with_error_429(self):
        is_error, code = _detect_api_error("", "error: 429")
        assert is_error
        assert code == 429

    def test_no_error(self):
        is_error, code = _detect_api_error("Everything is fine, task completed.", "")
        assert not is_error
        assert code is None

    def test_429_in_stdout_not_false_positive(self):
        """LLM output containing '429' should NOT trigger rate limit detection."""
        is_error, code = _detect_api_error('{"stories": [{"description": "Handle HTTP 429 status codes"}]}', "")
        assert not is_error
        assert code is None


class TestBuildCommand:
    def test_claude_with_prompt(self):
        provider = get_provider("sonnet")
        cmd = _build_command(provider, prompt="test prompt")
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "--dangerously-skip-permissions" in cmd
        assert "--model" in cmd

    def test_claude_with_prompt_file(self):
        provider = get_provider("sonnet")
        cmd = _build_command(provider, prompt_file="/tmp/test.md")
        assert "@/tmp/test.md" in cmd

    def test_gemini_command(self):
        provider = get_provider("gemini_pro")
        cmd = _build_command(provider, prompt="test")
        assert cmd[0] == "gemini"
        assert "-p" in cmd

    def test_ollama_command(self):
        provider = get_provider("qwen3_8b")
        cmd = _build_command(provider)
        assert cmd[0] == "ollama"
        assert "run" in cmd
        assert "qwen3:8b" in cmd

    def test_unknown_cli_raises(self):
        from src.llm.providers import CostTier, ProviderConfig

        provider = ProviderConfig(
            name="test",
            power=5,
            code_power=5,
            speed=5,
            cost_tier=CostTier.FREE,
            context_window=1000,
            cli_command="unknown_cli",
            model_id="test",
        )
        with pytest.raises(ValueError, match="Unknown CLI command"):
            _build_command(provider, prompt="test")


class TestInvoke:
    @pytest.mark.asyncio
    async def test_file_not_found_returns_environmental(self):
        """If the CLI command doesn't exist, return environmental error."""
        provider = get_provider("sonnet")
        # Use a fake command
        with patch("src.llm.cli_runner._build_command", return_value=["nonexistent_command_xyz"]):
            result = await invoke(provider, prompt="test")
            assert result.is_environmental
            assert result.exit_code == -1

    @pytest.mark.asyncio
    async def test_timeout_returns_api_error(self):
        """Timeout should be classified as API error 408."""
        provider = get_provider("sonnet")

        async def mock_create_subprocess_exec(*args, **kwargs):
            proc = AsyncMock()

            async def slow_communicate(*a, **kw):
                await asyncio.sleep(100)
                return b"", b""

            proc.communicate = slow_communicate
            proc.returncode = None
            proc.terminate = MagicMock()
            proc.kill = MagicMock()
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess_exec):
            result = await invoke(provider, prompt="test", timeout=0)
            assert result.is_api_error
            assert result.api_error_code == 408


class TestCLIResult:
    def test_default_values(self):
        result = CLIResult()
        assert result.stdout == ""
        assert result.exit_code == 0
        assert not result.is_api_error
        assert not result.is_environmental
