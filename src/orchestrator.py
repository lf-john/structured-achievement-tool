import os
import json
from typing import Dict, Any
from src.core.story_agent import StoryAgent
from src.core.phase_runner import PhaseRunner

class Orchestrator:
    def __init__(self, project_path: str, api_key: str, base_url: str = None):
        self.project_path = project_path
        self.agent = StoryAgent(api_key=api_key, base_url=base_url)
        self.runner = PhaseRunner(project_path=project_path)

    def process_task_file(self, file_path: str):
        """Main entry point to process an Obsidian task file."""
        with open(file_path, "r") as f:
            user_request = f.read()

        # 1. Classify
        classification = self.agent.classify(user_request)
        task_type = classification["task_type"]
        
        # 2. Decompose
        prd = self.agent.decompose(user_request, task_type)
        
        # 3. Execute Stories
        task_dir = os.path.dirname(file_path)
        results = []
        
        for story in prd.get("stories", []):
            phases = self.runner.get_phases(story)
            story_results = []
            
            for phase in phases:
                # Build the prompt for the phase
                phase_prompt = f"Execute {phase} for story: {story['title']}\nDescription: {story['description']}"
                
                # The CLI Router handles the actual tool invocation
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
            
            results.append({
                "story_id": story["id"],
                "results": story_results
            })
            
        return {
            "classification": classification,
            "prd": prd,
            "execution": results
        }
