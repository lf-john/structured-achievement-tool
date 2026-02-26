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


class LLMCLIExecutionError(Exception):
    """Custom exception for LLM CLI execution failures."""
    pass

from src.llm.providers import ProviderConfig, get_env_for_provider
from src.execution.stream_parser import StreamParser
from src.execution.session_continuator import SessionContinuator

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
# Note: bare "429" was removed — it caused false positives when LLM output
# contained "429" in content (e.g., HTTP status codes in documentation).
# Only match explicit rate-limit phrases or "error 429" / "status 429" patterns.
RATE_LIMIT_PATTERN = re.compile(
    r'rate.?limit|too many requests|error[:\s]+429|status[:\s]+429|code[:\s]+429|HTTP/\S+\s+429',
    re.IGNORECASE,
)


def _detect_api_error(stdout: str, stderr: str) -> tuple[bool, Optional[int]]:
    """Check if output contains API error indicators.

    Checks stderr for all patterns (API errors, auth, rate limits).
    Only checks stdout for explicit 'API Error: NNN' pattern — NOT rate
    limit patterns, which would false-positive on LLM content containing
    '429', 'rate limit', etc.
    """
    # Check stderr (reliable — contains actual API/CLI errors)
    combined_stderr = stderr
    match = API_ERROR_PATTERN.search(combined_stderr)
    if match:
        return True, int(match.group(1))
    if AUTH_ERROR_PATTERN.search(combined_stderr):
        return True, 401
    if RATE_LIMIT_PATTERN.search(combined_stderr):
        return True, 429

    # Check stdout only for explicit API error format (not rate-limit patterns)
    match = API_ERROR_PATTERN.search(stdout)
    if match:
        return True, int(match.group(1))

    return False, None


def _build_command(provider: ProviderConfig, prompt_file: Optional[str] = None, prompt: Optional[str] = None, agentic: bool = True) -> list[str]:
    """Build the CLI command for a provider.

    Args:
        agentic: If True, use agentic flags (--yolo, --dangerously-skip-permissions).
                 Set False for simple prompt-response phases (classify, decompose)
                 to avoid burning through API rate limits with tool calls.
    """
    if provider.cli_command == "claude":
        cmd = ["claude"]
        if prompt_file:
            cmd.extend(["-p", f"@{prompt_file}"])
        elif prompt:
            cmd.extend(["-p", prompt])
        if agentic:
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
        if agentic:
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
    stream_output_file: Optional[str] = None,
    task_id: Optional[str] = None,
    session_continuator: Optional[SessionContinuator] = None,
    agentic: bool = True,
) -> CLIResult:
    """Invoke an LLM via CLI subprocess.

    Args:
        provider: Provider configuration
        prompt: Text prompt (for -p flag or stdin)
        prompt_file: Path to prompt file (preferred over inline prompt for large prompts)
        working_directory: CWD for the subprocess
        timeout: Timeout in seconds
        stream_output_file: If provided, stream output incrementally to this file
        task_id: Task identifier for session continuation tracking
        session_continuator: If provided, auto-continue on max turns detection
        agentic: If True, use agentic flags. False for simple prompt-response.

    Returns:
        CLIResult with stdout, stderr, exit code, and error classification
    """
    cmd = _build_command(provider, prompt_file, prompt, agentic=agentic)
    env = get_env_for_provider(provider)
    cwd = working_directory or os.getcwd()

    start_time = time.monotonic()

    # Set up optional streaming
    stream_parser = None
    if stream_output_file:
        stream_parser = StreamParser(output_file=stream_output_file)

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
            if stream_parser:
                # Stream output while feeding stdin
                process.stdin.write(prompt.encode())
                await process.stdin.drain()
                process.stdin.close()
                stdout = await asyncio.wait_for(
                    stream_parser.stream_process(process),
                    timeout=timeout,
                )
                stderr_bytes = await process.stderr.read()
                stderr = stderr_bytes.decode(errors="replace")
                await process.wait()
            else:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(input=prompt.encode()),
                    timeout=timeout,
                )
                stdout = stdout_bytes.decode(errors="replace")
                stderr = stderr_bytes.decode(errors="replace")
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            if stream_parser:
                stdout = await asyncio.wait_for(
                    stream_parser.stream_process(process),
                    timeout=timeout,
                )
                stderr_bytes = await process.stderr.read()
                stderr = stderr_bytes.decode(errors="replace")
                await process.wait()
            else:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
                stdout = stdout_bytes.decode(errors="replace")
                stderr = stderr_bytes.decode(errors="replace")

        duration = time.monotonic() - start_time

        # Check for API errors in output
        is_api_error, error_code = _detect_api_error(stdout, stderr)

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
            logger.warning(f"API error stdout (first 500): {stdout[:500]}")
            logger.warning(f"API error stderr (first 500): {stderr[:500]}")
        elif process.returncode != 0:
            logger.warning(f"CLI failed for {provider.name}: exit_code={process.returncode}")

        # Auto-continue on max turns if continuator is provided
        if (session_continuator and task_id
                and session_continuator.detect_max_turns(stdout, result.exit_code)
                and session_continuator.can_continue(task_id)):
            session_id = session_continuator.extract_session_id(stdout)
            if session_id:
                logger.info(f"Max turns detected for {task_id}, auto-continuing session {session_id}")
                cont_result = session_continuator.continue_session(
                    session_id=session_id,
                    task_id=task_id,
                    working_dir=cwd,
                )
                if cont_result.success:
                    result.stdout += "\n" + cont_result.output
                    result.exit_code = 0
                else:
                    logger.warning(f"Session continuation failed: {cont_result.error}")

        return result

    except asyncio.TimeoutError:
        duration = time.monotonic() - start_time
        logger.error(f"Timeout after {timeout}s for {provider.name}")
        if stream_parser:
            stream_parser.finalize()
        # SIGKILL watchdog (Failure State 2): SIGTERM first, then hard-kill
        # after 10 seconds if the process hasn't exited.
        try:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                logger.warning(
                    "Process did not exit after SIGTERM+10s, sending SIGKILL"
                )
                process.kill()
                await asyncio.wait_for(process.wait(), timeout=5)
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

def execute_llm_command(
    provider_config: ProviderConfig,
    prompt: Optional[str] = None,
    prompt_file: Optional[str] = None,
    working_directory: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    stream_output_file: Optional[str] = None,
    task_id: Optional[str] = None,
    session_continuator: Optional[SessionContinuator] = None,
    agentic: bool = True,
) -> str:
    """Synchronous wrapper to invoke an LLM via CLI subprocess."""
    try:
        result = asyncio.run(
            invoke(
                provider=provider_config,
                prompt=prompt,
                prompt_file=prompt_file,
                working_directory=working_directory,
                timeout=timeout,
                stream_output_file=stream_output_file,
                task_id=task_id,
                session_continuator=session_continuator,
                agentic=agentic,
            )
        )

        if result.exit_code != 0 or result.is_api_error or result.is_environmental:
            error_details = f"Exit Code: {result.exit_code}, API Error: {result.is_api_error}, Environmental Error: {result.is_environmental}"
            full_error_message = f"LLM CLI command failed for {provider_config.name}. {error_details}\nStderr: {result.stderr}\nStdout: {result.stdout}"
            raise LLMCLIExecutionError(full_error_message)

        return result.stdout
    except Exception as e:
        raise LLMCLIExecutionError(f"Failed to execute LLM command: {e}") from e

