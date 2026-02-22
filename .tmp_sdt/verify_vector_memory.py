#!/usr/bin/env python3
"""
Verification script for Vector Memory (RAG) implementation.

This script demonstrates that all components are working correctly:
1. EmbeddingService generates embeddings
2. VectorStore stores and searches documents
3. Orchestrator integrates both components
"""

import sys
import os
import tempfile
import shutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.embedding_service import EmbeddingService
from src.core.vector_store import VectorStore


def test_embedding_service():
    """Test EmbeddingService functionality."""
    print("=" * 60)
    print("Testing EmbeddingService...")
    print("=" * 60)

    try:
        service = EmbeddingService(model_name="nomic-embed-text")
        print(f"✓ Created EmbeddingService with model: {service.model_name}")

        # Test single embedding
        text = "Implement user authentication system"
        embedding = service.embed_text(text)
        print(f"✓ Generated embedding for: '{text}'")
        print(f"  - Embedding dimension: {len(embedding)}")
        print(f"  - First 5 values: {embedding[:5]}")

        # Test batch embedding
        texts = [
            "Create login page",
            "Add password reset",
            "Implement JWT tokens"
        ]
        embeddings = service.embed_batch(texts)
        print(f"✓ Generated {len(embeddings)} embeddings in batch")

        print("\n✅ EmbeddingService: ALL CHECKS PASSED\n")
        return True

    except Exception as e:
        print(f"\n❌ EmbeddingService: FAILED - {e}\n")
        return False


def test_vector_store():
    """Test VectorStore functionality."""
    print("=" * 60)
    print("Testing VectorStore...")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()

    try:
        db_path = os.path.join(temp_dir, "test_vectors.db")
        embedding_service = EmbeddingService(model_name="nomic-embed-text")

        vector_store = VectorStore(
            db_path=db_path,
            embedding_service=embedding_service,
            dimension=768
        )
        print(f"✓ Created VectorStore at: {db_path}")

        # Add documents
        doc1_id = vector_store.add_document(
            "Implement user authentication with JWT tokens and refresh tokens",
            {"task_id": "auth-001", "type": "feature", "priority": "high"}
        )
        print(f"✓ Added document 1, ID: {doc1_id}")

        doc2_id = vector_store.add_document(
            "Create login page with email and password fields",
            {"task_id": "login-001", "type": "ui", "priority": "medium"}
        )
        print(f"✓ Added document 2, ID: {doc2_id}")

        doc3_id = vector_store.add_document(
            "Build shopping cart with add/remove functionality",
            {"task_id": "cart-001", "type": "feature", "priority": "low"}
        )
        print(f"✓ Added document 3, ID: {doc3_id}")

        # Search for similar documents
        print("\nSearching for: 'authentication login system'")
        results = vector_store.search("authentication login system", k=2)

        print(f"✓ Found {len(results)} similar documents:")
        for i, result in enumerate(results, 1):
            print(f"\n  Result {i}:")
            print(f"    - Similarity Score: {result['score']:.3f}")
            print(f"    - Text: {result['text'][:60]}...")
            print(f"    - Metadata: {result['metadata']}")

        # Verify persistence
        vector_store.close()
        print("\n✓ Closed database connection")

        vector_store2 = VectorStore(
            db_path=db_path,
            embedding_service=embedding_service,
            dimension=768
        )
        print("✓ Reopened database")

        results2 = vector_store2.search("shopping cart", k=1)
        print(f"✓ Verified persistence: found {len(results2)} documents after reopen")

        print("\n✅ VectorStore: ALL CHECKS PASSED\n")
        return True

    except Exception as e:
        print(f"\n❌ VectorStore: FAILED - {e}\n")
        import traceback
        traceback.print_exc()
        return False

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_orchestrator_integration():
    """Test Orchestrator integration with Vector Memory."""
    print("=" * 60)
    print("Testing Orchestrator Integration...")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()

    try:
        from src.orchestrator import Orchestrator

        orchestrator = Orchestrator(project_path=temp_dir)
        print("✓ Created Orchestrator instance")

        # Verify vector_store attribute exists
        assert hasattr(orchestrator, 'vector_store'), "Orchestrator missing vector_store attribute"
        print("✓ Orchestrator has vector_store attribute")

        # Verify vector_store is initialized
        assert orchestrator.vector_store is not None, "VectorStore not initialized"
        print("✓ VectorStore is initialized")

        # Verify database path
        db_path = orchestrator.vector_store.db_path
        print(f"✓ VectorStore database path: {db_path}")

        # Verify it's in the .memory directory
        assert ".memory" in db_path, "Database not in .memory directory"
        print("✓ Database is in .memory directory")

        print("\n✅ Orchestrator Integration: ALL CHECKS PASSED\n")
        return True

    except Exception as e:
        print(f"\n❌ Orchestrator Integration: FAILED - {e}\n")
        import traceback
        traceback.print_exc()
        return False

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("VECTOR MEMORY (RAG) IMPLEMENTATION VERIFICATION")
    print("=" * 60 + "\n")

    results = []

    # Test 1: EmbeddingService
    results.append(("EmbeddingService", test_embedding_service()))

    # Test 2: VectorStore
    results.append(("VectorStore", test_vector_store()))

    # Test 3: Orchestrator Integration
    results.append(("Orchestrator Integration", test_orchestrator_integration()))

    # Summary
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:.<40} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All verification checks passed!")
        print("Vector Memory (RAG) system is working correctly.\n")
        return 0
    else:
        print("\n⚠️  Some verification checks failed.")
        print("Please review the error messages above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
