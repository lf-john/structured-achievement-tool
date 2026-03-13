import logging
from typing import Any

from src.core.embedding_service import EmbeddingService
from src.core.vector_store import VectorStore

logger = logging.getLogger(__name__)


class OllamaICPMatcher:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        # VectorStore does not manage collections, it operates on a single implicit collection.
        # ICP profiles will be distinguished by metadata.

    def _ensure_collection_exists(self):
        try:
            # Attempt to get the collection info; if it doesn't exist, an error will be raised
            self.vector_store.get_collection(self.collection_name)
        except ValueError:
            # If it doesn't exist, create it
            self.vector_store.create_collection(self.collection_name, 768)  # 768 is the dimension for nomic-embed-text

    def add_icp_profile(self, profile_id: str, profile_data: dict[str, Any]) -> bool:
        """
        Adds an ICP profile to the vector store.
        """
        if not profile_data:
            logger.warning("Attempted to add an empty ICP profile for ID: %s", profile_id)
            return False

        try:
            profile_text = self._serialize_profile_data(profile_data)
            self.embedding_service.embed_text(profile_text)
            metadata = {"profile_id": profile_id, "type": "icp_profile", **profile_data}
            self.vector_store.add_document(profile_text, metadata)
            return True
        except Exception as e:
            logger.error("Error adding ICP profile %s: %s", profile_id, e)
            return False

    def match_icp(self, input_data: dict[str, Any], top_k: int = 1) -> dict[str, Any]:
        """
        Matches input data against stored ICP profiles and returns a fit score and reasoning.
        """
        if not input_data:
            return {"score": 0.0, "reasoning": "No input data provided."}

        try:
            input_text = self._serialize_profile_data(input_data)
            input_embedding = self.embedding_service.embed_text(input_text)

            if input_embedding is None:
                return {"score": 0.0, "reasoning": "Failed to generate embedding for input data."}

            # The VectorStore's search method expects a query_text, not an embedding directly.
            # We'll pass the serialized input_text for searching.
            results = self.vector_store.search(input_text, k=top_k * 5)  # Fetch more to filter down

            icp_results = [res for res in results if res.get("metadata", {}).get("type") == "icp_profile"]

            if not icp_results:
                return {"score": 0.0, "reasoning": "No ICP profiles found for matching."}

            # Sort by similarity (highest score first) and take the top_k
            icp_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            best_match = icp_results[0]

            score = self._calculate_fit_score(best_match.get("score", 0.0))
            reasoning = self._generate_reasoning(input_data, best_match)

            return {"score": score, "reasoning": reasoning, "matched_profile": best_match.get("metadata")}

        except Exception as e:
            logger.error("Error matching ICP: %s", e)
            return {"score": 0.0, "reasoning": f"An error occurred during matching: {e}"}

    def _serialize_profile_data(self, data: dict[str, Any]) -> str:
        """
        Converts a dictionary of profile data into a string for embedding.
        """
        # A simple serialization, can be made more sophisticated
        return " ".join(f"{k}: {v}" for k, v in data.items())

    def _calculate_fit_score(self, similarity: float) -> float:
        """
        Converts a similarity score (e.g., cosine similarity) into a fit score (0-100).
        """
        # Assuming similarity is between 0 and 1.
        # This can be adjusted based on desired scaling and distribution.
        return round(similarity * 100, 2)

    def _generate_reasoning(self, input_data: dict[str, Any], matched_profile: dict[str, Any]) -> str:
        """
        Generates reasoning for the ICP fit based on input and matched profile.
        """
        profile_metadata = matched_profile.get("metadata", {})
        similarity = matched_profile.get("similarity", 0.0)

        reasoning = (
            f"The input data shows a similarity of {similarity:.2f} with ICP profile "
            f"'{profile_metadata.get('name', profile_metadata.get('profile_id', 'N/A'))}' (ID: {profile_metadata.get('profile_id', 'N/A')}). "
        )
        reasoning += "Key matching points: "

        # Example: Compare common fields (can be enhanced with LLM for better reasoning)
        matching_fields = []
        for key, input_value in input_data.items():
            profile_value = profile_metadata.get(key)
            if profile_value and input_value == profile_value:
                matching_fields.append(key)

        if matching_fields:
            reasoning += f"Exact matches on: {', '.join(matching_fields)}. "
        else:
            reasoning += "No exact field matches found, but overall semantic similarity is high. "

        reasoning += f"This profile represents a {profile_metadata.get('description', 'typical ICP')}. "

        return reasoning
