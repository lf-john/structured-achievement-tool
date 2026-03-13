"""Tests for src.execution.multi_invoker — Multiple LLM Invoker with failover."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.execution.multi_invoker import (
    InvocationResult,
    MultiInvoker,
)
from src.llm.cli_runner import CLIResult
from src.llm.providers import get_provider


def _ok_result(provider_name: str = "qwen3_8b", stdout: str = "done") -> CLIResult:
    """Helper: build a successful CLIResult."""
    return CLIResult(
        stdout=stdout,
        stderr="",
        exit_code=0,
        is_api_error=False,
        is_environmental=False,
        provider_name=provider_name,
        duration_seconds=1.0,
    )


def _fail_result(provider_name: str = "qwen3_8b", code: int = 1) -> CLIResult:
    """Helper: build a failed CLIResult."""
    return CLIResult(
        stdout="",
        stderr="error",
        exit_code=code,
        is_api_error=False,
        is_environmental=False,
        provider_name=provider_name,
        duration_seconds=0.5,
    )


def _api_error_result(provider_name: str = "sonnet", error_code: int = 429) -> CLIResult:
    """Helper: build an API error CLIResult."""
    return CLIResult(
        stdout="",
        stderr="rate limit",
        exit_code=1,
        is_api_error=True,
        api_error_code=error_code,
        provider_name=provider_name,
        duration_seconds=0.3,
    )


def _env_error_result(provider_name: str = "sonnet") -> CLIResult:
    """Helper: build an environmental error CLIResult."""
    return CLIResult(
        stdout="",
        stderr="Command not found: claude",
        exit_code=-1,
        is_api_error=False,
        is_environmental=True,
        provider_name=provider_name,
        duration_seconds=0.1,
    )


# ---------------------------------------------------------------------------
# InvocationResult
# ---------------------------------------------------------------------------


class TestInvocationResult:
    def test_success_property_on_ok_result(self):
        ir = InvocationResult(cli_result=_ok_result(), provider_name="qwen3_8b")
        assert ir.success is True

    def test_success_property_on_failure(self):
        ir = InvocationResult(cli_result=_fail_result(), provider_name="qwen3_8b")
        assert ir.success is False

    def test_success_property_on_api_error(self):
        ir = InvocationResult(cli_result=_api_error_result(), provider_name="sonnet")
        assert ir.success is False

    def test_success_property_on_env_error(self):
        ir = InvocationResult(cli_result=_env_error_result(), provider_name="sonnet")
        assert ir.success is False

    def test_stdout_stderr_passthrough(self):
        ir = InvocationResult(cli_result=_ok_result(stdout="hello"), provider_name="qwen3_8b")
        assert ir.stdout == "hello"
        assert ir.stderr == ""


# ---------------------------------------------------------------------------
# Health Tracking
# ---------------------------------------------------------------------------


class TestHealthTracking:
    def test_new_provider_is_healthy(self):
        invoker = MultiInvoker()
        assert invoker.is_provider_healthy("qwen3_8b") is True

    def test_single_failure_stays_healthy(self):
        invoker = MultiInvoker(failure_threshold=3)
        invoker._record_failure("qwen3_8b")
        assert invoker.is_provider_healthy("qwen3_8b") is True

    def test_threshold_failures_marks_unhealthy(self):
        invoker = MultiInvoker(failure_threshold=3)
        for _ in range(3):
            invoker._record_failure("qwen3_8b")
        assert invoker.is_provider_healthy("qwen3_8b") is False

    def test_success_resets_consecutive_failures(self):
        invoker = MultiInvoker(failure_threshold=3)
        invoker._record_failure("qwen3_8b")
        invoker._record_failure("qwen3_8b")
        invoker._record_success("qwen3_8b")
        invoker._record_failure("qwen3_8b")
        # Only 1 consecutive failure after success, not 3
        assert invoker.is_provider_healthy("qwen3_8b") is True

    def test_auto_recovery_after_cooldown(self):
        invoker = MultiInvoker(failure_threshold=1, cooldown_seconds=0.01)
        invoker._record_failure("qwen3_8b")
        assert invoker.is_provider_healthy("qwen3_8b") is False
        # Wait for cooldown
        time.sleep(0.02)
        assert invoker.is_provider_healthy("qwen3_8b") is True

    def test_no_recovery_before_cooldown(self):
        invoker = MultiInvoker(failure_threshold=1, cooldown_seconds=9999)
        invoker._record_failure("qwen3_8b")
        assert invoker.is_provider_healthy("qwen3_8b") is False

    def test_health_summary(self):
        invoker = MultiInvoker(failure_threshold=2)
        invoker._record_success("qwen3_8b")
        invoker._record_failure("sonnet")
        invoker._record_failure("sonnet")
        summary = invoker.get_health_summary()
        assert summary["qwen3_8b"]["healthy"] is True
        assert summary["qwen3_8b"]["total_invocations"] == 1
        assert summary["sonnet"]["healthy"] is False
        assert summary["sonnet"]["consecutive_failures"] == 2

    def test_reset_health_single_provider(self):
        invoker = MultiInvoker(failure_threshold=1)
        invoker._record_failure("qwen3_8b")
        invoker._record_failure("sonnet")
        invoker.reset_health("qwen3_8b")
        assert invoker.is_provider_healthy("qwen3_8b") is True
        # sonnet untouched
        assert invoker.is_provider_healthy("sonnet") is False

    def test_reset_health_all(self):
        invoker = MultiInvoker(failure_threshold=1)
        invoker._record_failure("qwen3_8b")
        invoker._record_failure("sonnet")
        invoker.reset_health()
        assert invoker.is_provider_healthy("qwen3_8b") is True
        assert invoker.is_provider_healthy("sonnet") is True


# ---------------------------------------------------------------------------
# execute_with_provider
# ---------------------------------------------------------------------------


class TestExecuteWithProvider:
    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_success(self, mock_invoke):
        mock_invoke.return_value = _ok_result("qwen3_8b", "answer")
        invoker = MultiInvoker()
        result = await invoker.execute_with_provider("qwen3_8b", "hello")
        assert result.success is True
        assert result.provider_name == "qwen3_8b"
        assert result.stdout == "answer"
        mock_invoke.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_failure_records_health(self, mock_invoke):
        mock_invoke.return_value = _fail_result("qwen3_8b")
        invoker = MultiInvoker(failure_threshold=1)
        result = await invoker.execute_with_provider("qwen3_8b", "hello")
        assert result.success is False
        assert invoker.is_provider_healthy("qwen3_8b") is False

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_passes_working_directory_and_timeout(self, mock_invoke):
        mock_invoke.return_value = _ok_result()
        invoker = MultiInvoker()
        await invoker.execute_with_provider("qwen3_8b", "test", working_directory="/tmp", timeout=30)
        call_kwargs = mock_invoke.call_args[1]
        assert call_kwargs["working_directory"] == "/tmp"
        assert call_kwargs["timeout"] == 30


# ---------------------------------------------------------------------------
# execute_with_routing
# ---------------------------------------------------------------------------


class TestExecuteWithRouting:
    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_primary_succeeds(self, mock_invoke):
        mock_invoke.return_value = _ok_result("sonnet")
        engine = MagicMock()
        engine.select_with_fallback.return_value = (get_provider("sonnet"), get_provider("glm5"))
        invoker = MultiInvoker(routing_engine=engine)
        result = await invoker.execute_with_routing("coder", "write code")
        assert result.success is True
        assert result.provider_name == "sonnet"
        assert result.was_failover is False
        assert result.attempts == 1

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_failover_on_primary_failure(self, mock_invoke):
        mock_invoke.side_effect = [
            _fail_result("sonnet"),
            _ok_result("glm5", "fallback answer"),
        ]
        engine = MagicMock()
        engine.select_with_fallback.return_value = (get_provider("sonnet"), get_provider("glm5"))
        invoker = MultiInvoker(routing_engine=engine)
        result = await invoker.execute_with_routing("coder", "write code")
        assert result.success is True
        assert result.provider_name == "glm5"
        assert result.was_failover is True
        assert result.failover_from == "sonnet"
        assert result.attempts == 2

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_all_candidates_fail(self, mock_invoke):
        mock_invoke.side_effect = [
            _fail_result("sonnet"),
            _fail_result("glm5"),
        ]
        engine = MagicMock()
        engine.select_with_fallback.return_value = (get_provider("sonnet"), get_provider("glm5"))
        invoker = MultiInvoker(routing_engine=engine)
        result = await invoker.execute_with_routing("coder", "write code")
        assert result.success is False
        assert result.attempts == 2

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_unhealthy_primary_skipped(self, mock_invoke):
        """When primary is unhealthy, healthy fallback is tried first."""
        mock_invoke.return_value = _ok_result("glm5")
        engine = MagicMock()
        engine.select_with_fallback.return_value = (get_provider("sonnet"), get_provider("glm5"))
        invoker = MultiInvoker(routing_engine=engine, failure_threshold=1, cooldown_seconds=9999)
        # Mark sonnet unhealthy
        invoker._record_failure("sonnet")
        result = await invoker.execute_with_routing("coder", "write code")
        # glm5 should be tried first since sonnet is unhealthy
        assert result.success is True
        assert result.provider_name == "glm5"

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_same_primary_and_fallback(self, mock_invoke):
        """When primary == fallback, only one attempt is made."""
        mock_invoke.return_value = _ok_result("sonnet")
        engine = MagicMock()
        engine.select_with_fallback.return_value = (get_provider("sonnet"), get_provider("sonnet"))
        invoker = MultiInvoker(routing_engine=engine)
        result = await invoker.execute_with_routing("coder", "write code")
        assert result.attempts == 1

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_routing_passes_agent_params(self, mock_invoke):
        mock_invoke.return_value = _ok_result("sonnet")
        engine = MagicMock()
        engine.select_with_fallback.return_value = (get_provider("sonnet"), get_provider("glm5"))
        invoker = MultiInvoker(routing_engine=engine)
        await invoker.execute_with_routing("coder", "code", story_complexity=7, is_code_task=True)
        engine.select_with_fallback.assert_called_once_with(agent_name="coder", story_complexity=7, is_code_task=True)


# ---------------------------------------------------------------------------
# execute_local_first
# ---------------------------------------------------------------------------


class TestExecuteLocalFirst:
    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    @patch("src.execution.multi_invoker.list_providers")
    async def test_local_succeeds(self, mock_list, mock_invoke):
        mock_list.return_value = [get_provider("qwen3_8b"), get_provider("deepseek_r1")]
        mock_invoke.return_value = _ok_result("qwen3_8b", "local answer")
        invoker = MultiInvoker()
        result = await invoker.execute_local_first("summarize this")
        assert result.success is True
        assert result.provider_name == "qwen3_8b"
        assert result.was_failover is False

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    @patch("src.execution.multi_invoker.list_providers")
    async def test_local_fails_cloud_fallback(self, mock_list, mock_invoke):
        mock_list.return_value = [get_provider("qwen3_8b")]
        mock_invoke.side_effect = [
            _fail_result("qwen3_8b"),
            _ok_result("gemini_flash", "cloud answer"),
        ]
        invoker = MultiInvoker()
        result = await invoker.execute_local_first("summarize this")
        assert result.success is True
        assert result.provider_name == "gemini_flash"
        assert result.was_failover is True
        assert result.failover_from == "qwen3_8b"
        assert result.attempts == 2

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    @patch("src.execution.multi_invoker.list_providers")
    async def test_no_local_providers_goes_to_cloud(self, mock_list, mock_invoke):
        mock_list.return_value = []
        mock_invoke.return_value = _ok_result("gemini_flash", "cloud only")
        invoker = MultiInvoker()
        result = await invoker.execute_local_first("summarize this")
        assert result.success is True
        assert result.provider_name == "gemini_flash"
        assert result.was_failover is True

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    @patch("src.execution.multi_invoker.list_providers")
    async def test_preferred_local_override(self, mock_list, mock_invoke):
        mock_invoke.return_value = _ok_result("deepseek_r1", "deepseek answer")
        invoker = MultiInvoker()
        result = await invoker.execute_local_first("summarize", preferred_local="deepseek_r1")
        assert result.provider_name == "deepseek_r1"
        # list_providers should NOT be called when preferred_local is set
        mock_list.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    @patch("src.execution.multi_invoker.list_providers")
    async def test_custom_cloud_fallback(self, mock_list, mock_invoke):
        mock_list.return_value = [get_provider("qwen3_8b")]
        mock_invoke.side_effect = [
            _fail_result("qwen3_8b"),
            _ok_result("haiku", "haiku answer"),
        ]
        invoker = MultiInvoker()
        result = await invoker.execute_local_first("summarize", cloud_fallback="haiku")
        assert result.provider_name == "haiku"
        assert result.was_failover is True

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    @patch("src.execution.multi_invoker.list_providers")
    async def test_both_local_and_cloud_fail(self, mock_list, mock_invoke):
        mock_list.return_value = [get_provider("qwen3_8b")]
        mock_invoke.side_effect = [
            _fail_result("qwen3_8b"),
            _fail_result("gemini_flash"),
        ]
        invoker = MultiInvoker()
        result = await invoker.execute_local_first("summarize")
        assert result.success is False
        assert result.was_failover is True


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_default_routing_engine_created(self):
        invoker = MultiInvoker()
        assert invoker.routing_engine is not None

    def test_custom_thresholds(self):
        invoker = MultiInvoker(failure_threshold=5, cooldown_seconds=60)
        assert invoker.failure_threshold == 5
        assert invoker.cooldown_seconds == 60

    def test_is_result_failure_api_error(self):
        invoker = MultiInvoker()
        assert invoker._is_result_failure(_api_error_result()) is True

    def test_is_result_failure_env_error(self):
        invoker = MultiInvoker()
        assert invoker._is_result_failure(_env_error_result()) is True

    def test_is_result_failure_success(self):
        invoker = MultiInvoker()
        assert invoker._is_result_failure(_ok_result()) is False

    @pytest.mark.asyncio
    @patch("src.execution.multi_invoker.invoke", new_callable=AsyncMock)
    async def test_api_error_records_failure(self, mock_invoke):
        mock_invoke.return_value = _api_error_result("sonnet", 429)
        invoker = MultiInvoker(failure_threshold=1)
        await invoker.execute_with_provider("sonnet", "test")
        assert invoker.is_provider_healthy("sonnet") is False
