import subprocess
from typing import Dict, Any, Callable

class LLMCLIExecutionError(Exception):
    """Custom exception for LLM CLI execution failures."""
    pass

class CLIRunner:
    def __init__(self, run_shell_command_func: Callable[[str], str] = None):
        self._run_shell_command = run_shell_command_func or self._default_run_shell_command

    def _default_run_shell_command(self, command: str) -> str:
        """Default implementation for running shell commands."""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise LLMCLIExecutionError(f"Command failed: {e.cmd}\nStdout: {e.stdout}\nStderr: {e.stderr}") from e
        except Exception as e:
            raise LLMCLIExecutionError(f"Error executing command: {e}") from e

    def execute_llm_command(self, provider_config: Dict[str, Any], prompt: str) -> str:
        """
        Executes an LLM command based on the provider configuration.
        """
        cli_command_template = provider_config.get("cli_command")
        model_id = provider_config.get("model_id")

        if not cli_command_template or not model_id:
            raise ValueError("Provider configuration missing 'cli_command' or 'model_id'")
        
        # For now, a simple direct command execution
        # In a real scenario, this would involve proper CLI argument parsing and sanitization
        command = f"{cli_command_template} '{prompt}'"

        try:
            output = self._run_shell_command(command)
            return output
        except LLMCLIExecutionError:
            raise # Re-raise our custom exception
        except Exception as e:
            raise LLMCLIExecutionError(f"Failed to execute LLM command for {model_id}: {e}") from e

