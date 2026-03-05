import json

import requests


class N8NImportError(Exception):
    pass


class N8NWorkflowImporter:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def import_workflow(self, workflow_path: str) -> str:
        with open(workflow_path) as fh:
            workflow_data = json.load(fh)

        url = f"{self.api_url}/workflows"
        try:
            response = requests.post(url, headers=self.headers, json=workflow_data)
            response.raise_for_status()
            return response.json()["id"]
        except requests.RequestException as exc:
            raise N8NImportError(f"Failed to import workflow: {exc}") from exc

    def get_credentials(self) -> list:
        url = f"{self.api_url}/credentials"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.RequestException as exc:
            raise N8NImportError(f"Failed to fetch credentials: {exc}") from exc
