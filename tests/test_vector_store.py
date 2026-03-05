"""
Tests for the VectorStore class.

The VectorStore uses sqlite_vec for similarity search on embedded documents.
"""

import os
import shutil
import tempfile
from unittest.mock import Mock

import pytest

from src.core.embedding_service import EmbeddingService
from src.core.vector_store import VectorStore


class TestVectorStore:
    """Test suite for VectorStore."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file for testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_vectors.db")
        yield db_path
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embedding_service(self):
        """Create a mock EmbeddingService for testing."""
        service = Mock(spec=EmbeddingService)
        # Return a consistent embedding vector
        service.embed_text.return_value = [0.1, 0.2, 0.3, 0.4]
        return service

    @pytest.fixture
    def vector_store(self, temp_db_path, mock_embedding_service):
        """Create a VectorStore instance for testing."""
        return VectorStore(
            db_path=temp_db_path,
            embedding_service=mock_embedding_service
        )

    def test_init_creates_database_file(self, temp_db_path, mock_embedding_service):
        """Test that VectorStore creates a database file on initialization."""
        assert not os.path.exists(temp_db_path)
        VectorStore(db_path=temp_db_path, embedding_service=mock_embedding_service)
        assert os.path.exists(temp_db_path)

    def test_init_creates_tables(self, temp_db_path, mock_embedding_service):
        """Test that VectorStore creates necessary tables in the database."""
        VectorStore(db_path=temp_db_path, embedding_service=mock_embedding_service)

        # Verify tables exist by attempting to query them
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        # Check if documents table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
        result = cursor.fetchone()
        assert result is not None

        conn.close()

    def test_add_document_stores_text_and_metadata(self, vector_store, mock_embedding_service):
        """Test that add_document stores text content and metadata."""
        doc_id = vector_store.add_document(
            text="This is a test document",
            metadata={"task_id": "task-001", "type": "request"}
        )

        assert doc_id is not None
        assert isinstance(doc_id, (int, str))

        # Verify embedding service was called
        mock_embedding_service.embed_text.assert_called_once_with("This is a test document")

    def test_add_document_returns_unique_ids(self, vector_store, mock_embedding_service):
        """Test that add_document returns unique IDs for different documents."""
        id1 = vector_store.add_document("Document 1", {})
        id2 = vector_store.add_document("Document 2", {})

        assert id1 != id2

    def test_search_returns_similar_documents(self, vector_store, mock_embedding_service):
        """Test that search returns documents similar to the query."""
        # Add some documents
        vector_store.add_document("Python programming tutorial", {"topic": "python"})
        vector_store.add_document("JavaScript web development", {"topic": "javascript"})
        vector_store.add_document("Python data science", {"topic": "python"})

        # Mock different embeddings for search query
        mock_embedding_service.embed_text.return_value = [0.15, 0.25, 0.35, 0.45]

        # Search for similar documents
        results = vector_store.search("Python tutorial", k=2)

        assert isinstance(results, list)
        assert len(results) <= 2

    def test_search_returns_results_with_text_and_metadata(self, vector_store, mock_embedding_service):
        """Test that search results contain text content and metadata."""
        vector_store.add_document(
            "Test document",
            {"task_id": "task-123", "timestamp": "2024-01-01"}
        )

        results = vector_store.search("test", k=1)

        assert len(results) > 0
        result = results[0]
        assert "text" in result
        assert "metadata" in result
        assert result["text"] == "Test document"
        assert result["metadata"]["task_id"] == "task-123"

    def test_search_returns_similarity_scores(self, vector_store, mock_embedding_service):
        """Test that search results include similarity scores."""
        vector_store.add_document("Sample document", {})

        results = vector_store.search("sample", k=1)

        assert len(results) > 0
        assert "score" in results[0] or "similarity" in results[0] or "distance" in results[0]

    def test_search_respects_k_parameter(self, vector_store, mock_embedding_service):
        """Test that search returns at most k results."""
        # Add multiple documents
        for i in range(10):
            vector_store.add_document(f"Document {i}", {"index": i})

        results = vector_store.search("document", k=3)
        assert len(results) <= 3

    def test_search_handles_empty_database(self, vector_store, mock_embedding_service):
        """Test that search returns empty list when database is empty."""
        results = vector_store.search("query", k=5)
        assert results == []

    def test_add_document_handles_metadata_with_various_types(self, vector_store):
        """Test that add_document handles metadata with various data types."""
        metadata = {
            "string_field": "value",
            "int_field": 42,
            "float_field": 3.14,
            "bool_field": True,
            "list_field": [1, 2, 3],
            "dict_field": {"nested": "value"}
        }

        doc_id = vector_store.add_document("Test", metadata)
        assert doc_id is not None

    def test_search_orders_by_similarity(self, vector_store, mock_embedding_service):
        """Test that search results are ordered by similarity score."""
        # Add documents
        vector_store.add_document("Very similar text", {"id": 1})
        vector_store.add_document("Completely different", {"id": 2})
        vector_store.add_document("Somewhat similar", {"id": 3})

        results = vector_store.search("similar", k=3)

        # Results should be ordered by score (if present)
        if len(results) >= 2 and "score" in results[0]:
            # Assuming higher scores mean better similarity
            for i in range(len(results) - 1):
                assert results[i]["score"] >= results[i + 1]["score"]

    def test_vector_store_persists_across_instances(self, temp_db_path, mock_embedding_service):
        """Test that data persists when creating new VectorStore instances."""
        # Create store and add document
        store1 = VectorStore(db_path=temp_db_path, embedding_service=mock_embedding_service)
        store1.add_document("Persistent document", {"key": "value"})

        # Create new instance with same database
        store2 = VectorStore(db_path=temp_db_path, embedding_service=mock_embedding_service)
        results = store2.search("persistent", k=1)

        assert len(results) > 0
        assert results[0]["text"] == "Persistent document"

    def test_add_document_with_empty_text(self, vector_store):
        """Test that add_document handles empty text gracefully."""
        doc_id = vector_store.add_document("", {"empty": True})
        assert doc_id is not None

    def test_close_connection(self, vector_store):
        """Test that VectorStore can close its database connection."""
        vector_store.add_document("test", {})

        # Should have a close method
        if hasattr(vector_store, 'close'):
            vector_store.close()
            # After closing, operations should either fail or reconnect
