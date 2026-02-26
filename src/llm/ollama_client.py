class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen3:8b"):
        self.base_url = base_url
        self.model = model

    def generate(self, prompt: str) -> str:
        # Placeholder for actual API call
        return ""
