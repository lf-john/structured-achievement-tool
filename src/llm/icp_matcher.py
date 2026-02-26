import logging
from typing import Dict, Any, List, Tuple
from src.core.embedding_service import EmbeddingService
from src.core.vector_store import VectorStore

logger = logging.getLogger(__name__)

class OllamaICPMatcher:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        # No collection_name as VectorStore works on a single collection

    def add_icp_profile(self, profile_id: str, profile_data: Dict[str, Any]) -> bool:
        """
        Adds an ICP profile to the vector store.
        profile_data should contain 'description' key with a string summary of the ICP.
        """
        if not profile_data or "description" not in profile_data or not profile_data["description"]:
            logger.warning("Attempted to add an empty or invalid ICP profile.")
            return False

        try:
            description = profile_data["description"]
            # VectorStore.add_document generates its own embedding
            # Merge profile_id into metadata to retain it
            metadata = {"profile_id": profile_id, **profile_data}
            self.vector_store.add_document(text=description, metadata=metadata)
            logger.info(f"Successfully added ICP profile: {profile_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding ICP profile {profile_id}: {e}")
            return False

    def match_icp(self, input_data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Matches input contact/company data against stored ICP profiles
        and returns a fit score and reasoning.
        """
        if not input_data:
            logger.warning("Empty input data for ICP matching.")
            return 0.0, "No input data provided."

        input_description = self._generate_input_description(input_data)
        if not input_description:
            return 0.0, "Could not generate a description from input data."

        try:
            # VectorStore.search takes query_text and handles embedding internally
            results = self.vector_store.search(query_text=input_description, k=1)

            if not results:
                return 0.0, "No ICP profiles found to match against."

            best_match = results[0]
            score = best_match['score']
            profile_id = best_match['metadata'].get('profile_id', 'UNKNOWN')
            reasoning = (f"Matched with ICP profile '{profile_id}' with a similarity score of {score:.2f}. "
                         f"The profile describes: '{best_match['text']}'")

            # Simple score scaling for better user interpretation
            scaled_score = max(00.0, min(1.0, (score + 1) / 2)) # Scale from [-1, 1] to [0, 1]

            return scaled_score, reasoning
        except Exception as e:
            logger.error(f"Error matching ICP: {e}")
            return 0.0, f"An internal error occurred during matching: {e}"

    def _generate_input_description(self, input_data: Dict[str, Any]) -> str:
        """
        Generates a concise description from input contact/company data for embedding.
        """
        parts = []
        if "company_name" in input_data and input_data["company_name"]:
            parts.append(f"Company: {input_data['company_name']}")
        if "industry" in input_data and input_data["industry"]:
            parts.append(f"Industry: {input_data['industry']}")
        if "size" in input_data and input_data["size"]:
            parts.append(f"Size: {input_data['size']}")
        if "contact_role" in input_data and input_data["contact_role"]:
            parts.append(f"Contact role: {input_data['contact_role']}")
        if "pain_points" in input_data and input_data["pain_points"]:
            parts.append(f"Pain points: {input_data['pain_points']}")
        
        if not parts:
            return ""
        
        return ". ".join(parts) + "."
