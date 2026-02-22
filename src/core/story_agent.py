import json, os
from typing import Dict, Any
from src.core.logic_core import LogicCore

class StoryAgent:
    def __init__(self, project_path: str):
        self.logic = LogicCore(project_path)
        self.template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

    def _read_template(self, name: str) -> str:
        with open(os.path.join(self.template_dir, f"{name}.md"), "r") as f:
            return f.read()

    def _parse_json(self, text: str) -> Dict:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1: return {"response": text}
            return json.loads(text[start:end])
        except Exception as e:
            raise ValueError(f"JSON parse failed: {e}\nRaw: {text}")

    def classify(self, user_request: str) -> Dict:
        template = self._read_template("classify")
        # Append the required <User> tag
        prompt = user_request + "\n\n<User>"
        response = self.logic.generate_text(model="sonnet", prompt=prompt, system_prompt=template)
        return self._parse_json(response)

    def decompose(self, user_request: str, task_type: str, existing_prd: Dict = None, existing_progress: Dict = None) -> Dict:
        template = self._read_template("decompose")
        
        prompt = f"Request: {user_request}\nType: {task_type}"
        if existing_prd:
            prompt += f"\n\nExisting PRD:\n{json.dumps(existing_prd, indent=2)}"
        if existing_progress:
            prompt += f"\n\nExisting Progress:\n{json.dumps(existing_progress, indent=2)}"
            
        prompt += "\n\n<User>"
        
        response = self.logic.generate_text(model="sonnet", prompt=prompt, system_prompt=template)
        prd = self._parse_json(response)
        
        # Enforce required schema for Ralph Pro
        if "stories" in prd:
            for story in prd["stories"]:
                if "status" not in story:
                    story["status"] = "pending"
                    
        return prd
