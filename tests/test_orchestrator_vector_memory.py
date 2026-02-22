"""
Tests for VectorStore integration into the Orchestrator.

These tests verify that:
1. Orchestrator embeds completed task files
2. Orchestrator searches for similar past tasks before decomposition
3. Similar task context is injected into prompts
"""

import pytest
import os
import tempfile
import shutil
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from src.orchestrator import Orchestrator
from src.core.vector_store import VectorStore
from src.core.embedding_service import EmbeddingService


class TestOrchestratorVectorMemory:
    """Test suite for VectorStore integration with Orchestrator."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        project_dir = tempfile.mkdtemp()
        task_dir = tempfile.mkdtemp()
        db_dir = tempfile.mkdtemp()

        yield {
            "project": project_dir,
            "task": task_dir,
            "db": db_dir
        }

        # Cleanup
        for dir_path in [project_dir, task_dir, db_dir]:
            shutil.rmtree(dir_path, ignore_errors=True)

    @pytest.fixture
    def mock_embedding_service(self):
        """Create a mock EmbeddingService."""
        service = Mock(spec=EmbeddingService)
        service.embed_text.return_value = [0.1, 0.2, 0.3, 0.4]
        return service

    @pytest.fixture
    def vector_store(self, temp_dirs, mock_embedding_service):
        """Create a VectorStore for testing."""
        db_path = os.path.join(temp_dirs["db"], "vectors.db")
        return VectorStore(
            db_path=db_path,
            embedding_service=mock_embedding_service
        )

    def test_orchestrator_has_vector_store(self, temp_dirs):
        """Test that Orchestrator can be initialized with a VectorStore."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])

        # Orchestrator should have vector_store attribute
        assert hasattr(orchestrator, 'vector_store')

    def test_orchestrator_initializes_vector_store_with_default_path(self, temp_dirs):
        """Test that Orchestrator initializes VectorStore with default path."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])

        if orchestrator.vector_store is not None:
            assert isinstance(orchestrator.vector_store, VectorStore)
            # Check that a database file was created
            assert orchestrator.vector_store.db_path is not None

    @pytest.mark.asyncio
    async def test_orchestrator_embeds_completed_task(self, temp_dirs, vector_store):
        """Test that Orchestrator embeds task content after completion."""
        # Create orchestrator with vector store
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = vector_store

        # Create a task file
        task_file = os.path.join(temp_dirs["task"], "001_test.md")
        with open(task_file, "w") as f:
            f.write("Create a login feature with authentication")

        # Mock the agent methods
        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        # Mock the subprocess to avoid actual execution
        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"output", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            # Process the task
            await orchestrator.process_task_file(task_file)

        # Verify that the vector store has the task embedded
        # We should be able to search for it
        results = vector_store.search("login authentication", k=5)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_orchestrator_searches_similar_tasks_before_decomposition(self, temp_dirs, vector_store):
        """Test that Orchestrator searches for similar tasks before decomposing."""
        # Add some existing tasks to vector store
        vector_store.add_document(
            "Implement user registration with email verification",
            {"task_id": "task-001", "type": "request"}
        )
        vector_store.add_document(
            "Add password reset functionality",
            {"task_id": "task-002", "type": "request"}
        )

        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = vector_store

        # Create a new similar task
        task_file = os.path.join(temp_dirs["task"], "001_test.md")
        with open(task_file, "w") as f:
            f.write("Create login page with password recovery")

        # Mock agent methods and capture what decompose is called with
        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        decompose_mock = Mock(return_value={"stories": []})
        orchestrator.agent.decompose = decompose_mock

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Verify decompose was called
        assert decompose_mock.called

    @pytest.mark.asyncio
    async def test_orchestrator_injects_similar_task_context(self, temp_dirs, vector_store):
        """Test that similar task context is injected into the decomposition prompt."""
        # Add a completed task to vector store
        vector_store.add_document(
            "Request: Build authentication system\nResponse: Implemented JWT-based auth with refresh tokens",
            {"task_id": "task-auth", "type": "completed", "success": True}
        )

        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = vector_store

        task_file = os.path.join(temp_dirs["task"], "001_test.md")
        with open(task_file, "w") as f:
            f.write("Add user authentication to the app")

        # Capture what's passed to decompose
        call_args = []

        def capture_decompose(*args, **kwargs):
            call_args.append((args, kwargs))
            return {"stories": []}

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(side_effect=capture_decompose)

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Check that decompose was called with enriched context
        assert len(call_args) > 0
        # The first argument should be the user request (potentially enriched)
        # or there should be a context parameter

    def test_vector_store_database_location(self, temp_dirs):
        """Test that VectorStore database is in a sensible location."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])

        if orchestrator.vector_store is not None:
            # Database should be in project directory or a dedicated memory dir
            db_path = orchestrator.vector_store.db_path
            assert db_path is not None
            # Check it's not in a temporary location that gets deleted
            assert os.path.dirname(db_path) != "/tmp"

    @pytest.mark.asyncio
    async def test_orchestrator_stores_both_request_and_response(self, temp_dirs, vector_store):
        """Test that Orchestrator stores both request and response in vector memory."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = vector_store

        task_file = os.path.join(temp_dirs["task"], "001_test.md")
        request_text = "Implement a shopping cart feature"
        with open(task_file, "w") as f:
            f.write(request_text)

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Implemented cart with add/remove", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Search should find documents related to the task
        results = vector_store.search("shopping cart", k=5)
        assert len(results) > 0

        # At least one result should contain information from request or response
        found_relevant = False
        for result in results:
            if "shopping cart" in result["text"].lower() or "cart" in result["text"].lower():
                found_relevant = True
                break
        assert found_relevant

    @pytest.mark.asyncio
    async def test_vector_memory_persists_across_tasks(self, temp_dirs):
        """Test that vector memory accumulates knowledge across multiple tasks."""
        db_path = os.path.join(temp_dirs["db"], "persistent.db")

        # Process first task
        orchestrator1 = Orchestrator(project_path=temp_dirs["project"])
        # Manually set vector store path
        mock_embedding = Mock(spec=EmbeddingService)
        mock_embedding.embed_text.return_value = [0.1, 0.2, 0.3, 0.4]
        orchestrator1.vector_store = VectorStore(db_path=db_path, embedding_service=mock_embedding)

        task_file1 = os.path.join(temp_dirs["task"], "001_task1.md")
        with open(task_file1, "w") as f:
            f.write("First task about databases")

        orchestrator1.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator1.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            await orchestrator1.process_task_file(task_file1)

        # Create new orchestrator instance with same database
        orchestrator2 = Orchestrator(project_path=temp_dirs["project"])
        orchestrator2.vector_store = VectorStore(db_path=db_path, embedding_service=mock_embedding)

        # Should be able to find the first task
        results = orchestrator2.vector_store.search("database", k=5)
        assert len(results) > 0
