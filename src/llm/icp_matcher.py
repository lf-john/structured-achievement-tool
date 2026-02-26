import logging
from typing import Dict, List, Tuple
from src.llm.embedding_service import EmbeddingService
from src.core.vector_store import VectorStore

logger = logging.getLogger(__name__)

class OllamaICPMatcher:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore):
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def add_icp_profile(self, profile_name: str, description: str, examples: List[str]):
        profile_text = f"{profile_name} {description} {' '.join(examples)}"
        try:
            vector = self.embedding_service.embed_text(profile_text)
            payload = {
                "profile_name": profile_name,
                "description": description,
                "examples": examples
            }
            self.vector_store.add_document(text=profile_text, metadata=payload)
            logger.info(f"ICP profile '{profile_name}' added.")
        except Exception as e:
            logger.error(f"Error adding ICP profile '{profile_name}': {e}")
            raise

    def match_icp(self, contact_data: Dict, company_data: Dict) -> Tuple[float, str]:
        input_text = self._format_input_data(contact_data, company_data)

        if not input_text.strip():
            return 0.0, "No significant data provided for matching."

        try:
            input_vector = self.embedding_service.embed_text(input_text)
        except Exception as e:
            logger.error(f"Error processing embeddings for input data: {e}")
            return 0.0, f"Error processing embeddings: {e}"

        try:
            search_results = self.vector_store.search(query_text=input_text, k=1)
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return 0.0, f"Error searching ICP profiles: {e}"

        if not search_results:
            return 0.0, "No ICP profiles available to match against."

        # Assuming search_vectors returns a list of objects with 'payload' and 'score'
        best_match = search_results[0]
        score = best_match.get("score", 0.0)
        profile_name = best_match.get("metadata", {}).get("profile_name", "Unknown Profile")
        profile_reasoning = best_match.get("metadata", {}).get("reasoning", "No specific reasoning provided for this profile.")

        reasoning = f"Best match: {profile_name}. Fit score: {score:.2f}. Details: {profile_reasoning}"

        # Adjust score and reasoning for edge cases like very low similarity
        if score < 0.1: # Threshold for a very poor fit
            reasoning = f"Low fit for any ICP profile found. {profile_reasoning}"

        return score, reasoning

    def _format_input_data(self, contact_data: Dict, company_data: Dict) -> str:
        """Helper to format contact and company data into a single string."""
        formatted_data_parts = []
        if contact_data:
            formatted_data_parts.append("Contact: " + ", ".join(f"{k}: {v}" for k, v in contact_data.items()))
        if company_data:
            formatted_data_parts.append("Company: " + ", ".join(f"{k}: {v}" for k, v in company_data.items()))
        return ". ".join(formatted_data_parts)
