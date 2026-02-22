"""
EmbeddingService for generating text embeddings using Ollama.

This service uses the local 'nomic-embed-text' model via Ollama
to generate vector embeddings for text content.
"""

import json
from typing import List
import ollama


class EmbeddingService:
    """
    Service for generating text embeddings using Ollama.

    Uses the 'nomic-embed-text' model by default to generate
    numerical vector representations of text.
    """

    def __init__(self, model_name: str = "nomic-embed-text"):
        """
        Initialize the EmbeddingService.

        Args:
            model_name: Name of the Ollama model to use for embeddings.
                       Defaults to 'nomic-embed-text'.
        """
        self.model_name = model_name

    def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single text string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            Exception: If the Ollama command fails or returns an error.
        """
        try:
            response = ollama.embeddings(model=self.model_name, prompt=text)
            return response.get('embedding', [])
        except Exception as e:
            raise Exception(f"Ollama embedding failed: {e}")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate a 768-dimensional embedding vector for a single text string.

        This method specifically validates that the returned embedding is
        exactly 768 dimensions, as expected from the nomic-embed-text model.

        Args:
            text: The text to embed.

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
            response = ollama.embeddings(model=self.model_name, prompt=text)

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
