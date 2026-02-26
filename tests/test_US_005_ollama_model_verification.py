"""
IMPLEMENTATION PLAN for US-005:

Components:
  - OllamaModelVerifier (src/ollama_model_verifier.py):
      - Query http://localhost:11434/api/tags to get available models
      - Verify expected models are present (Qwen3 8B, Qwen2.5-Coder 7B, DeepSeek R1 8B, Nemotron Mini, nomic-embed-text)
      - Return boolean indicating if all expected models are available
      - Return list of available models for debugging
      - Handle connection errors gracefully

Test Cases:
  1. [AC 1] Verify all expected Ollama models are present
      - Test with all models present: should return True
  2. [AC 1] Verify when some models are missing
      - Test with missing models: should return False
  3. Verify API connection error handling
      - Test with Ollama not running: should handle gracefully
  4. Verify empty models list
      - Test when no models are available: should return False
  5. Verify exact model names match expectations
      - Test that specific model names are recognized

Edge Cases:
  - Ollama service is not running
  - API returns non-200 status
  - Empty response from API
  - Invalid JSON response from API
  - Partial model names (different casing)
"""

import pytest
import requests
from unittest.mock import patch, MagicMock
import sys
from src.ollama_model_verifier import verify_ollama_models, get_expected_models


class TestOllamaModelVerifier:
    """Tests for verifying Ollama model availability."""

    def test_verify_ollama_models_exists(self):
        """Test that the verify_ollama_models function exists."""
        global verify_ollama_models
        assert callable(verify_ollama_models), "verify_ollama_models function does not exist"

    def test_get_expected_models_exists(self):
        """Test that the get_expected_models function exists."""
        global get_expected_models
        assert callable(get_expected_models), "get_expected_models function does not exist"

    def test_verify_all_models_present(self):
        """Test that verification succeeds when all expected models are present."""
        global verify_ollama_models, get_expected_models

        expected_models = get_expected_models()

        # Mock API response with all expected models
        mock_api_response = {
            "models": [
                {"name": "qwen:latest"},
                {"name": "qwen3:8b"},
                {"name": "qwen2.5-coder:7b"},
                {"name": "deepseek-r1:8b"},
                {"name": "nemotron-mini"},
                {"name": "nomic-embed-text"}
            ]
        }

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            all_available, available_models = verify_ollama_models()

            assert all_available is True, "Should return True when all models are present"
            assert len(available_models) == 6, f"Expected 6 models, got {len(available_models)}"

    def test_verify_all_models_present_with_aliases(self):
        """Test that models with different names/versions are still recognized."""
        global verify_ollama_models, get_expected_models

        expected_models = get_expected_models()

        # Mock response with model name variations
        mock_api_response = {
            "models": [
                {"name": "qwen2.5:8b"},
                {"name": "qwen2.5-coder-7b-instruct"},
                {"name": "deepseek-r1-distill-8b"},
                {"name": "nvidia/nemotron-mini-4b"},
                {"name": "nomic-embed-text-v1.5"}
            ]
        }

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            all_available, available_models = verify_ollama_models()

            assert all_available is True, "Should return True when all models (with aliases) are present"
            assert len(available_models) == 5, f"Expected 5 models, got {len(available_models)}"

    def test_verify_missing_models(self):
        """Test that verification fails when some models are missing."""
        global verify_ollama_models, get_expected_models

        expected_models = get_expected_models()

        # Mock response missing some expected models
        mock_api_response = {
            "models": [
                {"name": "qwen:latest"},
                {"name": "qwen2.5-coder:7b"},
                {"name": "some-other-model"}
            ]
        }

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            all_available, available_models = verify_ollama_models()

            assert all_available is False, "Should return False when models are missing"
            assert len(available_models) == 3, f"Expected 3 models, got {len(available_models)}"

    def test_verify_empty_models_list(self):
        """Test that verification fails when no models are available."""
        global verify_ollama_models

        mock_api_response = {"models": []}

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            all_available, available_models = verify_ollama_models()

            assert all_available is False, "Should return False when no models are available"
            assert len(available_models) == 0, f"Expected 0 models, got {len(available_models)}"

    def test_verify_no_models_section(self):
        """Test that verification fails when models section is missing."""
        global verify_ollama_models

        mock_api_response = {"other_data": "value"}

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            all_available, available_models = verify_ollama_models()

            assert all_available is False, "Should return False when models section is missing"
            assert len(available_models) == 0, f"Expected 0 models, got {len(available_models)}"

    def test_verify_ollama_not_running(self):
        """Test that verification handles Ollama service not running gracefully."""
        global verify_ollama_models

        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError("Connection refused")

            all_available, available_models = verify_ollama_models()

            assert all_available is False, "Should return False when Ollama is not running"
            assert len(available_models) == 0, f"Expected 0 models, got {len(available_models)}"

    def test_verify_api_error(self):
        """Test that verification handles API errors gracefully."""
        global verify_ollama_models

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = requests.HTTPError("Internal Server Error")
            mock_get.return_value = mock_response

            all_available, available_models = verify_ollama_models()

            assert all_available is False, "Should return False when API returns error"
            assert len(available_models) == 0, f"Expected 0 models, got {len(available_models)}"

    def test_verify_invalid_json(self):
        """Test that verification handles invalid JSON response gracefully."""
        global verify_ollama_models

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_get.return_value = mock_response

            all_available, available_models = verify_ollama_models()

            assert all_available is False, "Should return False when JSON is invalid"
            assert len(available_models) == 0, f"Expected 0 models, got {len(available_models)}"

    def test_verify_ollama_connection_timeout(self):
        """Test that verification handles connection timeout gracefully."""
        global verify_ollama_models

        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.Timeout("Request timed out")

            all_available, available_models = verify_ollama_models()

            assert all_available is False, "Should return False on timeout"
            assert len(available_models) == 0, f"Expected 0 models, got {len(available_models)}"


class TestOllamaModelVerifierIntegration:
    """Integration tests for Ollama model verification."""

    def test_full_workflow_with_all_models(self):
        """Test complete workflow: get models, verify all are present."""
        global verify_ollama_models, get_expected_models

        expected_models = get_expected_models()

        with patch('requests.get') as mock_get:
            mock_api_response = {
                "models": [
                    {"name": "qwen3:8b"},
                    {"name": "qwen2.5-coder:7b"},
                    {"name": "deepseek-r1:8b"},
                    {"name": "nemotron-mini"},
                    {"name": "nomic-embed-text"}
                ]
            }

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            # Get available models
            all_available, available_models = verify_ollama_models()

            # Verify all expected models are found
            assert all_available is True, f"Expected all models to be available, got {all_available}"
            assert len(available_models) == 5, f"Expected 5 models, got {len(available_models)}"

    def test_full_workflow_with_missing_models(self):
        """Test complete workflow when some models are missing."""
        global verify_ollama_models, get_expected_models

        expected_models = get_expected_models()

        with patch('requests.get') as mock_get:
            mock_api_response = {
                "models": [
                    {"name": "qwen3:8b"},
                    {"name": "some-other-model"}
                ]
            }

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response
            mock_get.return_value = mock_response

            all_available, available_models = verify_ollama_models()

            assert all_available is False, "Expected verification to fail with missing models"
            assert len(available_models) == 2, f"Expected 2 models, got {len(available_models)}"


if __name__ == '__main__':
    # Run pytest programmatically
    pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(1 if test_failures > 0 else 0)
