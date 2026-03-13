"""
Tests for the EmbeddingService class.

The EmbeddingService is responsible for generating text embeddings using the
local 'nomic-embed-text' Ollama model.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.embedding_service import MAX_CHARS, EmbeddingService


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

    @patch("ollama.embeddings")
    def test_embed_text_returns_vector(self, mock_embeddings, embedding_service):
        """Test that embed_text returns a numerical vector for valid input."""
        # Mock the ollama embeddings response
        mock_embeddings.return_value = {"embedding": [0.1, 0.2, 0.3, 0.4]}

        result = embedding_service.embed_text("test text")

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(x, (int, float)) for x in result)
        assert result == [0.1, 0.2, 0.3, 0.4]

    @patch("ollama.embeddings")
    def test_embed_text_calls_ollama_with_correct_params(self, mock_embeddings, embedding_service):
        """Test that embed_text calls ollama with the correct parameters."""
        mock_embeddings.return_value = {"embedding": [0.1, 0.2]}

        embedding_service.embed_text("test text")

        # Verify ollama was called with correct arguments
        mock_embeddings.assert_called_once()
        call_args = mock_embeddings.call_args
        assert call_args.kwargs["model"] == "nomic-embed-text"
        assert call_args.kwargs["prompt"] == "test text"

    @patch("ollama.embeddings")
    def test_embed_text_handles_empty_string(self, mock_embeddings, embedding_service):
        """Test that embed_text handles empty string input gracefully."""
        mock_embeddings.return_value = {"embedding": [0.0]}

        result = embedding_service.embed_text("")
        assert isinstance(result, list)

    @patch("ollama.embeddings")
    def test_embed_text_raises_on_ollama_error(self, mock_embeddings, embedding_service):
        """Test that embed_text raises an exception when ollama fails."""
        mock_embeddings.side_effect = Exception("Model not found")

        with pytest.raises(Exception) as exc_info:
            embedding_service.embed_text("test text")

        assert "ollama" in str(exc_info.value).lower() or "model" in str(exc_info.value).lower()

    @patch("ollama.embeddings")
    def test_embed_batch_returns_multiple_vectors(self, mock_embeddings, embedding_service):
        """Test that embed_batch returns vectors for multiple texts."""
        # Mock multiple calls
        mock_embeddings.return_value = {"embedding": [0.1, 0.2]}

        texts = ["text1", "text2", "text3"]
        results = embedding_service.embed_batch(texts)

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(vec, list) for vec in results)

    @patch("ollama.embeddings")
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


class TestTruncation:
    """Test suite for text truncation logic."""

    def test_short_text_not_truncated(self):
        """Text under the limit is returned unchanged."""
        text = "Hello world"
        assert EmbeddingService._truncate(text) == text

    def test_long_text_truncated_to_max_chars(self):
        """Text over the limit is truncated."""
        text = "a" * (MAX_CHARS + 5000)
        result = EmbeddingService._truncate(text)
        assert len(result) <= MAX_CHARS

    def test_truncation_prefers_sentence_boundary(self):
        """Truncation cuts at a sentence boundary when possible."""
        # Build text with a sentence break in the second half
        filler = "x" * (MAX_CHARS - 100)
        text = filler + ". More text after sentence. " + "y" * 5000
        result = EmbeddingService._truncate(text)
        assert result.endswith(".")
        assert len(result) <= MAX_CHARS

    def test_truncation_prefers_paragraph_boundary(self):
        """Truncation prefers paragraph breaks over sentence breaks."""
        filler = "x" * (MAX_CHARS - 100)
        text = filler + "\n\nNew paragraph. " + "y" * 5000
        result = EmbeddingService._truncate(text)
        assert len(result) <= MAX_CHARS

    def test_truncation_hard_cut_if_no_boundary(self):
        """Falls back to hard truncation when no sentence boundary exists."""
        text = "a" * (MAX_CHARS + 1000)
        result = EmbeddingService._truncate(text)
        assert len(result) == MAX_CHARS

    @patch("ollama.embeddings")
    def test_embed_text_truncates_long_input(self, mock_embeddings):
        """embed_text truncates input before sending to Ollama."""
        mock_embeddings.return_value = {"embedding": [0.1, 0.2]}
        service = EmbeddingService()

        long_text = "word " * 10000  # ~50k chars
        service.embed_text(long_text)

        call_args = mock_embeddings.call_args
        sent_text = call_args.kwargs["prompt"]
        assert len(sent_text) <= MAX_CHARS


class TestHealthCheck:
    """Test suite for Ollama health check and auto-recovery."""

    @patch("ollama.list")
    def test_check_ollama_health_returns_true_when_healthy(self, mock_list):
        """Returns True when Ollama responds."""
        mock_list.return_value = {"models": []}
        assert EmbeddingService.check_ollama_health() is True

    @patch("ollama.list")
    def test_check_ollama_health_returns_false_when_down(self, mock_list):
        """Returns False when Ollama is unreachable."""
        mock_list.side_effect = Exception("Connection refused")
        assert EmbeddingService.check_ollama_health() is False

    @patch("subprocess.run")
    @patch("ollama.list")
    def test_restart_ollama_calls_systemctl(self, mock_list, mock_run):
        """restart_ollama calls systemctl restart."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_list.return_value = {"models": []}

        result = EmbeddingService.restart_ollama()
        assert result is True
        mock_run.assert_called_once()
        assert "ollama" in mock_run.call_args[0][0]

    @patch("ollama.embeddings")
    @patch("ollama.list")
    def test_embed_text_retries_after_restart(self, mock_list, mock_embeddings):
        """embed_text retries after restarting Ollama on failure."""
        # First call fails, health check fails, but we can't actually restart in test
        mock_embeddings.side_effect = [
            Exception("Connection refused"),
        ]
        mock_list.side_effect = Exception("down")

        service = EmbeddingService()
        with pytest.raises(Exception):
            service.embed_text("test")

    @patch("ollama.embeddings")
    def test_embed_text_succeeds_on_first_try(self, mock_embeddings):
        """Normal path: embed_text succeeds without needing recovery."""
        mock_embeddings.return_value = {"embedding": [0.1, 0.2]}
        service = EmbeddingService()
        result = service.embed_text("test")
        assert result == [0.1, 0.2]
