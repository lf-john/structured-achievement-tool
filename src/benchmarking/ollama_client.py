import requests

from .config import OLLAMA_API_BASE_URL


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_API_BASE_URL):
        self.base_url = base_url

    def is_available(self) -> bool:
        """Check if the Ollama API is running."""
        try:
            response = requests.get(self.base_url)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False

    def list_models(self):
        """List available models."""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Ollama API: {e}")
            return None
