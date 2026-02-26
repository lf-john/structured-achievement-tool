class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen3:8b"):
        self.base_url = base_url
        self.model = model

    def get_completion(self, prompt: str) -> str:
        # For testing, return a mock response that ResponseParser can handle.
        # In a real scenario, this would involve an actual API call to Ollama.
        if "Ollama API Error" in prompt: # Simulate API error based on prompt content
            raise Exception("Ollama API Error")
        return "Score: 85, Confidence: 0.9"

