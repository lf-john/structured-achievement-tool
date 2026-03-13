# src/utils/ollama_client.py
import json
from typing import Any

import requests


class OllamaClient:
    def __init__(self, api_url: str, model: str):
        self.api_url = api_url
        self.model = model

    def score_lead(self, contact: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(contact)
        try:
            response = requests.post(
                self.api_url, json={"model": self.model, "prompt": prompt, "stream": False}, timeout=60
            )
            response.raise_for_status()
            response_json = response.json()
            return self._parse_response(response_json.get("response", ""))
        except requests.RequestException as e:
            # In a real app, you'd have more robust logging
            print(f"Error calling Ollama API: {e}")
            return {"score": 0, "confidence": "low", "error": str(e)}

    def _build_prompt(self, contact: dict[str, Any]) -> str:
        # This prompt engineering is crucial for getting good results.
        # It needs to clearly define the output format.
        return f"""
        Analyze the following contact and score them from 1 to 100 based on their fit for our Ideal Customer Profile (ICP).

        ICP Criteria:
        - Title/Seniority: Director, VP, C-level in Marketing, Sales, or Technology.
        - Company Size: 50 - 1000 employees.
        - Industry: SaaS, Technology, Marketing Agencies, E-commerce.
        - Geography: North America, Europe.

        Contact Details:
        - Name: {contact.get("name", "N/A")}
        - Title: {contact.get("title", "N/A")}
        - Company: {contact.get("company", "N/A")}
        - Industry: {contact.get("industry", "N/A")}
        - Company Size: {contact.get("company_size", "N/A")}
        - Location: {contact.get("location", "N/A")}

        Output your response as a JSON object with two keys: "score" (an integer from 1 to 100) and "confidence" (a string: "high", "medium", or "low").
        Do not include any other text or explanation.

        Example Response:
        {{"score": 85, "confidence": "high"}}

        JSON Response:
        """

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        try:
            # Find the JSON part of the response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in response")

            json_str = response_text[json_start:json_end]
            parsed = json.loads(json_str)

            # Basic validation
            if isinstance(parsed.get("score"), int) and parsed.get("confidence") in ["high", "medium", "low"]:
                return parsed
            else:
                raise ValueError("Parsed JSON does not match expected format")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"""Error parsing Ollama response: {e}
Response text: '{response_text}'""")
            return {"score": 0, "confidence": "low", "error": "Failed to parse response"}
