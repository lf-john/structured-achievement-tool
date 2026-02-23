"""
CLI Runner — Async subprocess spawner for LLM invocations.

Ported from Ralph Pro invokeClaudeDirect (lines 489-603).
Handles: env vars, timeout, stdout/stderr capture, API error detection,
environmental error classification.
"""

import asyncio
import os
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from src.llm.providers import ProviderConfig, get_env_for_provider

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 600  # 10 minutes
HEALTH_CHECK_TIMEOUT = 30


@dataclass
class CLIResult:
    """Result of a CLI invocation."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    is_api_error: bool = False
    is_environmental: bool = False
    api_error_code: Optional[int] = None
    duration_seconds: float = 0.0
    provider_name: str = ""


# Patterns that indicate API errors (from Ralph Pro)
API_ERROR_PATTERN = re.compile(r'API Error:\s*(\d{3})')
AUTH_ERROR_PATTERN = re.compile(r'authentication_error|invalid.*api.*key|unauthorized', re.IGNORECASE)
RATE_LIMIT_PATTERN = re.compile(r'rate.?limit|429|too many requests', re.IGNORECASE)


def _detect_api_error(output: str) -> tuple[bool, Optional[int]]:
    """Check if output contains API error indicators."""
    match = API_ERROR_PATTERN.search(output)
    if match:
        return True, int(match.group(1))
    if AUTH_ERROR_PATTERN.search(output):
        return True, 401
    if RATE_LIMIT_PATTERN.search(output):
        return True, 429
    return False, None


def _build_command(provider: ProviderConfig, prompt_file: Optional[str] = None, prompt: Optional[str] = None) -> list[str]:
    """Build the CLI command for a provider."""
    if provider.cli_command == "claude":
        cmd = ["claude"]
        if prompt_file:
            cmd.extend(["-p", f"@{prompt_file}"])
        elif prompt:
            cmd.extend(["-p", prompt])
        cmd.append("--dangerously-skip-permissions")
        # Add model override
        if provider.model_id:
            cmd.extend(["--model", provider.model_id])
        return cmd

    elif provider.cli_command == "gemini":
        cmd = ["gemini"]
        if prompt_file:
            cmd.extend(["-p", f"@{prompt_file}"])
        elif prompt:
            cmd.extend(["-p", prompt])
        cmd.append("--yolo")  # Auto-accept all actions (headless mode)
        if provider.model_id:
            cmd.extend(["-m", provider.model_id])
        return cmd

    elif provider.cli_command == "ollama":
        cmd = ["ollama", "run", provider.model_id]
        # Ollama reads from stdin, not -p flag
        return cmd

    else:
        raise ValueError(f"Unknown CLI command: {provider.cli_command}")


async def invoke(
    provider: ProviderConfig,
    prompt: Optional[str] = None,
    prompt_file: Optional[str] = None,
    working_directory: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> CLIResult:
    """Invoke an LLM via CLI subprocess.

    Args:
        provider: Provider configuration
        prompt: Text prompt (for -p flag or stdin)
        prompt_file: Path to prompt file (preferred over inline prompt for large prompts)
        working_directory: CWD for the subprocess
        timeout: Timeout in seconds

    Returns:
        CLIResult with stdout, stderr, exit code, and error classification
    """
    cmd = _build_command(provider, prompt_file, prompt)
    env = get_env_for_provider(provider)
    cwd = working_directory or os.getcwd()

    start_time = time.monotonic()

    try:
        if provider.cli_command == "ollama" and prompt and not prompt_file:
            # Ollama: pipe prompt to stdin
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(input=prompt.encode()),
                timeout=timeout,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

        duration = time.monotonic() - start_time
        stdout = stdout_bytes.decode(errors="replace")
        stderr = stderr_bytes.decode(errors="replace")

        # Check for API errors in output
        is_api_error, error_code = _detect_api_error(stdout + stderr)

        result = CLIResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=process.returncode or 0,
            is_api_error=is_api_error,
            api_error_code=error_code,
            duration_seconds=duration,
            provider_name=provider.name,
        )

        if is_api_error:
            logger.warning(f"API error from {provider.name}: code={error_code}")
        elif process.returncode != 0:
            logger.warning(f"CLI failed for {provider.name}: exit_code={process.returncode}")

        return result

    except asyncio.TimeoutError:
        duration = time.monotonic() - start_time
        logger.error(f"Timeout after {timeout}s for {provider.name}")
        # Try to kill the process
        try:
            process.terminate()
            await asyncio.sleep(2)
            if process.returncode is None:
                process.kill()
        except Exception:
            pass

        return CLIResult(
            stderr=f"Timeout after {timeout} seconds",
            exit_code=-1,
            is_api_error=True,
            api_error_code=408,
            duration_seconds=duration,
            provider_name=provider.name,
        )

    except FileNotFoundError:
        duration = time.monotonic() - start_time
        logger.error(f"CLI command not found: {cmd[0]}")
        return CLIResult(
            stderr=f"Command not found: {cmd[0]}",
            exit_code=-1,
            is_environmental=True,
            duration_seconds=duration,
            provider_name=provider.name,
        )

    except PermissionError:
        duration = time.monotonic() - start_time
        logger.error(f"Permission denied: {cmd[0]}")
        return CLIResult(
            stderr=f"Permission denied: {cmd[0]}",
            exit_code=-1,
            is_environmental=True,
            duration_seconds=duration,
            provider_name=provider.name,
        )


async def health_check(provider: ProviderConfig) -> bool:
    """Check if a provider is healthy by sending a simple test prompt."""
    result = await invoke(
        provider=provider,
        prompt="Reply with just the word HEALTHY",
        timeout=HEALTH_CHECK_TIMEOUT,
    )
    return (
        result.exit_code == 0
        and not result.is_api_error
        and "HEALTHY" in result.stdout.upper()
    )
