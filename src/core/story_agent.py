import json
import os
from typing import Dict, Any, List
import anthropic

class StoryAgent:
    def __init__(self, api_key: str, base_url: str = None):
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url
        )
        # Use absolute path to templates directory
        self.template_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "templates"
        )

    def _read_template(self, name: str) -> str:
        path = os.path.join(self.template_dir, f"{name}.md")
        with open(path, "r") as f:
            return f.read()

    def classify(self, user_request: str) -> Dict[str, Any]:
        """Classify the user request into a task type."""
        template = self._read_template("classify")
        
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=template,
            messages=[{"role": "user", "content": user_request}]
        )
        
        text = response.content[0].text
        return json.loads(text)

    def decompose(self, user_request: str, task_type: str) -> Dict[str, Any]:
        """Decompose the request into atomic user stories."""
        template = self._read_template("decompose")
        
        user_prompt = f"Request: {user_request}\nType: {task_type}"
        
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=template,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        text = response.content[0].text
        return json.loads(text)
