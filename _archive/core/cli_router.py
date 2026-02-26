import os
from typing import Dict, Optional
from pydantic import BaseModel

class ProviderConfig(BaseModel):
    name: str
    cli_command: str
    env_vars: Dict[str, str] = {}

class CLIRouter:
    def __init__(self):
        self.providers = {
            "anthropic": ProviderConfig(
                name="anthropic",
                cli_command="claude"
            ),
            "google": ProviderConfig(
                name="google",
                cli_command="gemini"
            ),
            "ollama": ProviderConfig(
                name="ollama",
                cli_command="claude",
                env_vars={
                    "ANTHROPIC_BASE_URL": "http://localhost:11434",
                    "ANTHROPIC_AUTH_TOKEN": "ollama"
                }
            ),
            "glm": ProviderConfig(
                name="glm",
                cli_command="claude",
                env_vars={
                    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"
                }
            )
        }

    def get_command(self, provider: str) -> str:
        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")
        return self.providers[provider].cli_command

    def get_env_vars(self, provider: str) -> Dict[str, str]:
        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")
        return self.providers[provider].env_vars
