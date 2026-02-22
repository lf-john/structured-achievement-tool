import os
import json
import asyncio
from typing import Dict, Any, List
from src.core.story_agent import StoryAgent
from src.core.phase_runner import PhaseRunner
from src.core.dag_executor import DAGExecutor

class Orchestrator:
    def __init__(self, project_path: str, api_key: str, base_url: str = None, shadow_mode: bool = False):
        self.project_path = project_path
        self.agent = StoryAgent(api_key=api_key, base_url=base_url)
        self.runner = PhaseRunner(project_path=project_path)
        self.shadow_mode = shadow_mode

    def _get_output_dir(self, task_dir: str) -> str:
        """Return the appropriate output directory based on shadow_mode setting.

        Args:
            task_dir: The base task directory

        Returns:
            task_dir if shadow_mode is False, otherwise task_dir/_shadow
        """
        if self.shadow_mode:
            return os.path.join(task_dir, "_shadow")
        return task_dir

    def _ensure_shadow_dir(self, task_dir: str) -> str:
        """Ensure the shadow directory exists if shadow_mode is enabled.

        Args:
            task_dir: The base task directory

        Returns:
            The path to the shadow directory (or task_dir if shadow_mode is False)
        """
        output_dir = self._get_output_dir(task_dir)
        if self.shadow_mode and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        return output_dir

    async def execute_story(self, story: Dict[str, Any], task_dir: str) -> Dict[str, Any]:
        """Execute a single story through its phases."""
        # Ensure shadow directory exists if shadow mode is enabled
        output_dir = self._ensure_shadow_dir(task_dir)

        phases = self.runner.get_phases(story)
        story_results = []

        for phase in phases:
            # Build the prompt for the phase
            phase_prompt = f"Execute {phase} for story: {story['title']}\nDescription: {story['description']}"

            # The CLI Router handles the actual tool invocation
            # Note: task_dir is passed to execute_cli, not output_dir
            # The CLI tool is responsible for writing to the correct location
            result = self.runner.execute_cli(
                provider="anthropic", # Default
                prompt=phase_prompt,
                task_dir=task_dir
            )
            story_results.append({
                "phase": phase,
                "exit_code": result["exit_code"],
                "output": result["stdout"]
            })

        return {
            "story_id": story["id"],
            "results": story_results
        }

    async def process_task_file(self, file_path: str):
        """Main entry point to process an Obsidian task file using DAG execution."""
        with open(file_path, "r") as f:
            user_request = f.read()

        # 1. Classify
        classification = self.agent.classify(user_request)
        task_type = classification["task_type"]
        
        # 2. Decompose
        prd = self.agent.decompose(user_request, task_type)
        stories = prd.get("stories", [])
        
        # 3. Execute Stories via DAG
        task_dir = os.path.dirname(file_path)
        
        # Create executor wrapper that knows how to run our stories
        executor = DAGExecutor(stories, runner=self.runner)
        
        # Override the _execute_story_async to use our actual logic
        async def _run_actual_story(story_id: str):
            story = executor._stories_by_id[story_id]
            return await self.execute_story(story, task_dir)
            
        executor._execute_story_async = _run_actual_story
        
        # Execute in parallel levels
        results = await executor.execute_parallel()
            
        return {
            "classification": classification,
            "prd": prd,
            "execution": results
        }
