"""
IMPLEMENTATION PLAN for US-004:

Components:
  - src/llm/icp_matcher.py:
    - OllamaICPMatcher class:
      - __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore)
      - add_icp_profile(self, profile_name: str, description: str, examples: list[str])
      - match_icp(self, contact_data: dict, company_data: dict) -> tuple[float, str]
  - Existing EmbeddingService (src/llm/embedding_service.py)
  - Existing VectorStore (src/db/vector_store.py)

Data Flow:
  1. User provides contact and company data to match_icp.
  2. match_icp converts data into textual representation.
  3. OllamaICPMatcher uses EmbeddingService to generate embeddings for input data.
  4. OllamaICPMatcher queries VectorStore for similar ICP profiles.
  5. Based on similarity, calculates ICP fit score and generates reasoning.
  6. match_icp returns fit score and reasoning.

Integration Points:
  - Potentially src/llm_router.py or src/orchestrator_v2.py for higher-level workflow integration.
  - Direct dependency on EmbeddingService and VectorStore; these will be mocked in tests.

Edge Cases:
  - Empty contact_data or company_data.
  - No ICP profiles stored in VectorStore.
  - Poor quality input data leading to low confidence scores.
  - EmbeddingService or VectorStore errors (graceful degradation/error handling).

Test Cases:
  1. AC 1: ICP matcher workflow is operational.
     - test_icp_matcher_is_operational_with_valid_data: Verify that match_icp returns a score and reasoning.
     - test_add_icp_profile_stores_profile_correctly: Verify add_icp_profile calls vector_store correctly.
  2. AC 2: Outputs ICP fit score and reasoning based on input data.
     - test_match_icp_outputs_score_and_reasoning_types: Verify output types (float, str).
     - test_match_icp_calculates_score_based_on_similarity: Verify score reflects similarity to stored profiles.

Edge Cases Tests:
  - test_match_icp_with_empty_input_data: Handles empty input gracefully.
  - test_match_icp_when_no_profiles_exist: Returns appropriate result when no profiles are stored.
  - test_match_icp_with_poor_fit_data: Returns low score for non-matching data.
  - test_icp_matcher_handles_embedding_service_failure: Graceful handling of embedding service errors.
"""
import pytest
from unittest.mock import MagicMock, patch

# These imports are expected to fail as the modules/classes don't exist yet
from src.llm.icp_matcher import OllamaICPMatcher
from src.llm.embedding_service import EmbeddingService
from src.db.vector_store import VectorStore

class TestOllamaICPMatcher:
    @pytest.fixture
    def mock_embedding_service(self):
        """Mocks the EmbeddingService."""
        mock = MagicMock(spec=EmbeddingService)
        mock.embed_text.return_value = [0.1] * 768  # Simulate an embedding vector
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Mocks the VectorStore."""
        mock = MagicMock(spec=VectorStore)
        # Simulate an empty search result by default
        mock.search_vectors.return_value = []
        return mock

    @pytest.fixture
    def icp_matcher(self, mock_embedding_service, mock_vector_store):
        """Provides an instance of OllamaICPMatcher with mocked dependencies."""
        return OllamaICPMatcher(mock_embedding_service, mock_vector_store)

    def test_icp_matcher_is_operational_with_valid_data(self, icp_matcher, mock_vector_store, mock_embedding_service):
        """
        AC 1: Verify that the ICP matcher workflow is operational and returns a score and reasoning
        for valid input when an ICP profile exists.
        """
        # Set up a mock profile in the vector store for search
        mock_vector_store.search_vectors.return_value = [
            MagicMock(payload={'profile_name': 'Tech Startup', 'reasoning': 'Strong fit for tech startup'}),
        ]
        mock_embedding_service.embed_text.return_value = [0.9] * 768 # Simulate a good match

        contact_data = {"email": "john@example.com", "title": "CEO"}
        company_data = {"name": "InnovateX", "industry": "Software", "employees": 50}

        score, reasoning = icp_matcher.match_icp(contact_data, company_data)

        assert isinstance(score, float)
        assert isinstance(reasoning, str)
        assert score >= 0.0
        assert "Strong fit" in reasoning  # Expect reasoning from the mock payload
        mock_embedding_service.embed_text.assert_called()
        mock_vector_store.search_vectors.assert_called()

    def test_add_icp_profile_stores_profile_correctly(self, icp_matcher, mock_vector_store, mock_embedding_service):
        """
        AC 1: Verify that add_icp_profile correctly interacts with the mocked VectorStore
        to store a new ICP profile.
        """
        profile_name = "Enterprise SaaS"
        description = "Large companies, 1000+ employees, B2B SaaS"
        examples = ["Salesforce", "Microsoft Dynamics"]

        icp_matcher.add_icp_profile(profile_name, description, examples)

        mock_embedding_service.embed_text.assert_called_with(f"{profile_name} {description} {' '.join(examples)}")
        mock_vector_store.add_vector.assert_called_once()
        args, _ = mock_vector_store.add_vector.call_args
        assert 'vector' in args[0]
        assert args[0]['payload']['profile_name'] == profile_name
        assert args[0]['payload']['description'] == description
        assert args[0]['payload']['examples'] == examples

    def test_match_icp_outputs_score_and_reasoning_types(self, icp_matcher, mock_vector_store, mock_embedding_service):
        """
        AC 2: Verify that match_icp outputs an ICP fit score (float) and reasoning (string).
        """
        mock_vector_store.search_vectors.return_value = [
            MagicMock(payload={'profile_name': 'Retail E-commerce', 'reasoning': 'Good for e-commerce stores'}),
        ]
        mock_embedding_service.embed_text.return_value = [0.8] * 768

        contact_data = {"name": "Alice"}
        company_data = {"industry": "Retail"}

        score, reasoning = icp_matcher.match_icp(contact_data, company_data)

        assert isinstance(score, float)
        assert isinstance(reasoning, str)
        assert score >= 0.0

    def test_match_icp_calculates_score_based_on_similarity(self, icp_matcher, mock_vector_store, mock_embedding_service):
        """
        AC 2: Verify that the fit score is calculated based on the similarity to stored ICP profiles.
        This is tested by simulating different similarity scores from the vector store.
        """
        # Simulate a high similarity match
        mock_vector_store.search_vectors.return_value = [
            MagicMock(payload={'profile_name': 'High Fit Profile', 'reasoning': 'Very similar'}),
        ]
        mock_embedding_service.embed_text.return_value = [0.95] * 768 # High embedding match

        contact_data_high = {"topic": "AI", "role": "Engineer"}
        company_data_high = {"tech": "ML", "size": 100}

        score_high, _ = icp_matcher.match_icp(contact_data_high, company_data_high)

        # Simulate a lower similarity match
        mock_vector_store.search_vectors.return_value = [
            MagicMock(payload={'profile_name': 'Low Fit Profile', 'reasoning': 'Not very similar'}),
        ]
        mock_embedding_service.embed_text.return_value = [0.1] * 768 # Low embedding match

        contact_data_low = {"topic": "Finance", "role": "Analyst"}
        company_data_low = {"tech": "Banking", "size": 500}

        score_low, _ = icp_matcher.match_icp(contact_data_low, company_data_low)

        assert score_high > score_low # Expect higher score for higher similarity

    def test_match_icp_with_empty_input_data(self, icp_matcher, mock_vector_store, mock_embedding_service):
        """
        Edge Case: Ensure match_icp handles empty contact/company data gracefully,
        returning a default low score and appropriate reasoning.
        """
        mock_vector_store.search_vectors.return_value = [
            MagicMock(payload={'profile_name': 'Some Profile', 'reasoning': 'Default reasoning'}),
        ]
        mock_embedding_service.embed_text.return_value = [0.0] * 768 # Simulate very low embedding

        score, reasoning = icp_matcher.match_icp({}, {})

        assert isinstance(score, float)
        assert isinstance(reasoning, str)
        assert score < 0.1 # Expect a very low score
        assert "No significant data" in reasoning or "Unable to determine" in reasoning # Example reasoning

    def test_match_icp_when_no_profiles_exist(self, icp_matcher, mock_vector_store, mock_embedding_service):
        """
        Edge Case: Test that if no ICP profiles exist in the vector store, it returns
        a default low score and reasoning indicating no profiles to match against.
        """
        mock_vector_store.search_vectors.return_value = [] # No profiles
        mock_embedding_service.embed_text.return_value = [0.5] * 768

        contact_data = {"email": "test@test.com"}
        company_data = {"name": "TestCo"}

        score, reasoning = icp_matcher.match_icp(contact_data, company_data)

        assert isinstance(score, float)
        assert isinstance(reasoning, str)
        assert score == 0.0 # Expect a zero score if no profiles to match
        assert "No ICP profiles available" in reasoning

    def test_match_icp_with_poor_fit_data(self, icp_matcher, mock_vector_store, mock_embedding_service):
        """
        Edge Case: Test that data not matching any stored ICP profile returns a low score.
        """
        mock_vector_store.search_vectors.return_value = [
            MagicMock(payload={'profile_name': 'Finance Only', 'reasoning': 'Strong fit for finance'}),
        ]
        mock_embedding_service.embed_text.return_value = [0.05] * 768 # Simulate very low similarity

        contact_data = {"topic": "Art", "role": "Designer"}
        company_data = {"industry": "Entertainment"}

        score, reasoning = icp_matcher.match_icp(contact_data, company_data)

        assert isinstance(score, float)
        assert isinstance(reasoning, str)
        assert score < 0.2 # Expect a low score

    @patch('src.llm.embedding_service.EmbeddingService') # Patch at the module level where it's imported
    def test_icp_matcher_handles_embedding_service_failure(self, MockEmbeddingService, icp_matcher, mock_vector_store):
        """
        Edge Case: Ensure ICPMatcher handles EmbeddingService errors gracefully,
        e.g., by returning a default low score and an error message.
        """
        # Configure the mock to raise an exception
        MockEmbeddingService.return_value.embed_text.side_effect = Exception("Embedding service unavailable")
        
        # We need to re-instantiate icp_matcher to use the patched EmbeddingService
        icp_matcher_with_error = OllamaICPMatcher(MockEmbeddingService(), mock_vector_store)

        contact_data = {"email": "error@example.com"}
        company_data = {"name": "ErrorCo"}

        score, reasoning = icp_matcher_with_error.match_icp(contact_data, company_data)

        assert isinstance(score, float)
        assert isinstance(reasoning, str)
        assert score == 0.0  # Expect a default low score on error
        assert "Error processing embeddings" in reasoning or "Embedding service unavailable" in reasoning

