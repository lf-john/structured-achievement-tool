"""
Classifier Agent — Classify a user request into a workflow type.

Complexity: 3 (Classification task). Routes to local models.
"""

from typing import Type
from pydantic import BaseModel

from src.agents.base_agent import BaseAgent
from src.llm.response_parser import ClassifyResponse


class ClassifierAgent(BaseAgent):

    @property
    def agent_name(self) -> str:
        return "classifier"

    @property
    def response_model(self) -> Type[BaseModel]:
        return ClassifyResponse

    async def classify(self, user_request: str, working_directory: str) -> ClassifyResponse:
        """Classify a user request into a workflow type.

        Returns ClassifyResponse with task_type, confidence, reasoning.
        """
        story = {
            "id": "CLASSIFY",
            "title": "Task Classification",
            "description": user_request,
        }

        result = await self.execute(
            story=story,
            phase="CLASSIFY",
            working_directory=working_directory,
        )
        return result
