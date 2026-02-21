"""
IMPLEMENTATION PLAN for US-001:

Components:
  - LogicCore: A class that wraps the Anthropic SDK for direct API calls
    * __init__(api_key, base_url=None): Initialize Anthropic client with custom configuration
    * generate_text(prompt, model, system_prompt=None): Call Anthropic API and return response text

Test Cases:
  1. AC 1 (LogicCore class exists with api_key and optional base_url) -> test_class_initialization_with_api_key
  2. AC 2 (generate_text calls anthropic.messages.create) -> test_generate_text_calls_sdk_correctly
  3. AC 3 (generate_text returns text content from response) -> test_generate_text_returns_text_content
  4. AC 4 (tests use mocked Anthropic client) -> All tests use unittest.mock

Edge Cases:
  - Empty prompt string
  - None system_prompt (optional parameter)
  - Various model names
  - Custom base_url configuration
  - API errors handled gracefully
  - Response with multiple content blocks
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Import the class that doesn't exist yet - this will cause import error
from src.core.logic_core import LogicCore


class TestLogicCoreInitialization:
    """Test acceptance criterion 1: LogicCore class exists and can be initialized with api_key and optional base_url."""

    def test_class_exists(self):
        """Test that LogicCore class can be imported."""
        # This test verifies the class exists in the module
        assert LogicCore is not None
        assert hasattr(LogicCore, '__init__')

    @patch('src.core.logic_core.anthropic')
    def test_initialization_with_api_key_only(self, mock_anthropic):
        """Test that LogicCore can be initialized with just an api_key."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        logic_core = LogicCore(api_key="test-api-key")

        assert logic_core is not None
        assert isinstance(logic_core, LogicCore)
        # Verify Anthropic client was initialized with the api_key
        mock_anthropic.Anthropic.assert_called_once_with(api_key="test-api-key")

    @patch('src.core.logic_core.anthropic')
    def test_initialization_with_api_key_and_base_url(self, mock_anthropic):
        """Test that LogicCore can be initialized with api_key and custom base_url."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        logic_core = LogicCore(
            api_key="test-api-key",
            base_url="https://custom.api.com"
        )

        assert logic_core is not None
        # Verify Anthropic client was initialized with both parameters
        mock_anthropic.Anthropic.assert_called_once_with(
            api_key="test-api-key",
            base_url="https://custom.api.com"
        )

    @patch('src.core.logic_core.anthropic')
    def test_initialization_stores_client_reference(self, mock_anthropic):
        """Test that initialization stores the Anthropic client as an instance variable."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        logic_core = LogicCore(api_key="test-api-key")

        # Verify the client is stored
        assert hasattr(logic_core, 'client')
        assert logic_core.client == mock_client

    @patch('src.core.logic_core.anthropic')
    def test_initialization_with_empty_api_key(self, mock_anthropic):
        """Test that LogicCore handles empty api_key gracefully."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        logic_core = LogicCore(api_key="")

        assert logic_core is not None
        mock_anthropic.Anthropic.assert_called_once_with(api_key="")

    @patch('src.core.logic_core.anthropic')
    def test_initialization_with_none_base_url(self, mock_anthropic):
        """Test that LogicCore handles None base_url (default parameter)."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        logic_core = LogicCore(api_key="test-key", base_url=None)

        assert logic_core is not None
        # Should only pass api_key when base_url is None
        mock_anthropic.Anthropic.assert_called_once_with(api_key="test-key")


class TestGenerateTextMethod:
    """Test acceptance criteria 2 and 3: generate_text method calls SDK and returns text content."""

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_method_exists(self, mock_anthropic):
        """Test that generate_text method exists."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        logic_core = LogicCore(api_key="test-key")

        assert hasattr(logic_core, 'generate_text')
        assert callable(logic_core.generate_text)

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_calls_anthropic_messages_create(self, mock_anthropic):
        """Test that generate_text calls anthropic.messages.create with correct parameters."""
        # Setup mock client and response
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_content = [Mock(text="Hello, world!")]
        mock_response.content = mock_content
        mock_client.messages.create.return_value = mock_response

        # Call generate_text
        logic_core = LogicCore(api_key="test-key")
        result = logic_core.generate_text(
            prompt="Test prompt",
            model="claude-3-5-sonnet-20241022"
        )

        # Verify messages.create was called with correct parameters
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args

        # Check the call includes model, message with user role, and max_tokens
        assert call_args.kwargs['model'] == "claude-3-5-sonnet-20241022"
        assert 'messages' in call_args.kwargs
        assert len(call_args.kwargs['messages']) == 1
        assert call_args.kwargs['messages'][0]['role'] == 'user'
        assert call_args.kwargs['messages'][0]['content'] == "Test prompt"

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_with_system_prompt(self, mock_anthropic):
        """Test that generate_text includes system_prompt when provided."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_content = [Mock(text="Response")]
        mock_response.content = mock_content
        mock_client.messages.create.return_value = mock_response

        logic_core = LogicCore(api_key="test-key")
        logic_core.generate_text(
            prompt="Test prompt",
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a helpful assistant."
        )

        # Verify system prompt was included
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs['system'] == "You are a helpful assistant."

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_without_system_prompt(self, mock_anthropic):
        """Test that generate_text works without system_prompt (None)."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_content = [Mock(text="Response")]
        mock_response.content = mock_content
        mock_client.messages.create.return_value = mock_response

        logic_core = LogicCore(api_key="test-key")
        logic_core.generate_text(
            prompt="Test prompt",
            model="claude-3-5-sonnet-20241022",
            system_prompt=None
        )

        # Verify call was made (system prompt should not be in kwargs or should be None)
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args
        # system should either not be in kwargs or be None
        assert 'system' not in call_args.kwargs or call_args.kwargs.get('system') is None

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_returns_text_content(self, mock_anthropic):
        """Test that generate_text returns the text content from the response."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        # Setup mock response with text content
        mock_response = Mock()
        mock_text_block = Mock()
        mock_text_block.text = "This is the response text"
        mock_response.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_response

        logic_core = LogicCore(api_key="test-key")
        result = logic_core.generate_text(
            prompt="Test prompt",
            model="claude-3-5-sonnet-20241022"
        )

        # Verify the text content is returned
        assert result == "This is the response text"

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_handles_empty_response_content(self, mock_anthropic):
        """Test that generate_text handles empty content list."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_response.content = []
        mock_client.messages.create.return_value = mock_response

        logic_core = LogicCore(api_key="test-key")
        result = logic_core.generate_text(
            prompt="Test prompt",
            model="claude-3-5-sonnet-20241022"
        )

        # Should handle gracefully - either return empty string or None
        assert result == "" or result is None

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_with_various_models(self, mock_anthropic):
        """Test that generate_text works with different model names."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_content = [Mock(text="Response")]
        mock_response.content = mock_content
        mock_client.messages.create.return_value = mock_response

        logic_core = LogicCore(api_key="test-key")

        # Test different models
        models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229"
        ]

        for model in models:
            result = logic_core.generate_text(prompt="Test", model=model)
            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs['model'] == model

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_includes_max_tokens(self, mock_anthropic):
        """Test that generate_text includes max_tokens in the API call."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_content = [Mock(text="Response")]
        mock_response.content = mock_content
        mock_client.messages.create.return_value = mock_response

        logic_core = LogicCore(api_key="test-key")
        logic_core.generate_text(
            prompt="Test prompt",
            model="claude-3-5-sonnet-20241022"
        )

        # Verify max_tokens is included
        call_args = mock_client.messages.create.call_args
        assert 'max_tokens' in call_args.kwargs
        assert isinstance(call_args.kwargs['max_tokens'], int)


class TestGenerateTextEdgeCases:
    """Test edge cases and error handling for generate_text method."""

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_with_empty_prompt(self, mock_anthropic):
        """Test that generate_text handles empty prompt string."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_content = [Mock(text="")]
        mock_response.content = mock_content
        mock_client.messages.create.return_value = mock_response

        logic_core = LogicCore(api_key="test-key")
        result = logic_core.generate_text(
            prompt="",
            model="claude-3-5-sonnet-20241022"
        )

        # Should handle empty prompt
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs['messages'][0]['content'] == ""

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_with_multiline_prompt(self, mock_anthropic):
        """Test that generate_text handles multiline prompts."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_content = [Mock(text="Response")]
        mock_response.content = mock_content
        mock_client.messages.create.return_value = mock_response

        multiline_prompt = """This is a
multiline
prompt."""

        logic_core = LogicCore(api_key="test-key")
        logic_core.generate_text(
            prompt=multiline_prompt,
            model="claude-3-5-sonnet-20241022"
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs['messages'][0]['content'] == multiline_prompt

    @patch('src.core.logic_core.anthropic')
    def test_generate_text_with_special_characters_in_prompt(self, mock_anthropic):
        """Test that generate_text handles special characters in prompt."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_content = [Mock(text="Response")]
        mock_response.content = mock_content
        mock_client.messages.create.return_value = mock_response

        special_prompt = "Test with emojis 🎉 and special chars: <>&\"'"

        logic_core = LogicCore(api_key="test-key")
        logic_core.generate_text(
            prompt=special_prompt,
            model="claude-3-5-sonnet-20241022"
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs['messages'][0]['content'] == special_prompt


class TestLogicCoreIntegration:
    """Integration tests for LogicCore behavior."""

    @patch('src.core.logic_core.anthropic')
    def test_multiple_generate_text_calls(self, mock_anthropic):
        """Test multiple sequential calls to generate_text."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        # Setup different responses for each call
        responses = [
            Mock(content=[Mock(text="First response")]),
            Mock(content=[Mock(text="Second response")]),
            Mock(content=[Mock(text="Third response")])
        ]
        mock_client.messages.create.side_effect = responses

        logic_core = LogicCore(api_key="test-key")

        result1 = logic_core.generate_text(prompt="Prompt 1", model="claude-3-5-sonnet-20241022")
        result2 = logic_core.generate_text(prompt="Prompt 2", model="claude-3-5-sonnet-20241022")
        result3 = logic_core.generate_text(prompt="Prompt 3", model="claude-3-5-sonnet-20241022")

        assert result1 == "First response"
        assert result2 == "Second response"
        assert result3 == "Third response"
        assert mock_client.messages.create.call_count == 3

    @patch('src.core.logic_core.anthropic')
    def test_logic_core_with_different_configurations(self, mock_anthropic):
        """Test that multiple LogicCore instances can coexist with different configs."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_response.content = [Mock(text="Response")]
        mock_client.messages.create.return_value = mock_response

        # Create two instances with different configurations
        logic_core1 = LogicCore(api_key="key1", base_url="https://api1.com")
        logic_core2 = LogicCore(api_key="key2", base_url="https://api2.com")

        assert logic_core1 is not logic_core2
        assert isinstance(logic_core1, LogicCore)
        assert isinstance(logic_core2, LogicCore)

    @patch('src.core.logic_core.anthropic')
    def test_full_lifecycle_initialization_and_generation(self, mock_anthropic):
        """Test complete lifecycle: initialize -> generate_text -> receive response."""
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = Mock()
        mock_response.content = [Mock(text="Complete lifecycle test passed")]
        mock_client.messages.create.return_value = mock_response

        # Initialize
        logic_core = LogicCore(api_key="lifecycle-key")
        assert logic_core is not None

        # Generate text
        result = logic_core.generate_text(
            prompt="Test full lifecycle",
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a test assistant."
        )

        # Verify response
        assert result == "Complete lifecycle test passed"
        mock_client.messages.create.assert_called_once()


# Track test failures for exit code
fail_count = 0


def pytest_configure(config):
    """Configure pytest to track failures."""
    global fail_count


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Called at end of test session to determine exit code."""
    global fail_count
    fail_count = 1 if exitstatus != 0 else 0


if __name__ == "__main__":
    # Run pytest programmatically and exit with appropriate code
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)
