"""
Logic Core SDK Interface

Wraps the Anthropic SDK to provide direct API calls for logic/summarization phases.
"""

import anthropic


class LogicCore:
    """Wrapper for Anthropic SDK to provide text generation capabilities."""

    def __init__(self, api_key: str, base_url: str = None):
        """
        Initialize the LogicCore with an Anthropic client.

        Args:
            api_key: The API key for authenticating with Anthropic
            base_url: Optional custom base URL for the API
        """
        if base_url:
            self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=api_key)

    def generate_text(self, prompt: str, model: str, system_prompt: str = None) -> str:
        """
        Generate text using the Anthropic API.

        Args:
            prompt: The user prompt to send to the model
            model: The model name to use (e.g., "claude-3-5-sonnet-20241022")
            system_prompt: Optional system prompt to guide the model's behavior

        Returns:
            The text content from the model's response
        """
        # Build the API call parameters
        kwargs = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }

        # Only include system prompt if provided
        if system_prompt:
            kwargs["system"] = system_prompt

        # Call the Anthropic API
        response = self.client.messages.create(**kwargs)

        # Extract and return the text content
        if response.content and len(response.content) > 0:
            return response.content[0].text

        return ""
