"""
EmbeddingService for generating text embeddings using Ollama.

This service uses the local 'nomic-embed-text' model via Ollama
to generate vector embeddings for text content.

Handles text truncation to stay within the model's context window
and checks Ollama health before making requests.
"""

import json
import logging
import subprocess
from typing import List, Optional
import ollama

logger = logging.getLogger(__name__)

# nomic-embed-text has a 2048-token context window.
# Conservative character limit (~4 chars per token on average).
MAX_CHARS = 7500


class EmbeddingService:
    """
    Service for generating text embeddings using Ollama.

    Uses the 'nomic-embed-text' model by default to generate
    numerical vector representations of text.
    Automatically truncates long text to fit within the model's context window.
    Checks Ollama availability and attempts auto-recovery on failure.
    """

    def __init__(self, model_name: str = "nomic-embed-text"):
        """
        Initialize the EmbeddingService.

        Args:
            model_name: Name of the Ollama model to use for embeddings.
                       Defaults to 'nomic-embed-text'.
        """
        self.model_name = model_name

    @staticmethod
    def _truncate(text: str, max_chars: int = MAX_CHARS) -> str:
        """Truncate text to fit within the model's context window.

        Tries to cut at a sentence boundary; falls back to hard truncation.
        """
        if len(text) <= max_chars:
            return text

        truncated = text[:max_chars]
        # Try to cut at last sentence boundary
        for sep in ("\n\n", "\n", ". ", "! ", "? "):
            idx = truncated.rfind(sep)
            if idx > max_chars // 2:
                return truncated[:idx + len(sep)].rstrip()
        return truncated

    @staticmethod
    def check_ollama_health() -> bool:
        """Check if Ollama is running and responsive.

        Returns:
            True if Ollama is healthy, False otherwise.
        """
        try:
            ollama.list()
            return True
        except Exception:
            return False

    @staticmethod
    def restart_ollama() -> bool:
        """Attempt to restart the Ollama service via systemctl.

        Returns:
            True if restart succeeded, False otherwise.
        """
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "ollama"],
                capture_output=True, timeout=30
            )
            if result.returncode == 0:
                # Wait for service to become ready
                import time
                for _ in range(10):
                    time.sleep(1)
                    if EmbeddingService.check_ollama_health():
                        logger.info("Ollama restarted successfully")
                        return True
            logger.warning("Ollama restart returned %d", result.returncode)
            return False
        except Exception as e:
            logger.warning("Failed to restart Ollama: %s", e)
            return False

    def _call_ollama(self, text: str) -> dict:
        """Call Ollama embeddings API with auto-recovery on failure.

        Truncates input, checks health, and retries once after restarting
        Ollama if the first attempt fails.
        """
        text = self._truncate(text)

        try:
            return ollama.embeddings(model=self.model_name, prompt=text)
        except Exception as first_error:
            logger.warning("Ollama embedding failed: %s — checking health", first_error)
            if not self.check_ollama_health():
                logger.info("Ollama is down, attempting restart")
                if self.restart_ollama():
                    try:
                        return ollama.embeddings(model=self.model_name, prompt=text)
                    except Exception as retry_error:
                        raise Exception(f"Ollama embedding failed after restart: {retry_error}")
            raise Exception(f"Ollama embedding failed: {first_error}")

    def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single text string.

        Args:
            text: The text to embed. Automatically truncated if too long.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            Exception: If the Ollama command fails or returns an error.
        """
        response = self._call_ollama(text)
        return response.get('embedding', [])

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate a 768-dimensional embedding vector for a single text string.

        This method specifically validates that the returned embedding is
        exactly 768 dimensions, as expected from the nomic-embed-text model.

        Args:
            text: The text to embed. Automatically truncated if too long.

        Returns:
            A list of exactly 768 floats representing the embedding vector.

        Raises:
            ValueError: If the embedding is not 768 dimensions.
            KeyError: If the response doesn't contain 'embedding' key.
            ConnectionError: If network connection to Ollama fails.
            TimeoutError: If the request times out.
            Exception: For other Ollama API errors.
        """
        try:
            response = self._call_ollama(text)

            # Extract embedding from response
            if 'embedding' not in response:
                raise KeyError("Response from Ollama API missing 'embedding' key")

            embedding = response['embedding']

            # Convert all values to float
            embedding_floats = [float(x) for x in embedding]

            # Validate dimension count
            if len(embedding_floats) != 768:
                raise ValueError(
                    f"Expected 768-dimensional embedding, but got {len(embedding_floats)} dimensions"
                )

            return embedding_floats

        except ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Ollama: {e}")
        except TimeoutError as e:
            raise TimeoutError(f"Ollama request timed out: {e}")
        except KeyError as e:
            raise KeyError(f"Invalid Ollama response format: {e}")
        except ValueError as e:
            # Re-raise ValueError as-is (dimension validation)
            raise
        except Exception as e:
            # Wrap other exceptions with context
            raise Exception(f"Ollama embedding generation failed: {e}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embedding vectors for multiple text strings.

        Args:
            texts: A list of text strings to embed.

        Returns:
            A list of embedding vectors, one for each input text.
        """
        if not texts:
            return []

        embeddings = []
        for text in texts:
            embedding = self.embed_text(text)
            embeddings.append(embedding)

        return embeddings
