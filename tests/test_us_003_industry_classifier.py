"""
IMPLEMENTATION PLAN for US-003:

Components:
  - src/industry_classifier.py: Main module for industry classification.
    - IndustryClassifier class: Encapsulates classification logic.
    - classify_industry(company_description: str) -> str: Public method to classify.
    - _embed_description(description: str) -> List[float]: Internal method to get embeddings via EmbeddingService.
    - _load_industry_embeddings() -> Dict[str, List[float]]: Loads pre-defined industry embeddings.
    - _calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float: Calculates similarity.
    - _determine_best_match(desc_embedding: List[float], industry_embeddings: Dict[str, List[float]]) -> str: Finds best match.
  - src/llm/embedding_service.py: (Existing) Used by IndustryClassifier to generate text embeddings.

Data Flow:
  - Input: company_description (string)
  - IndustryClassifier.classify_industry receives description.
  - Calls _embed_description to get embedding using EmbeddingService.
  - Loads pre-defined industry embeddings (e.g., healthcare, higher_ed, manufacturing, other).
  - Compares description embedding to industry embeddings using similarity metric.
  - Returns the best matching industry category string.

Integration Points:
  - IndustryClassifier will depend on src.llm.embedding_service.EmbeddingService.
  - No direct modifications to existing orchestrator or daemon, but the classifier will be callable.

Edge Cases:
  - Empty company description: Should return 'other' or a default.
  - Description not clearly matching any category: Should return 'other'.
  - EmbeddingService failure: Should gracefully handle, possibly returning 'other' or raising a specific custom error.

Test Cases:
  1. [AC 1] Industry classification workflow is operational. -> test_classify_industry_returns_string_for_valid_input
  2. [AC 2] Correct industry category is output based on company description.
     -> test_classify_industry_correctly_identifies_healthcare
     -> test_classify_industry_correctly_identifies_higher_ed
     -> test_classify_industry_correctly_identifies_manufacturing
     -> test_classify_industry_identifies_other_for_unmatched_description

Edge Cases Test Cases:
  - test_classify_industry_handles_empty_description
  - test_classify_industry_handles_ollama_embedding_service_failure
"""

import pytest
from unittest.mock import MagicMock, patch
import sys

# Mock embeddings for testing. In a real scenario, these would come from Ollama.
MOCK_HEALTHCARE_EMBEDDING = [0.1] * 768
MOCK_HIGHER_ED_EMBEDDING = [0.2] * 768
MOCK_MANUFACTURING_EMBEDDING = [0.3] * 768
MOCK_OTHER_EMBEDDING = [0.4] * 768

# Define industry categories and their mock embeddings for similarity comparison
MOCK_INDUSTRY_EMBEDDINGS = {
    "healthcare": MOCK_HEALTHCARE_EMBEDDING,
    "higher_ed": MOCK_HIGHER_ED_EMBEDDING,
    "manufacturing": MOCK_MANUFACTURING_EMBEDDING,
    "other": MOCK_OTHER_EMBEDDING,
}

# This import will fail because src/industry_classifier.py does not exist yet.
# This is intentional for TDD-RED phase.
from src.industry_classifier import IndustryClassifier, IndustryClassificationError

class TestIndustryClassifier:
    @pytest.fixture
    def mock_embedding_service(self):
        with patch("src.llm.embedding_service.EmbeddingService") as MockEmbeddingService:
            instance = MockEmbeddingService.return_value
            # Configure the mock to return specific embeddings for specific inputs
            instance.embed_text.side_effect = lambda text: {
                "description about hospitals and clinics": MOCK_HEALTHCARE_EMBEDDING,
                "description about universities and colleges": MOCK_HIGHER_ED_EMBEDDING,
                "description about factories and production lines": MOCK_MANUFACTURING_EMBEDDING,
                "description about a totally unrelated topic": MOCK_OTHER_EMBEDDING,
                "some general company description": MOCK_OTHER_EMBEDDING,
                "": MOCK_OTHER_EMBEDDING, # For empty description
            }.get(text, MOCK_OTHER_EMBEDDING) # Default to other for unknown inputs
            yield instance

    @pytest.fixture
    def classifier(self, mock_embedding_service):
        # Pass the mock embedding service instance to the classifier during initialization
        return IndustryClassifier(embedding_service=mock_embedding_service, industry_embeddings=MOCK_INDUSTRY_EMBEDDINGS)

    # AC 1: Industry classification workflow is operational.
    def test_classify_industry_returns_string_for_valid_input(self, classifier):
        company_description = "description about hospitals and clinics"
        result = classifier.classify_industry(company_description)
        assert isinstance(result, str)
        assert result in MOCK_INDUSTRY_EMBEDDINGS.keys()

    # AC 2: Correct industry category is output based on company description.
    def test_classify_industry_correctly_identifies_healthcare(self, classifier, mock_embedding_service):
        company_description = "description about hospitals and clinics"
        expected_category = "healthcare"
        result = classifier.classify_industry(company_description)
        assert result == expected_category
        mock_embedding_service.embed_text.assert_called_with(company_description)

    def test_classify_industry_correctly_identifies_higher_ed(self, classifier, mock_embedding_service):
        company_description = "description about universities and colleges"
        expected_category = "higher_ed"
        result = classifier.classify_industry(company_description)
        assert result == expected_category
        mock_embedding_service.embed_text.assert_called_with(company_description)

    def test_classify_industry_correctly_identifies_manufacturing(self, classifier, mock_embedding_service):
        company_description = "description about factories and production lines"
        expected_category = "manufacturing"
        result = classifier.classify_industry(company_description)
        assert result == expected_category
        mock_embedding_service.embed_text.assert_called_with(company_description)

    def test_classify_industry_identifies_other_for_unmatched_description(self, classifier, mock_embedding_service):
        company_description = "description about a totally unrelated topic"
        expected_category = "other"
        result = classifier.classify_industry(company_description)
        assert result == expected_category
        mock_embedding_service.embed_text.assert_called_with(company_description)

    # Edge Cases
    def test_classify_industry_handles_empty_description(self, classifier, mock_embedding_service):
        company_description = ""
        expected_category = "other" # Assuming 'other' as default for empty input
        result = classifier.classify_industry(company_description)
        assert result == expected_category
        mock_embedding_service.embed_text.assert_called_with(company_description)

    def test_classify_industry_handles_ollama_embedding_service_failure(self, mock_embedding_service):
        mock_embedding_service.embed_text.side_effect = Exception("Ollama service down")
        classifier = IndustryClassifier(embedding_service=mock_embedding_service, industry_embeddings=MOCK_INDUSTRY_EMBEDDINGS)
        
        # Expecting an exception to be raised, or a default to 'other' if handled internally
        # For now, let's assume it raises our custom error
        with pytest.raises(IndustryClassificationError, match="Failed to get embeddings"):
            classifier.classify_industry("any description")
        mock_embedding_service.embed_text.assert_called_with("any description")

# This is a placeholder for running tests and collecting failures.
# In a real pytest execution, pytest handles exit codes.
# This part ensures the script itself exits with a non-zero code if run directly
# and there's some kind of failure in test discovery or initial imports.
# For TDD-RED, the import error from src.industry_classifier will cause an early exit.
if __name__ == "__main__":
    # This block won't be reached if the import fails at the top.
    # It's here for completeness as per instructions, but pytest will manage exits.
    print("This script is meant to be run with pytest.")
    # Simulate a failure to ensure non-zero exit in this direct execution context
    sys.exit(1)
