import pytest
from unittest.mock import MagicMock, patch
import sys

"""
IMPLEMENTATION PLAN for US-005:

Components:
  - src/mautic/engagement_scorer.py:
    - EngagementScorer class: Main entry point for the workflow.
    - _get_mautic_history(user_id): Fetches Mautic engagement history (mocked).
    - _generate_embedding(text): Uses EmbeddingService to generate embeddings.
    - _classify_engagement_tier(embedding): Compares embedding with tier embeddings using VectorStore.
    - score_user_engagement(user_id): Orchestrates the scoring process.

Test Cases:
  1. [AC 1] Engagement scorer workflow is operational. -> Should successfully score a user with valid history.
  2. [AC 1] Engagement scorer workflow is operational. -> Should handle empty Mautic history gracefully.
  3. [AC 2] Outputs correct engagement tier based on Mautic history. -> Should classify "hot" engagement correctly.
  4. [AC 2] Outputs correct engagement tier based on Mautic history. -> Should classify "warm" engagement correctly.
  5. [AC 2] Outputs correct engagement tier based on Mautic history. -> Should classify "cold" engagement correctly.
  6. [AC 2] Outputs correct engagement tier based on Mautic history. -> Should handle EmbeddingService failure.
  7. [AC 2] Outputs correct engagement tier based on Mautic history. -> Should handle VectorStore search failure.

Edge Cases:
  - Empty Mautic history for a user.
  - EmbeddingService returning an error or empty embedding.
  - VectorStore search returning no matches.
  - Mautic history resulting in an ambiguous embedding (tie in similarity).
"""

class TestEngagementScorer:
    # Mock dependencies for the EngagementScorer
    @pytest.fixture
    def mock_embedding_service(self):
        with patch('src.core.embedding_service.EmbeddingService') as MockService:
            instance = MockService.return_value
            instance.create_embedding.return_value = [0.1] * 768 # Dummy embedding
            yield instance

    @pytest.fixture
    def mock_vector_store(self):
        with patch('src.core.vector_store.VectorStore') as MockStore:
            instance = MockStore.return_value
            # Default mock for classification: return 'cold' if no specific setup
            instance.similarity_search_and_return_scores.return_value = [
                ({'tier': 'cold'}, 0.9)
            ]
            yield instance

    @pytest.fixture
    def engagement_scorer(self, mock_embedding_service, mock_vector_store):
        # We need to import the EngagementScorer class here
        # This import will fail initially as the file/class doesn't exist
        from src.mautic.engagement_scorer import EngagementScorer
        return EngagementScorer(mock_embedding_service, mock_vector_store)

    def test_should_classify_hot_engagement_when_relevant_history_provided(self, engagement_scorer, mock_embedding_service, mock_vector_store):
        """
        [AC 2] Outputs correct engagement tier based on Mautic history.
        Should classify "hot" engagement correctly.
        """
        user_id = "user-hot-123"
        mock_embedding_service.create_embedding.return_value = [0.9] * 768 # Simulate a "hot" embedding
        mock_vector_store.similarity_search_and_return_scores.return_value = [
            ({'tier': 'hot'}, 0.95),
            ({'tier': 'warm'}, 0.7),
            ({'tier': 'cold'}, 0.3),
        ]

        # Assuming _get_mautic_history will be mocked internally or passed
        # For this test, we are focusing on the scoring logic after history is obtained
        with patch('src.mautic.engagement_scorer.EngagementScorer._get_mautic_history', return_value=["hot interaction 1", "hot interaction 2"]):
            tier = engagement_scorer.score_user_engagement(user_id)
            assert tier == "hot"
            mock_embedding_service.create_embedding.assert_called_once()
            mock_vector_store.similarity_search_and_return_scores.assert_called_once()

    def test_should_classify_warm_engagement_when_relevant_history_provided(self, engagement_scorer, mock_embedding_service, mock_vector_store):
        """
        [AC 2] Outputs correct engagement tier based on Mautic history.
        Should classify "warm" engagement correctly.
        """
        user_id = "user-warm-456"
        mock_embedding_service.create_embedding.return_value = [0.5] * 768 # Simulate a "warm" embedding
        mock_vector_store.similarity_search_and_return_scores.return_value = [
            ({'tier': 'warm'}, 0.9),
            ({'tier': 'cold'}, 0.6),
            ({'tier': 'hot'}, 0.4),
        ]

        with patch('src.mautic.engagement_scorer.EngagementScorer._get_mautic_history', return_value=["warm interaction 1"]):
            tier = engagement_scorer.score_user_engagement(user_id)
            assert tier == "warm"

    def test_should_classify_cold_engagement_when_relevant_history_provided(self, engagement_scorer, mock_embedding_service, mock_vector_store):
        """
        [AC 2] Outputs correct engagement tier based on Mautic history.
        Should classify "cold" engagement correctly.
        """
        user_id = "user-cold-789"
        mock_embedding_service.create_embedding.return_value = [0.1] * 768 # Simulate a "cold" embedding
        mock_vector_store.similarity_search_and_return_scores.return_value = [
            ({'tier': 'cold'}, 0.8),
            ({'tier': 'warm'}, 0.3),
            ({'tier': 'hot'}, 0.1),
        ]

        with patch('src.mautic.engagement_scorer.EngagementScorer._get_mautic_history', return_value=["cold interaction 1"]):
            tier = engagement_scorer.score_user_engagement(user_id)
            assert tier == "cold"

    def test_should_return_default_tier_when_empty_mautic_history(self, engagement_scorer, mock_embedding_service, mock_vector_store):
        """
        [AC 1] Engagement scorer workflow is operational.
        Should handle empty Mautic history gracefully, returning a default tier.
        """
        user_id = "user-empty-history"
        mock_vector_store.similarity_search_and_return_scores.return_value = [
            ({'tier': 'cold'}, 0.9) # Assume 'cold' is the default for no history
        ]

        with patch('src.mautic.engagement_scorer.EngagementScorer._get_mautic_history', return_value=[]):
            tier = engagement_scorer.score_user_engagement(user_id)
            assert tier == "cold" # Or 'unclassified', depending on design. 'cold' is a reasonable default.
            # No embedding should be created for empty history if logic prevents it,
            # but for failing test, we assume it proceeds to return a default if no history.
            # mock_embedding_service.create_embedding.assert_not_called() # This would be true in actual implementation
            mock_vector_store.similarity_search_and_return_scores.assert_called_once() # We still expect a default lookup.

    def test_should_handle_embedding_service_failure_gracefully(self, engagement_scorer, mock_embedding_service, mock_vector_store):
        """
        [AC 2] Outputs correct engagement tier based on Mautic history.
        Should handle EmbeddingService failure gracefully.
        """
        user_id = "user-embedding-fail"
        mock_embedding_service.create_embedding.side_effect = Exception("Ollama service down")
        mock_vector_store.similarity_search_and_return_scores.return_value = [
            ({'tier': 'cold'}, 0.9) # Assume 'cold' is the default on error
        ]

        with patch('src.mautic.engagement_scorer.EngagementScorer._get_mautic_history', return_value=["some history"]):
            tier = engagement_scorer.score_user_engagement(user_id)
            assert tier == "cold" # Expecting a default/fallback tier
            mock_embedding_service.create_embedding.assert_called_once()
            mock_vector_store.similarity_search_and_return_scores.assert_called_once() # A default lookup might still happen


    def test_should_handle_vector_store_search_failure_gracefully(self, engagement_scorer, mock_embedding_service, mock_vector_store):
        """
        [AC 2] Outputs correct engagement tier based on Mautic history.
        Should handle VectorStore search failure gracefully.
        """
        user_id = "user-vector-store-fail"
        mock_vector_store.similarity_search_and_return_scores.side_effect = Exception("DB error")
        # Ensure create_embedding works, as the failure is in vector store
        mock_embedding_service.create_embedding.return_value = [0.5] * 768

        with patch('src.mautic.engagement_scorer.EngagementScorer._get_mautic_history', return_value=["some history"]):
            tier = engagement_scorer.score_user_engagement(user_id)
            assert tier == "cold" # Expecting a default/fallback tier
            mock_embedding_service.create_embedding.assert_called_once()
            mock_vector_store.similarity_search_and_return_scores.assert_called_once()

    def test_workflow_operational_with_valid_history(self, engagement_scorer, mock_embedding_service, mock_vector_store):
        """
        [AC 1] Engagement scorer workflow is operational.
        Ensures the overall workflow functions as expected with valid inputs.
        """
        user_id = "user-operational-test"
        mock_embedding_service.create_embedding.return_value = [0.7] * 768
        mock_vector_store.similarity_search_and_return_scores.return_value = [
            ({'tier': 'warm'}, 0.85)
        ]

        with patch('src.mautic.engagement_scorer.EngagementScorer._get_mautic_history', return_value=["recent login", "product view"]):
            tier = engagement_scorer.score_user_engagement(user_id)
            assert tier == "warm"
            mock_embedding_service.create_embedding.assert_called_once()
            mock_vector_store.similarity_search_and_return_scores.assert_called_once()

# This is a placeholder for running the tests and capturing failures
# In a real scenario, pytest would manage this. For the agent to verify
# failing tests, we need a simple way to exit with 1 on error.
if __name__ == '__main__':
    pytest.main(['tests/US-005_engagement_scorer.test.py'])
    # This part won't be executed in the agent's pytest run, but for manual check.
    # The agent will run pytest externally.
    # For a guaranteed failing exit for this phase, simply having an import error is enough.
    # If the above pytest.main runs successfully, it means the import error was somehow resolved,
    # which is not the goal for TDD-RED.
    # So, we expect the import error to cause pytest to fail directly.
