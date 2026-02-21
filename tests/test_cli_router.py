import pytest
from src.core.cli_router import CLIRouter, ProviderConfig

def test_route_anthropic_returns_claude():
    router = CLIRouter()
    command = router.get_command("anthropic")
    assert command == "claude"

def test_route_google_returns_gemini():
    router = CLIRouter()
    command = router.get_command("google")
    assert command == "gemini"

def test_route_ollama_returns_claude():
    router = CLIRouter()
    command = router.get_command("ollama")
    assert command == "claude"

def test_route_unknown_provider_raises_error():
    router = CLIRouter()
    with pytest.raises(ValueError, match="Unknown provider"):
        router.get_command("unknown")

def test_get_env_vars_for_ollama():
    router = CLIRouter()
    env = router.get_env_vars("ollama")
    assert env["ANTHROPIC_BASE_URL"] == "http://localhost:11434"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "ollama"

def test_get_env_vars_for_google():
    router = CLIRouter()
    # Gemini CLI uses its own internal auth or GOOGLE_API_KEY
    # but for now we just verify it doesn't force Anthropic vars
    env = router.get_env_vars("google")
    assert "ANTHROPIC_BASE_URL" not in env
