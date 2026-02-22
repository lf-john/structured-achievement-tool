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
