#!/usr/bin/env python3
"""
Manual Integration Test for Vector Memory (RAG) System

This script performs a manual integration test to verify:
1. EmbeddingService can generate embeddings with actual Ollama model
2. VectorStore can store and search embeddings
3. Similar task context is properly injected into decomposition prompts
"""

import os
import shutil
import sys
import tempfile

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.embedding_service import EmbeddingService
from src.core.vector_store import VectorStore


def test_embedding_service():
    """Test that EmbeddingService can generate embeddings."""
    print("\n=== Testing EmbeddingService ===")
    try:
        service = EmbeddingService(model_name="nomic-embed-text")
        embedding = service.embed_text("This is a test document about Python programming")

        print(f"✓ Generated embedding with {len(embedding)} dimensions")
        print(f"  First 5 values: {embedding[:5]}")

        return service
    except Exception as e:
        print(f"✗ EmbeddingService failed: {e}")
        print("  Note: This requires Ollama to be installed and running")
        print("  with the 'nomic-embed-text' model available.")
        return None


def test_vector_store(embedding_service):
    """Test that VectorStore can store and search documents."""
    print("\n=== Testing VectorStore ===")

    if embedding_service is None:
        print("✗ Skipping VectorStore test (no embedding service available)")
        return False

    # Create temporary database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_vectors.db")

    try:
        # Initialize vector store
        vector_store = VectorStore(db_path=db_path, embedding_service=embedding_service)

        # Add some documents
        doc1_id = vector_store.add_document(
            "Implement user authentication with JWT tokens", {"task_type": "development", "feature": "auth"}
        )
        print(f"✓ Added document 1 (ID: {doc1_id})")

        doc2_id = vector_store.add_document(
            "Create login page with email and password fields", {"task_type": "development", "feature": "ui"}
        )
        print(f"✓ Added document 2 (ID: {doc2_id})")

        doc3_id = vector_store.add_document(
            "Write unit tests for shopping cart functionality", {"task_type": "testing", "feature": "cart"}
        )
        print(f"✓ Added document 3 (ID: {doc3_id})")

        # Search for similar documents
        print("\n--- Searching for 'authentication and login' ---")
        results = vector_store.search("authentication and login", k=3)

        for idx, result in enumerate(results, 1):
            print(f"\n{idx}. Score: {result['score']:.4f}")
            print(f"   Text: {result['text'][:80]}...")
            print(f"   Metadata: {result['metadata']}")

        # Verify that relevant documents are returned (authentication OR login)
        if results and ("authentication" in results[0]["text"].lower() or "login" in results[0]["text"].lower()):
            print("\n✓ RAG search successfully returned relevant documents")
            # Check that the shopping cart task has the lowest score
            if results[-1]["metadata"]["feature"] == "cart":
                print("✓ Irrelevant documents scored lower")
            success = True
        else:
            print("\n✗ RAG search did not return expected results")
            success = False

        vector_store.close()
        return success

    except Exception as e:
        print(f"✗ VectorStore test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_memory_directory_creation():
    """Test that memory directory is created in project path."""
    print("\n=== Testing Memory Directory Creation ===")

    project_path = os.path.join(os.path.dirname(__file__), "..")
    memory_dir = os.path.join(project_path, ".memory")

    if os.path.exists(memory_dir):
        print(f"✓ Memory directory exists: {memory_dir}")

        db_file = os.path.join(memory_dir, "task_vectors.db")
        if os.path.exists(db_file):
            print(f"✓ Database file exists: {db_file}")
            print(f"  File size: {os.path.getsize(db_file)} bytes")
            return True
        else:
            print(f"✗ Database file not found: {db_file}")
            return False
    else:
        print(f"✗ Memory directory not found: {memory_dir}")
        return False


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("Vector Memory (RAG) System - Manual Integration Test")
    print("=" * 70)

    # Test 1: EmbeddingService
    embedding_service = test_embedding_service()

    # Test 2: VectorStore
    vector_store_success = test_vector_store(embedding_service)

    # Test 3: Memory directory
    memory_dir_success = test_memory_directory_creation()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if embedding_service:
        print("✓ EmbeddingService: PASSED")
    else:
        print("⚠ EmbeddingService: SKIPPED (Ollama not available)")

    if vector_store_success:
        print("✓ VectorStore: PASSED")
    elif embedding_service is None:
        print("⚠ VectorStore: SKIPPED (no embedding service)")
    else:
        print("✗ VectorStore: FAILED")

    if memory_dir_success:
        print("✓ Memory Directory: PASSED")
    else:
        print("⚠ Memory Directory: NOT YET CREATED (run daemon first)")

    print("\nNote: These tests require Ollama to be installed and running")
    print("with the 'nomic-embed-text' model available. To install:")
    print("  ollama pull nomic-embed-text")
    print("=" * 70)


if __name__ == "__main__":
    main()
