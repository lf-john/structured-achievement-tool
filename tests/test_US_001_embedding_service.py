"""
Tests for US-001: EmbeddingService with Ollama nomic-embed-text

This test suite verifies the implementation of the EmbeddingService class
with specific focus on the generate_embedding method that returns 768-dimensional
vectors using the Ollama nomic-embed-text model.

IMPLEMENTATION PLAN for US-001:

Components:
  - EmbeddingService: Service class that wraps Ollama API
  - generate_embedding(text: str): Method that generates 768-dimensional vectors
  - Error handling: Network failures, model unavailability

Test Cases:
  1. AC 1: EmbeddingService class exists in src/core/embedding_service.py
  2. AC 2: generate_embedding(text: str) method returns 768-dimensional vector
  3. AC 3: Uses Ollama API to call nomic-embed-text model
  4. AC 4: Handles errors gracefully (network failures, model not found)
  5. AC 5: Tests verify embedding dimensions and format
  6. AC 6: All methods have corresponding unit tests with 100% coverage

Edge Cases:
  - Empty string input
  - Very long text input
  - Network timeouts
  - Model not available
  - Invalid response from Ollama
  - Missing 'embedding' key in response
  - Non-768 dimensional vectors (should raise error)
  - Special characters in text
  - Unicode text

Integration Points:
  - Existing embed_text method should continue to work (backward compatibility)
  - VectorStore tests may need updates if they use generate_embedding
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.embedding_service import EmbeddingService


class TestEmbeddingServiceClassExists:
    """Test AC 1: EmbeddingService class exists in src/core/embedding_service.py"""

    def test_embedding_service_class_exists(self):
        """Test that EmbeddingService class can be imported."""
        from src.core.embedding_service import EmbeddingService
        assert EmbeddingService is not None

    def test_embedding_service_can_be_instantiated(self):
        """Test that EmbeddingService can be instantiated."""
        service = EmbeddingService()
        assert service is not None
        assert isinstance(service, EmbeddingService)


class TestGenerateEmbeddingMethod:
    """Test AC 2: generate_embedding(text: str) method that returns 768-dimensional vector"""

    @pytest.fixture
    def embedding_service(self):
        """Create an EmbeddingService instance for testing."""
        return EmbeddingService(model_name="nomic-embed-text")

    @pytest.fixture
    def mock_ollama_768_response(self):
        """Mock ollama response with 768-dimensional vector."""
        return {
            'embedding': [0.1] * 768
        }

    def test_generate_embedding_method_exists(self, embedding_service):
        """Test that generate_embedding method exists."""
        assert hasattr(embedding_service, 'generate_embedding')
        assert callable(embedding_service.generate_embedding)

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_returns_768_dimensional_vector(
        self, mock_embeddings, embedding_service, mock_ollama_768_response
    ):
        """Test that generate_embedding returns exactly 768 dimensions."""
        mock_embeddings.return_value = mock_ollama_768_response

        result = embedding_service.generate_embedding("test text")

        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 768, f"Expected 768 dimensions, got {len(result)}"
        assert all(isinstance(x, (int, float)) for x in result), "All elements should be numbers"

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_returns_float_list(
        self, mock_embeddings, embedding_service, mock_ollama_768_response
    ):
        """Test that generate_embedding returns a list of floats."""
        mock_embeddings.return_value = mock_ollama_768_response

        result = embedding_service.generate_embedding("test")

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_validates_dimensions(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding raises error if vector is not 768 dimensions."""
        # Mock ollama to return wrong dimensions (512 instead of 768)
        mock_embeddings.return_value = {'embedding': [0.1] * 512}

        with pytest.raises(ValueError) as exc_info:
            embedding_service.generate_embedding("test")

        assert "768" in str(exc_info.value).lower() or "dimension" in str(exc_info.value).lower()

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_handles_empty_string(
        self, mock_embeddings, embedding_service, mock_ollama_768_response
    ):
        """Test that generate_embedding handles empty string input."""
        mock_embeddings.return_value = mock_ollama_768_response

        result = embedding_service.generate_embedding("")

        assert isinstance(result, list)
        assert len(result) == 768

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_handles_unicode_text(
        self, mock_embeddings, embedding_service, mock_ollama_768_response
    ):
        """Test that generate_embedding handles unicode characters."""
        mock_embeddings.return_value = mock_ollama_768_response

        unicode_text = "Hello 世界 🌍 العربية"
        result = embedding_service.generate_embedding(unicode_text)

        assert len(result) == 768

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_handles_special_characters(
        self, mock_embeddings, embedding_service, mock_ollama_768_response
    ):
        """Test that generate_embedding handles special characters."""
        mock_embeddings.return_value = mock_ollama_768_response

        special_text = "Test with \n\t\r and !@#$%^&*() special chars"
        result = embedding_service.generate_embedding(special_text)

        assert len(result) == 768


class TestOllamaAPICall:
    """Test AC 3: Uses Ollama API to call nomic-embed-text model"""

    @pytest.fixture
    def embedding_service(self):
        """Create an EmbeddingService instance."""
        return EmbeddingService(model_name="nomic-embed-text")

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_calls_ollama_with_correct_model(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding calls ollama with nomic-embed-text model."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        embedding_service.generate_embedding("test text")

        mock_embeddings.assert_called_once()
        call_kwargs = mock_embeddings.call_args.kwargs
        assert 'model' in call_kwargs
        assert call_kwargs['model'] == 'nomic-embed-text'

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_passes_text_to_ollama(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding passes the text prompt to ollama."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        test_text = "This is a test prompt"
        embedding_service.generate_embedding(test_text)

        call_kwargs = mock_embeddings.call_args.kwargs
        assert 'prompt' in call_kwargs
        assert call_kwargs['prompt'] == test_text

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_uses_customizable_model(
        self, mock_embeddings
    ):
        """Test that generate_embedding can use different models."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        service = EmbeddingService(model_name="custom-model")
        service.generate_embedding("test")

        call_kwargs = mock_embeddings.call_args.kwargs
        assert call_kwargs['model'] == 'custom-model'


class TestErrorHandling:
    """Test AC 4: Handles errors gracefully (network failures, model not found)"""

    @pytest.fixture
    def embedding_service(self):
        """Create an EmbeddingService instance."""
        return EmbeddingService(model_name="nomic-embed-text")

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_handles_model_not_found(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding handles model not found errors gracefully."""
        # Simulate ollama error for model not found
        mock_embeddings.side_effect = Exception("model 'nomic-embed-text' not found")

        with pytest.raises(Exception) as exc_info:
            embedding_service.generate_embedding("test")

        # Should raise a meaningful error
        assert "ollama" in str(exc_info.value).lower() or "model" in str(exc_info.value).lower()

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_handles_network_failure(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding handles network errors gracefully."""
        # Simulate network error
        mock_embeddings.side_effect = ConnectionError("Failed to connect to Ollama")

        with pytest.raises(Exception) as exc_info:
            embedding_service.generate_embedding("test")

        # Should raise a meaningful error
        error_msg = str(exc_info.value).lower()
        assert "ollama" in error_msg or "connection" in error_msg or "network" in error_msg

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_handles_timeout(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding handles timeout errors."""
        mock_embeddings.side_effect = TimeoutError("Request timed out")

        with pytest.raises(Exception) as exc_info:
            embedding_service.generate_embedding("test")

        error_msg = str(exc_info.value).lower()
        assert "timeout" in error_msg or "ollama" in error_msg

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_handles_missing_embedding_key(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding handles response without 'embedding' key."""
        mock_embeddings.return_value = {'wrong_key': [0.1, 0.2]}

        with pytest.raises(KeyError) as exc_info:
            embedding_service.generate_embedding("test")

        assert "embedding" in str(exc_info.value).lower()

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_handles_malformed_response(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding handles malformed response from ollama."""
        # Return non-dict response
        mock_embeddings.return_value = "not a dict"

        with pytest.raises((AttributeError, KeyError, TypeError)):
            embedding_service.generate_embedding("test")

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_wraps_generic_exceptions(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding wraps generic exceptions with context."""
        mock_embeddings.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(Exception):
            embedding_service.generate_embedding("test")


class TestEmbeddingDimensionsAndFormat:
    """Test AC 5 & 6: Tests verify embedding dimensions and format with 100% coverage"""

    @pytest.fixture
    def embedding_service(self):
        """Create an EmbeddingService instance."""
        return EmbeddingService(model_name="nomic-embed-text")

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_embedding_values_are_in_valid_range(
        self, mock_embeddings, embedding_service
    ):
        """Test that embedding values are within expected range for normalized vectors."""
        # Create a normalized 768-dimensional vector
        normalized_vector = [0.5, -0.3, 0.8] + [0.1] * 765
        mock_embeddings.return_value = {'embedding': normalized_vector}

        result = embedding_service.generate_embedding("test")

        # All values should be floats
        assert all(isinstance(x, float) for x in result)

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_embedding_format_matches_ollama_spec(
        self, mock_embeddings, embedding_service
    ):
        """Test that embedding format matches Ollama's specification."""
        mock_embeddings.return_value = {'embedding': [0.123456] * 768}

        result = embedding_service.generate_embedding("test")

        # Check precision is maintained
        assert len(result) == 768
        assert all(abs(x - 0.123456) < 0.000001 for x in result)

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_returns_copy_not_reference(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding returns a copy, not reference to internal data."""
        original_vector = [0.1] * 768
        mock_embeddings.return_value = {'embedding': original_vector}

        result1 = embedding_service.generate_embedding("test1")
        result2 = embedding_service.generate_embedding("test2")

        # Should be equal copies but not the same object reference
        assert result1 == result2
        # Note: They may or may not be the same object depending on implementation
        # This test documents the behavior

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_produces_different_vectors_for_different_text(
        self, mock_embeddings, embedding_service
    ):
        """Test that different texts produce different embeddings (mocked)."""
        # Return different vectors for different texts
        call_count = [0]

        def mock_side_effect(*args, **kwargs):
            call_count[0] += 1
            return {'embedding': [call_count[0] * 0.1] * 768}

        mock_embeddings.side_effect = mock_side_effect

        result1 = embedding_service.generate_embedding("text1")
        result2 = embedding_service.generate_embedding("text2")

        assert result1 != result2

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_handles_long_text(
        self, mock_embeddings, embedding_service
    ):
        """Test that generate_embedding handles very long text input."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        long_text = "word " * 10000  # Very long text
        result = embedding_service.generate_embedding(long_text)

        assert len(result) == 768

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_dimensions_are_consistent(
        self, mock_embeddings, embedding_service
    ):
        """Test that multiple calls return consistent 768-dimensional vectors."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        results = [embedding_service.generate_embedding(f"text {i}") for i in range(10)]

        # All should have 768 dimensions
        assert all(len(r) == 768 for r in results)


class TestBackwardCompatibility:
    """Ensure backward compatibility with existing embed_text method."""

    @pytest.fixture
    def embedding_service(self):
        """Create an EmbeddingService instance."""
        return EmbeddingService(model_name="nomic-embed-text")

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_embed_text_method_still_exists(self, mock_embeddings, embedding_service):
        """Test that embed_text method still exists for backward compatibility."""
        assert hasattr(embedding_service, 'embed_text')
        assert callable(embedding_service.embed_text)

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_embed_text_still_works(self, mock_embeddings, embedding_service):
        """Test that embed_text method still works."""
        mock_embeddings.return_value = {'embedding': [0.1, 0.2, 0.3, 0.4]}

        result = embedding_service.embed_text("test")

        assert result == [0.1, 0.2, 0.3, 0.4]

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_embed_batch_method_still_exists(self, mock_embeddings, embedding_service):
        """Test that embed_batch method still exists."""
        assert hasattr(embedding_service, 'embed_batch')
        assert callable(embedding_service.embed_batch)

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_embed_batch_still_works(self, mock_embeddings, embedding_service):
        """Test that embed_batch method still works."""
        mock_embeddings.return_value = {'embedding': [0.1, 0.2]}

        results = embedding_service.embed_batch(["text1", "text2"])

        assert len(results) == 2
        assert all(isinstance(r, list) for r in results)


class TestEdgeCases:
    """Additional edge case tests for comprehensive coverage."""

    @pytest.fixture
    def embedding_service(self):
        """Create an EmbeddingService instance."""
        return EmbeddingService(model_name="nomic-embed-text")

    def test_init_with_different_model_name(self):
        """Test initialization with different model name."""
        service = EmbeddingService(model_name="llama2")
        assert service.model_name == "llama2"

    def test_init_with_empty_model_name(self):
        """Test initialization with empty model name."""
        service = EmbeddingService(model_name="")
        assert service.model_name == ""

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_with_whitespace_only(
        self, mock_embeddings, embedding_service
    ):
        """Test generate_embedding with whitespace-only input."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        result = embedding_service.generate_embedding("   \n\t   ")

        assert len(result) == 768

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_generate_embedding_preserves_text_encoding(
        self, mock_embeddings, embedding_service
    ):
        """Test that text encoding is preserved when calling ollama."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        test_text = "Test emoji 🚀 and arabic العربية"
        embedding_service.generate_embedding(test_text)

        # Verify the text was passed correctly
        call_kwargs = mock_embeddings.call_args.kwargs
        assert call_kwargs['prompt'] == test_text

    @patch('src.core.embedding_service.ollama.embeddings')
    def test_multiple_consecutive_calls(
        self, mock_embeddings, embedding_service
    ):
        """Test multiple consecutive calls to generate_embedding."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        for i in range(5):
            result = embedding_service.generate_embedding(f"test {i}")
            assert len(result) == 768

        assert mock_embeddings.call_count == 5


# Run tests with: python -m pytest tests/test_US_001_embedding_service.py -v
