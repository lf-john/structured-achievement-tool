import json, os
from typing import Dict
from src.core.logic_core import LogicCore

class StoryAgent:
    def __init__(self, p: str): 
        self.l = LogicCore(p)
        self.t = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

    def _r(self, n: str) -> str:
        with open(os.path.join(self.t, f"{n}.md"), "r") as f: return f.read()

    def _p(self, t: str) -> Dict:
        try: 
            s, e = t.find("{"), t.rfind("}")+1
            return json.loads(t[s:e]) if s!=-1 else {"r":t}
        except Exception as e: 
            raise ValueError(f"JSON fail: {e}\n{t}")

    def classify(self, r: str) -> Dict: 
        # Use the CLASSIFY phase routing
        return self._p(self.l.generate_text(r, phase="CLASSIFY", system_prompt=self._r("classify")))

    def decompose(self, r: str, t: str, existing_prd: Dict = None, existing_progress: Dict = None) -> Dict:
        # Use the DECOMPOSE phase routing
        prompt = f"Request: {r}\nType: {t}"
        if existing_prd:
            prompt += f"\n\nExisting PRD:\n{json.dumps(existing_prd, indent=2)}"
        if existing_progress:
            prompt += f"\n\nExisting Progress:\n{json.dumps(existing_progress, indent=2)}"
        
        prompt += "\n\n<User>"
        return self._p(self.l.generate_text(prompt, phase="DECOMPOSE", system_prompt=self._r("decompose")))
