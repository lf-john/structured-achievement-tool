import pytest
from unittest.mock import patch, MagicMock
from src.core.story_agent import StoryAgent

@patch("anthropic.Anthropic")
def test_classify_logic(mock_anthropic):
    # Mock the response from Claude
    mock_client = mock_anthropic.return_value
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"task_type": "development", "confidence": 0.95}')]
    mock_client.messages.create.return_value = mock_message

    agent = StoryAgent(api_key="fake")
    result = agent.classify("Implement a login page")
    
    assert result["task_type"] == "development"
    assert result["confidence"] == 0.95

@patch("anthropic.Anthropic")
def test_decompose_logic(mock_anthropic):
    mock_client = mock_anthropic.return_value
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"stories": [{"id": "US-001", "title": "Create DB"}]}')]
    mock_client.messages.create.return_value = mock_message

    agent = StoryAgent(api_key="fake")
    result = agent.decompose("Build a website", "development")
    
    assert len(result["stories"]) == 1
    assert result["stories"][0]["id"] == "US-001"
