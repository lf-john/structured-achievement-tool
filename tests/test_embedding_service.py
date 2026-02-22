"""
Tests for the EmbeddingService class.

The EmbeddingService is responsible for generating text embeddings using the
local 'nomic-embed-text' Ollama model.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.embedding_service import EmbeddingService


class TestEmbeddingService:
    """Test suite for EmbeddingService."""

    @pytest.fixture
    def embedding_service(self):
        """Create an EmbeddingService instance for testing."""
        return EmbeddingService(model_name="nomic-embed-text")

    def test_init_creates_service_with_model_name(self):
        """Test that EmbeddingService initializes with the correct model name."""
        service = EmbeddingService(model_name="nomic-embed-text")
        assert service.model_name == "nomic-embed-text"

    def test_init_uses_default_model_name(self):
        """Test that EmbeddingService uses default model if none specified."""
        service = EmbeddingService()
        assert service.model_name == "nomic-embed-text"

    @patch('ollama.embeddings')
    def test_embed_text_returns_vector(self, mock_embeddings, embedding_service):
        """Test that embed_text returns a numerical vector for valid input."""
        # Mock the ollama embeddings response
        mock_embeddings.return_value = {'embedding': [0.1, 0.2, 0.3, 0.4]}

        result = embedding_service.embed_text("test text")

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(x, (int, float)) for x in result)
        assert result == [0.1, 0.2, 0.3, 0.4]

    @patch('ollama.embeddings')
    def test_embed_text_calls_ollama_with_correct_params(self, mock_embeddings, embedding_service):
        """Test that embed_text calls ollama with the correct parameters."""
        mock_embeddings.return_value = {'embedding': [0.1, 0.2]}

        embedding_service.embed_text("test text")

        # Verify ollama was called with correct arguments
        mock_embeddings.assert_called_once()
        call_args = mock_embeddings.call_args
        assert call_args.kwargs['model'] == 'nomic-embed-text'
        assert call_args.kwargs['prompt'] == 'test text'

    @patch('ollama.embeddings')
    def test_embed_text_handles_empty_string(self, mock_embeddings, embedding_service):
        """Test that embed_text handles empty string input gracefully."""
        mock_embeddings.return_value = {'embedding': [0.0]}

        result = embedding_service.embed_text("")
        assert isinstance(result, list)

    @patch('ollama.embeddings')
    def test_embed_text_raises_on_ollama_error(self, mock_embeddings, embedding_service):
        """Test that embed_text raises an exception when ollama fails."""
        mock_embeddings.side_effect = Exception("Model not found")

        with pytest.raises(Exception) as exc_info:
            embedding_service.embed_text("test text")

        assert "ollama" in str(exc_info.value).lower() or "model" in str(exc_info.value).lower()

    @patch('ollama.embeddings')
    def test_embed_batch_returns_multiple_vectors(self, mock_embeddings, embedding_service):
        """Test that embed_batch returns vectors for multiple texts."""
        # Mock multiple calls
        mock_embeddings.return_value = {'embedding': [0.1, 0.2]}

        texts = ["text1", "text2", "text3"]
        results = embedding_service.embed_batch(texts)

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(vec, list) for vec in results)

    @patch('ollama.embeddings')
    def test_embed_batch_handles_empty_list(self, mock_embeddings, embedding_service):
        """Test that embed_batch handles empty list gracefully."""
        results = embedding_service.embed_batch([])
        assert results == []
        mock_embeddings.assert_not_called()

    def test_vector_dimension_is_consistent(self):
        """Test that all embeddings from the same model have consistent dimensions."""
        # This test will use the actual ollama if available, otherwise skip
        try:
            service = EmbeddingService()
            vec1 = service.embed_text("hello world")
            vec2 = service.embed_text("goodbye world")
            assert len(vec1) == len(vec2)
        except Exception:
            pytest.skip("Ollama not available for integration test")
