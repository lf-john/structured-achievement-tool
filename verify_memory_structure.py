#!/usr/bin/env python3
"""
Script to verify that the VectorStore creates the proper memory directory structure.
"""
import os
import tempfile
import shutil
from src.orchestrator import Orchestrator

def test_memory_structure():
    """Test that Orchestrator creates the correct memory directory structure."""
    # Create a temporary project directory
    temp_project = tempfile.mkdtemp(prefix="test_project_")

    try:
        print(f"Testing memory directory creation in: {temp_project}")

        # Initialize orchestrator without specifying vector_db_path
        # This should use default path in .memory/task_vectors.db
        orchestrator = Orchestrator(project_path=temp_project)

        # Check that .memory directory was created
        memory_dir = os.path.join(temp_project, ".memory")
        if os.path.exists(memory_dir):
            print(f"✓ Memory directory created: {memory_dir}")
        else:
            print(f"✗ Memory directory NOT found at: {memory_dir}")
            return False

        # Check that database file exists
        expected_db_path = os.path.join(memory_dir, "task_vectors.db")
        if os.path.exists(expected_db_path):
            print(f"✓ Database file created: {expected_db_path}")
        else:
            print(f"✗ Database file NOT found at: {expected_db_path}")
            return False

        # Verify the orchestrator is using the correct path
        if orchestrator.vector_store.db_path == expected_db_path:
            print(f"✓ VectorStore is using correct path: {orchestrator.vector_store.db_path}")
        else:
            print(f"✗ VectorStore is using wrong path: {orchestrator.vector_store.db_path}")
            print(f"  Expected: {expected_db_path}")
            return False

        # Test adding a document to ensure everything works
        try:
            from unittest.mock import Mock
            orchestrator.embedding_service.embed_text = Mock(return_value=[0.1, 0.2, 0.3, 0.4])
            doc_id = orchestrator.vector_store.add_document(
                "Test document for verification",
                {"test": True}
            )
            print(f"✓ Successfully added test document (ID: {doc_id})")

            # Test searching
            results = orchestrator.vector_store.search("test", k=1)
            if len(results) > 0:
                print(f"✓ Successfully searched and found {len(results)} result(s)")
            else:
                print("✗ Search returned no results")
                return False

        except Exception as e:
            print(f"✗ Error testing vector store operations: {e}")
            return False

        print("\n✓ All memory structure checks passed!")
        return True

    finally:
        # Cleanup
        shutil.rmtree(temp_project, ignore_errors=True)
        print(f"\nCleaned up temporary directory: {temp_project}")

if __name__ == "__main__":
    success = test_memory_structure()
    exit(0 if success else 1)
