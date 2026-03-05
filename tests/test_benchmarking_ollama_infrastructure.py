"""
Tests for Ollama Benchmark Infrastructure (US-001)
Comprehensive tests for the benchmarking framework.
"""
import datetime
import os
from unittest.mock import MagicMock, patch

import pytest
import requests.exceptions
from pydantic import ValidationError

# Import the benchmarking module components
import src.benchmarking.config
import src.benchmarking.data_models
import src.benchmarking.ollama_client


class TestDirectoryStructure:
    """Verify the system-reports directory exists."""

    def test_system_reports_directory_exists(self):
        """Verify the ~/projects/system-reports/ directory exists."""
        system_reports_dir = os.path.expanduser("~/projects/system-reports/")
        assert os.path.exists(system_reports_dir), f"Directory {system_reports_dir} does not exist"


class TestDataModels:
    """Test the BenchmarkResult data model."""

    def test_benchmark_result_creation_with_valid_data(self):
        """Test creating a BenchmarkResult with all required fields."""
        result = src.benchmarking.data_models.BenchmarkResult(
            model_name="llama3",
            prompt="What is the capital of France?",
            tokens_per_sec=150.5,
            time_to_first_token=0.8,
            total_response_time=5.2,
            timestamp=datetime.datetime.now()
        )
        assert result.model_name == "llama3"
        assert result.prompt == "What is the capital of France?"
        assert result.tokens_per_sec == 150.5
        assert result.time_to_first_token == 0.8
        assert result.total_response_time == 5.2
        assert isinstance(result.timestamp, datetime.datetime)

    def test_benchmark_result_validation_missing_field(self):
        """Test that BenchmarkResult raises ValidationError for missing required fields."""
        with pytest.raises(ValidationError):
            src.benchmarking.data_models.BenchmarkResult(
                model_name="llama3",
                prompt="What is the capital of France?",
                # Missing tokens_per_sec
                time_to_first_token=0.8,
                total_response_time=5.2,
                timestamp=datetime.datetime.now()
            )

    def test_benchmark_result_default_types(self):
        """Test that all fields have correct types."""
        result = src.benchmarking.data_models.BenchmarkResult(
            model_name="llama3",
            prompt="Test prompt",
            tokens_per_sec=100.0,
            time_to_first_token=0.5,
            total_response_time=3.0,
            timestamp=datetime.datetime.now()
        )
        assert isinstance(result.model_name, str)
        assert isinstance(result.prompt, str)
        assert isinstance(result.tokens_per_sec, (int, float))
        assert isinstance(result.time_to_first_token, (int, float))
        assert isinstance(result.total_response_time, (int, float))
        assert isinstance(result.timestamp, datetime.datetime)


class TestConfiguration:
    """Test the configuration module."""

    def test_models_configured_correctly(self):
        """Verify all 4 models are defined in the configuration."""
        assert len(src.benchmarking.config.MODELS) == 4, f"Expected 4 models, got {len(src.benchmarking.config.MODELS)}"
        expected_models = ["qwen3:8b", "qwen2.5-coder:7b", "deepseek-r1:8b", "nemotron-mini"]
        assert expected_models == src.benchmarking.config.MODELS, f"Models mismatch: {src.benchmarking.config.MODELS}"

    def test_prompts_configured_correctly(self):
        """Verify all 3 prompts are defined in the configuration."""
        assert len(src.benchmarking.config.PROMPTS) == 3, f"Expected 3 prompts, got {len(src.benchmarking.config.PROMPTS)}"
        expected_prompts = [
            "Write a python function to calculate the fibonacci sequence.",
            "What are the main benefits of using a containerized application?",
            "Explain the concept of RAG in large language models.",
        ]
        assert expected_prompts == src.benchmarking.config.PROMPTS, f"Prompts mismatch: {src.benchmarking.config.PROMPTS}"

    def test_api_url_configured(self):
        """Verify the Ollama API URL is configured correctly."""
        assert src.benchmarking.config.OLLAMA_API_BASE_URL == "http://localhost:11434", \
            f"API URL mismatch: {src.benchmarking.config.OLLAMA_API_BASE_URL}"

    def test_configuration_is_list(self):
        """Test that MODELS and PROMPTS are lists (extensible)."""
        assert isinstance(src.benchmarking.config.MODELS, list)
        assert isinstance(src.benchmarking.config.PROMPTS, list)
        assert all(isinstance(m, str) for m in src.benchmarking.config.MODELS)
        assert all(isinstance(p, str) for p in src.benchmarking.config.PROMPTS)

    def test_configuration_can_be_extended(self):
        """Test that configuration can be easily extended by appending to lists."""
        new_model = "gpt-4"
        new_prompt = "What is 2+2?"
        src.benchmarking.config.MODELS.append(new_model)
        src.benchmarking.config.PROMPTS.append(new_prompt)
        assert new_model in src.benchmarking.config.MODELS
        assert new_prompt in src.benchmarking.config.PROMPTS
        # Clean up for other tests
        src.benchmarking.config.MODELS.remove(new_model)
        src.benchmarking.config.PROMPTS.remove(new_prompt)


class TestOllamaClient:
    """Test the OllamaClient HTTP client."""

    def test_ollama_client_initialization_with_default_url(self):
        """Test client initialization with default URL."""
        client = src.benchmarking.ollama_client.OllamaClient()
        assert client.base_url == "http://localhost:11434"

    def test_ollama_client_initialization_with_custom_url(self):
        """Test client initialization with custom URL."""
        custom_url = "http://custom-ollama:11434"
        client = src.benchmarking.ollama_client.OllamaClient(base_url=custom_url)
        assert client.base_url == custom_url

    @patch('requests.get')
    def test_is_available_when_ollama_is_running(self, mock_get):
        """Test is_available returns True when Ollama API is accessible."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = src.benchmarking.ollama_client.OllamaClient()
        assert client.is_available() is True
        mock_get.assert_called_once_with(client.base_url)

    @patch('requests.get')
    def test_is_available_when_ollama_is_not_running(self, mock_get):
        """Test is_available returns False when Ollama API is not accessible."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection failed")

        client = src.benchmarking.ollama_client.OllamaClient()
        assert client.is_available() is False

    @patch('requests.get')
    def test_list_models_successfully(self, mock_get):
        """Test listing available models from Ollama."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3", "modelfile": "llama3:latest"},
                {"name": "mistral", "modelfile": "mistral:latest"}
            ]
        }
        mock_get.return_value = mock_response

        client = src.benchmarking.ollama_client.OllamaClient()
        result = client.list_models()

        assert result is not None
        mock_get.assert_called_once_with(f"{client.base_url}/api/tags")

    @patch('requests.get')
    def test_list_models_handles_connection_error(self, mock_get):
        """Test list_models handles connection errors gracefully."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection failed")

        client = src.benchmarking.ollama_client.OllamaClient()
        result = client.list_models()

        assert result is None

    @patch('requests.get')
    def test_list_models_handles_http_error(self, mock_get):
        """Test list_models handles HTTP errors gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("HTTP 500 Error")
        mock_get.return_value = mock_response

        client = src.benchmarking.ollama_client.OllamaClient()
        result = client.list_models()

        assert result is None


class TestIntegration:
    """Integration tests for the benchmarking infrastructure."""

    def test_benchmark_result_serialization(self):
        """Test that BenchmarkResult can be serialized to dict."""
        result = src.benchmarking.data_models.BenchmarkResult(
            model_name="llama3",
            prompt="Test prompt",
            tokens_per_sec=100.0,
            time_to_first_token=0.5,
            total_response_time=3.0,
            timestamp=datetime.datetime.now()
        )
        data = result.model_dump()
        assert data["model_name"] == "llama3"
        assert data["prompt"] == "Test prompt"
        assert data["tokens_per_sec"] == 100.0
        assert data["time_to_first_token"] == 0.5
        assert data["total_response_time"] == 3.0
        assert isinstance(data["timestamp"], str) or isinstance(data["timestamp"], datetime.datetime)

    def test_benchmark_result_can_be_created_from_dict(self):
        """Test that BenchmarkResult can be created from dict."""
        data = {
            "model_name": "llama3",
            "prompt": "Test prompt",
            "tokens_per_sec": 100.0,
            "time_to_first_token": 0.5,
            "total_response_time": 3.0,
            "timestamp": "2026-02-26T12:00:00"
        }
        result = src.benchmarking.data_models.BenchmarkResult(**data)
        assert result.model_name == "llama3"
        assert result.prompt == "Test prompt"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
