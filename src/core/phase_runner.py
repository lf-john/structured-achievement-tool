import subprocess
import os
from typing import List, Dict, Any, Optional
from src.core.cli_router import CLIRouter

class PhaseRunner:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.router = CLIRouter()

    def get_phases(self, story: Dict[str, Any]) -> List[str]:
        """Determine phases for a story."""
        if "phases" in story:
            return story["phases"]
        
        if story.get("tdd", False):
            return ["DESIGN", "TDD-RED", "CODE", "VERIFY", "LEARN"]
        
        return ["DESIGN", "CODE", "VERIFY", "LEARN"]

    def execute_cli(self, provider: str, prompt: str, task_dir: str) -> Dict[str, Any]:
        """Invoke the CLI for a specific provider."""
        command = self.router.get_command(provider)
        env = os.environ.copy()
        env.update(self.router.get_env_vars(provider))
        
        # Build the command list
        if command == "claude":
            cmd = ["claude", "-p", prompt, "--dangerously-skip-permissions"]
        elif command == "gemini":
            cmd = ["gemini", "-p", prompt]
        else:
            cmd = [command, prompt]

        result = subprocess.run(
            cmd,
            cwd=task_dir,
            env=env,
            capture_output=True,
            text=True
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
