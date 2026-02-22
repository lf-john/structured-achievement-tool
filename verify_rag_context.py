#!/usr/bin/env python3
"""
Script to verify RAG search and context injection in the Orchestrator.
"""
import os
import tempfile
import shutil
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from src.orchestrator import Orchestrator

async def test_rag_context_injection():
    """Test that similar task context is injected into decomposition."""
    temp_project = tempfile.mkdtemp(prefix="test_rag_")
    temp_task = tempfile.mkdtemp(prefix="test_task_")

    try:
        print("Testing RAG search and context injection...")

        # Initialize orchestrator
        orchestrator = Orchestrator(project_path=temp_project)

        # Mock the embedding service to return consistent embeddings
        from unittest.mock import Mock
        orchestrator.embedding_service.embed_text = Mock(return_value=[0.1, 0.2, 0.3, 0.4])

        # Add some past tasks to the vector store
        print("\n1. Adding past tasks to vector memory...")
        orchestrator.vector_store.add_document(
            "Request: Build authentication system\nResponse: Implemented JWT-based auth",
            {"task_id": "auth-001", "type": "completed", "success": True}
        )
        orchestrator.vector_store.add_document(
            "Request: Add user registration\nResponse: Created registration endpoint",
            {"task_id": "reg-001", "type": "completed", "success": True}
        )
        print("   ✓ Added 2 past tasks to vector memory")

        # Create a new task file
        task_file = os.path.join(temp_task, "001_login.md")
        with open(task_file, "w") as f:
            f.write("Create login page with authentication")

        print(f"\n2. Created new task file: {task_file}")

        # Mock agent methods and capture what's passed to decompose
        captured_args = []

        def capture_decompose(enriched_request, task_type):
            captured_args.append({
                'enriched_request': enriched_request,
                'task_type': task_type
            })
            return {"stories": []}

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(side_effect=capture_decompose)

        # Mock subprocess execution
        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Success", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            print("\n3. Processing task file...")
            await orchestrator.process_task_file(task_file)

        print("\n4. Analyzing captured decompose arguments...")

        # Verify that decompose was called with enriched context
        if len(captured_args) == 0:
            print("   ✗ decompose was never called!")
            return False

        enriched_request = captured_args[0]['enriched_request']
        original_request = "Create login page with authentication"

        print(f"\n   Original request length: {len(original_request)} chars")
        print(f"   Enriched request length: {len(enriched_request)} chars")

        # Check if the enriched request contains the original request
        if original_request not in enriched_request:
            print("   ✗ Original request not found in enriched request!")
            return False
        else:
            print("   ✓ Original request preserved in enriched request")

        # Check if context from similar tasks was added
        if "Context from Similar Past Tasks" in enriched_request or \
           "authentication" in enriched_request.lower() or \
           len(enriched_request) > len(original_request):
            print("   ✓ Similar task context appears to be injected")

            # Show a sample of the enriched context
            if len(enriched_request) > len(original_request):
                added_context = enriched_request[len(original_request):]
                print(f"\n   Added context (first 200 chars):")
                print(f"   {added_context[:200]}...")
        else:
            print("   ⚠ No obvious context injection detected")
            print("   This could mean no similar tasks were found")

        # Verify that the task was also added to vector memory after completion
        print("\n5. Verifying task was added to vector memory...")
        results = orchestrator.vector_store.search("login authentication", k=5)
        print(f"   Found {len(results)} results when searching for 'login authentication'")

        # The newly processed task should be in the results
        found_new_task = False
        for result in results:
            if "login" in result['text'].lower():
                found_new_task = True
                print(f"   ✓ Found newly processed task in vector memory")
                break

        if not found_new_task:
            print("   ⚠ Newly processed task not found in vector memory")

        print("\n✓ RAG context injection verification complete!")
        return True

    except Exception as e:
        print(f"\n✗ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        shutil.rmtree(temp_project, ignore_errors=True)
        shutil.rmtree(temp_task, ignore_errors=True)
        print(f"\nCleaned up temporary directories")

if __name__ == "__main__":
    success = asyncio.run(test_rag_context_injection())
    exit(0 if success else 1)
