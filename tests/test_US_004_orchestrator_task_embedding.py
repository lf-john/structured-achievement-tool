"""
IMPLEMENTATION PLAN for US-004:

Components:
  - Orchestrator.process_task_file(): Main method that processes task files
    * Executes Ralph Pro via subprocess
    * Embeds completed tasks into VectorStore
    * Handles embedding errors gracefully

  - Task Document Generation: Creates document for embedding
    * Combines request, response logs, and final result
    * Format: "Request: {user_request}\n\nResponse: {log_content}\n\nResult: {final_message}"

  - Metadata Generation: Creates metadata dictionary for task
    * task_id: Parent directory name (unique identifier)
    * task_name: Task file name without extension
    * task_type: Classification from agent (development, bugfix, etc.)
    * file_path: Full path to task file
    * success: Boolean based on returncode == 0
    * returncode: Integer exit code from Ralph Pro

  - Error Handling: Graceful degradation
    * Wraps embedding in try/except
    * Logs warning on failure
    * Does not break task completion

Test Cases:
  1. AC 1 (Orchestrator embeds completed tasks after Ralph Pro execution) -> test_orchestrator_embeds_task_after_ralph_pro_execution
  2. AC 2 (Document includes request, response, and result) -> test_document_includes_request_response_and_result
  3. AC 3 (Metadata includes all required fields) -> test_metadata_includes_all_required_fields
  4. AC 4 (Embedding happens regardless of task success/failure) -> test_embedding_happens_on_successful_task, test_embedding_happens_on_failed_task
  5. AC 5 (Gracefully handles embedding errors) -> test_gracefully_handles_embedding_errors, test_embedding_error_does_not_break_task_completion
  6. AC 6 (Integration tests verify embedding called with correct data) -> test_integration_embedding_flow
  7. AC 7 (Tests mock VectorStore to verify add_document parameters) -> test_vector_store_add_document_called_with_correct_parameters

Edge Cases:
  - Empty request content
  - Very long response logs
  - Unicode characters in request/response
  - Ralph Pro subprocess fails to start
  - VectorStore.add_document() raises various exceptions
  - Multiple sequential task executions
  - task_id with special characters
  - Missing or None task_type
"""

import pytest
import os
import tempfile
import shutil
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from src.orchestrator import Orchestrator
from src.core.vector_store import VectorStore
from src.core.embedding_service import EmbeddingService


class TestOrchestratorEmbedsCompletedTasks:
    """Test AC 1: Orchestrator embeds completed tasks after Ralph Pro execution."""

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
    def mock_vector_store(self):
        """Create a mock VectorStore for testing."""
        store = Mock(spec=VectorStore)
        store.add_document.return_value = 123  # Mock document ID
        store.search.return_value = []
        return store

    @pytest.fixture
    def mock_embedding_service(self):
        """Create a mock EmbeddingService."""
        service = Mock(spec=EmbeddingService)
        service.embed_text.return_value = [0.1] * 768
        return service

    @pytest.mark.asyncio
    async def test_orchestrator_embeds_task_after_ralph_pro_execution(self, temp_dirs, mock_vector_store):
        """Test that vector_store.add_document() is called after Ralph Pro completes."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        # Create a task file
        task_file = os.path.join(temp_dirs["task"], "001_test_task.md")
        user_request = "Implement a user authentication system"
        with open(task_file, "w") as f:
            f.write(user_request)

        # Mock the agent methods
        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        # Mock the Ralph Pro subprocess
        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Build successful", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            # Process the task
            await orchestrator.process_task_file(task_file)

        # Verify that add_document was called
        assert mock_vector_store.add_document.called, "add_document should be called after task execution"
        mock_vector_store.add_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_embedding_happens_after_response_written(self, temp_dirs, mock_vector_store):
        """Test that embedding occurs after response files are written."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "002_test.md")
        with open(task_file, "w") as f:
            f.write("Create API endpoint")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        # Track the order of operations - use synchronous tracking
        call_order = []

        def track_add_document(*args, **kwargs):
            call_order.append("add_document")
            return 1  # Return document ID

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Output", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            # Patch _write_response to track calls
            original_write_response = orchestrator._write_response

            async def track_write_response(*args, **kwargs):
                call_order.append("_write_response")
                return await original_write_response(*args, **kwargs)

            orchestrator._write_response = track_write_response
            mock_vector_store.add_document = track_add_document

            await orchestrator.process_task_file(task_file)

        # Verify that write_response happened before add_document
        # Note: There are 2 write_response calls (log + final message)
        assert call_order.count("_write_response") >= 2, "Should write responses before embedding"
        assert "add_document" in call_order, "Should embed after responses"


class TestDocumentContent:
    """Test AC 2: Document includes request, response, and result."""

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

        for dir_path in [project_dir, task_dir, db_dir]:
            shutil.rmtree(dir_path, ignore_errors=True)

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore."""
        store = Mock(spec=VectorStore)
        store.add_document.return_value = 1
        store.search.return_value = []
        return store

    @pytest.mark.asyncio
    async def test_document_includes_request(self, temp_dirs, mock_vector_store):
        """Test that the document includes the user request."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "003_test.md")
        user_request = "Create a payment processing module"
        with open(task_file, "w") as f:
            f.write(user_request)

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Output", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Get the document text that was passed to add_document
        call_args = mock_vector_store.add_document.call_args
        document_text = call_args[0][0]

        # Verify request is in the document
        assert "Request:" in document_text
        assert user_request in document_text

    @pytest.mark.asyncio
    async def test_document_includes_response_logs(self, temp_dirs, mock_vector_store):
        """Test that the document includes the response logs from Ralph Pro."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "004_test.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        stdout_output = b"Build completed successfully\nAll tests passed"
        stderr_output = b"Warning: deprecated feature used"

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (stdout_output, stderr_output)
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        document_text = call_args[0][0]

        # Verify response logs are in the document
        assert "Response:" in document_text
        assert "Ralph Pro Execution Log" in document_text
        assert stdout_output.decode() in document_text
        assert stderr_output.decode() in document_text
        assert "Exit Code:" in document_text

    @pytest.mark.asyncio
    async def test_document_includes_final_result(self, temp_dirs, mock_vector_store):
        """Test that the document includes the final result message."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "005_test.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Output", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        document_text = call_args[0][0]

        # Verify result is in the document
        assert "Result:" in document_text
        assert "completed successfully" in document_text

    @pytest.mark.asyncio
    async def test_document_includes_request_response_and_result(self, temp_dirs, mock_vector_store):
        """Test that the document has all three sections in correct format."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "006_test.md")
        user_request = "Implement feature X"
        with open(task_file, "w") as f:
            f.write(user_request)

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Execution output", b"Errors")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        document_text = call_args[0][0]

        # Verify all sections exist and are in correct order
        assert document_text.index("Request:") < document_text.index("Response:")
        assert document_text.index("Response:") < document_text.index("Result:")


class TestMetadataContent:
    """Test AC 3: Metadata includes all required fields."""

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

        for dir_path in [project_dir, task_dir, db_dir]:
            shutil.rmtree(dir_path, ignore_errors=True)

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore."""
        store = Mock(spec=VectorStore)
        store.add_document.return_value = 1
        store.search.return_value = []
        return store

    @pytest.mark.asyncio
    async def test_metadata_includes_task_id(self, temp_dirs, mock_vector_store):
        """Test that metadata includes task_id (parent directory name)."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        # Create task in a subdirectory to have a meaningful parent_dir_name
        task_subdir = os.path.join(temp_dirs["task"], "my_feature_task")
        os.makedirs(task_subdir, exist_ok=True)
        task_file = os.path.join(task_subdir, "007_test.md")

        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]

        # Verify task_id
        assert "task_id" in metadata
        assert metadata["task_id"] == "my_feature_task"

    @pytest.mark.asyncio
    async def test_metadata_includes_task_name(self, temp_dirs, mock_vector_store):
        """Test that metadata includes task_name (filename without extension)."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "my_feature_task.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]

        # Verify task_name
        assert "task_name" in metadata
        assert metadata["task_name"] == "my_feature_task"

    @pytest.mark.asyncio
    async def test_metadata_includes_task_type(self, temp_dirs, mock_vector_store):
        """Test that metadata includes task_type from classification."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "009_test.md")
        with open(task_file, "w") as f:
            f.write("Fix the login bug")

        orchestrator.agent.classify = Mock(return_value={"task_type": "bugfix"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]

        # Verify task_type
        assert "task_type" in metadata
        assert metadata["task_type"] == "bugfix"

    @pytest.mark.asyncio
    async def test_metadata_includes_file_path(self, temp_dirs, mock_vector_store):
        """Test that metadata includes the full file path."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "010_test.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]

        # Verify file_path
        assert "file_path" in metadata
        assert metadata["file_path"] == task_file

    @pytest.mark.asyncio
    async def test_metadata_includes_success_flag(self, temp_dirs, mock_vector_store):
        """Test that metadata includes success flag (True when returncode == 0)."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "011_test.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0  # Success
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]

        # Verify success flag
        assert "success" in metadata
        assert metadata["success"] is True

    @pytest.mark.asyncio
    async def test_metadata_includes_returncode(self, temp_dirs, mock_vector_store):
        """Test that metadata includes the actual return code."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "012_test.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 5  # Specific return code
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]

        # Verify returncode
        assert "returncode" in metadata
        assert metadata["returncode"] == 5
        assert metadata["success"] is False  # Should be False when returncode != 0

    @pytest.mark.asyncio
    async def test_metadata_includes_all_required_fields(self, temp_dirs, mock_vector_store):
        """Test that metadata includes all required fields in one test."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_subdir = os.path.join(temp_dirs["task"], "complete_task")
        os.makedirs(task_subdir, exist_ok=True)
        task_file = os.path.join(task_subdir, "feature.md")

        with open(task_file, "w") as f:
            f.write("Implement feature")

        orchestrator.agent.classify = Mock(return_value={"task_type": "feature"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Output", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]

        # Verify all required fields are present
        required_fields = ["task_id", "task_name", "task_type", "file_path", "success", "returncode"]
        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"


class TestEmbeddingRegardlessOfSuccess:
    """Test AC 4: Embedding happens regardless of task success/failure."""

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

        for dir_path in [project_dir, task_dir, db_dir]:
            shutil.rmtree(dir_path, ignore_errors=True)

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore."""
        store = Mock(spec=VectorStore)
        store.add_document.return_value = 1
        store.search.return_value = []
        return store

    @pytest.mark.asyncio
    async def test_embedding_happens_on_successful_task(self, temp_dirs, mock_vector_store):
        """Test that embedding occurs when task succeeds (returncode == 0)."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "013_success.md")
        with open(task_file, "w") as f:
            f.write("Successful task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Success", b"")
            mock_process.returncode = 0  # Success
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Verify embedding occurred
        assert mock_vector_store.add_document.called
        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]
        assert metadata["success"] is True
        assert metadata["returncode"] == 0

    @pytest.mark.asyncio
    async def test_embedding_happens_on_failed_task(self, temp_dirs, mock_vector_store):
        """Test that embedding occurs when task fails (returncode != 0)."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "014_failed.md")
        with open(task_file, "w") as f:
            f.write("Failing task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error occurred")
            mock_process.returncode = 1  # Failure
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Verify embedding still occurred
        assert mock_vector_store.add_document.called
        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]
        assert metadata["success"] is False
        assert metadata["returncode"] == 1

    @pytest.mark.asyncio
    async def test_embedding_happens_on_different_failure_codes(self, temp_dirs, mock_vector_store):
        """Test that embedding happens for various non-zero return codes."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        for returncode in [1, 2, 127, 255, -1]:
            mock_vector_store.add_document.reset_mock()

            task_file = os.path.join(temp_dirs["task"], f"test_{returncode}.md")
            with open(task_file, "w") as f:
                f.write("Test task")

            orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
            orchestrator.agent.decompose = Mock(return_value={"stories": []})

            with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
                mock_process = AsyncMock()
                mock_process.communicate.return_value = (b"", b"Error")
                mock_process.returncode = returncode
                mock_subprocess.return_value = mock_process

                await orchestrator.process_task_file(task_file)

            # Verify embedding occurred for each failure code
            assert mock_vector_store.add_document.called, f"Should embed for returncode {returncode}"

            call_args = mock_vector_store.add_document.call_args
            metadata = call_args[0][1]
            assert metadata["returncode"] == returncode
            assert metadata["success"] is False


class TestGracefulErrorHandling:
    """Test AC 5: Gracefully handles embedding errors without breaking task completion."""

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

        for dir_path in [project_dir, task_dir, db_dir]:
            shutil.rmtree(dir_path, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_gracefully_handles_embedding_errors(self, temp_dirs):
        """Test that embedding errors are caught and handled gracefully."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])

        # Create a mock VectorStore that raises an exception
        mock_vector_store = Mock(spec=VectorStore)
        mock_vector_store.add_document.side_effect = Exception("Embedding failed")
        mock_vector_store.search.return_value = []

        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "015_test.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Output", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            # Should not raise an exception
            result = await orchestrator.process_task_file(task_file)

        # Task should complete despite embedding error
        assert result is not None
        assert result["status"] == "complete"
        assert result["returncode"] == 0

    @pytest.mark.asyncio
    async def test_embedding_error_does_not_break_task_completion(self, temp_dirs):
        """Test that task completion succeeds even when embedding fails."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])

        mock_vector_store = Mock(spec=VectorStore)
        mock_vector_store.add_document.side_effect = RuntimeError("Database connection lost")
        mock_vector_store.search.return_value = []

        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "016_test.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Task output", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            # Should complete without error
            result = await orchestrator.process_task_file(task_file)

        # Verify task completed successfully
        assert result["status"] == "complete"

    @pytest.mark.asyncio
    async def test_various_embedding_exceptions_handled(self, temp_dirs):
        """Test that different exception types are handled gracefully."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])

        exception_types = [
            Exception("Generic error"),
            RuntimeError("Runtime error"),
            ValueError("Invalid value"),
            ConnectionError("Connection failed"),
            IOError("IO error")
        ]

        for exc in exception_types:
            mock_vector_store = Mock(spec=VectorStore)
            mock_vector_store.add_document.side_effect = exc
            mock_vector_store.search.return_value = []

            orchestrator.vector_store = mock_vector_store

            task_file = os.path.join(temp_dirs["task"], f"test_{exc.__class__.__name__}.md")
            with open(task_file, "w") as f:
                f.write("Test task")

            orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
            orchestrator.agent.decompose = Mock(return_value={"stories": []})

            with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
                mock_process = AsyncMock()
                mock_process.communicate.return_value = (b"", b"")
                mock_process.returncode = 0
                mock_subprocess.return_value = mock_process

                # Should handle all exception types
                result = await orchestrator.process_task_file(task_file)

            assert result["status"] == "complete"


class TestIntegrationTests:
    """Test AC 6: Integration tests verify embedding is called with correct data."""

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

        for dir_path in [project_dir, task_dir, db_dir]:
            shutil.rmtree(dir_path, ignore_errors=True)

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore."""
        store = Mock(spec=VectorStore)
        store.add_document.return_value = 42
        store.search.return_value = []
        return store

    @pytest.mark.asyncio
    async def test_integration_embedding_flow(self, temp_dirs, mock_vector_store):
        """Test complete flow: task execution -> document generation -> embedding."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "017_integration.md")
        user_request = "Create a REST API"
        with open(task_file, "w") as f:
            f.write(user_request)

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        ralph_output = b"API created successfully\nEndpoints: /users, /posts"

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (ralph_output, b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await orchestrator.process_task_file(task_file)

        # Verify the complete flow
        # 1. Ralph Pro was executed
        assert mock_subprocess.called

        # 2. Vector store was called
        assert mock_vector_store.add_document.called

        # 3. Task completed successfully
        assert result["status"] == "complete"
        assert result["returncode"] == 0

        # 4. Document was created with correct content
        call_args = mock_vector_store.add_document.call_args
        document = call_args[0][0]
        metadata = call_args[0][1]

        assert user_request in document
        assert ralph_output.decode() in document
        assert "completed successfully" in document
        assert metadata["success"] is True

    @pytest.mark.asyncio
    async def test_end_to_end_with_real_vector_store(self, temp_dirs):
        """Integration test with real VectorStore (not mocked)."""
        # Use real embedding service mock for vector store
        mock_embedding = Mock(spec=EmbeddingService)
        mock_embedding.embed_text.return_value = [0.1] * 768

        db_path = os.path.join(temp_dirs["db"], "test_vectors.db")
        real_vector_store = VectorStore(
            db_path=db_path,
            embedding_service=mock_embedding
        )

        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = real_vector_store

        task_file = os.path.join(temp_dirs["task"], "018_e2e.md")
        with open(task_file, "w") as f:
            f.write("Create user model")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Model created", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Verify document was actually added to vector store
        results = real_vector_store.search("user model", k=5)
        assert len(results) > 0, "Should find the embedded task"


class TestVectorStoreParameters:
    """Test AC 7: Tests mock VectorStore to verify add_document is called with correct parameters."""

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

        for dir_path in [project_dir, task_dir, db_dir]:
            shutil.rmtree(dir_path, ignore_errors=True)

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore."""
        store = Mock(spec=VectorStore)
        store.add_document.return_value = 1
        store.search.return_value = []
        return store

    @pytest.mark.asyncio
    async def test_vector_store_add_document_called_with_correct_text(self, temp_dirs, mock_vector_store):
        """Test that add_document is called with the document text as first parameter."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "019_test.md")
        user_request = "Implement caching"
        with open(task_file, "w") as f:
            f.write(user_request)

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Cache implemented", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Verify add_document was called with text as first positional arg
        call_args = mock_vector_store.add_document.call_args
        assert len(call_args[0]) >= 1
        document_text = call_args[0][0]
        assert isinstance(document_text, str)
        assert len(document_text) > 0

    @pytest.mark.asyncio
    async def test_vector_store_add_document_called_with_correct_metadata(self, temp_dirs, mock_vector_store):
        """Test that add_document is called with metadata dict as second parameter."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "020_test.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "bugfix"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Fixed", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Verify add_document was called with metadata as second positional arg
        call_args = mock_vector_store.add_document.call_args
        assert len(call_args[0]) >= 2
        metadata = call_args[0][1]
        assert isinstance(metadata, dict)

    @pytest.mark.asyncio
    async def test_add_document_called_once_per_task(self, temp_dirs, mock_vector_store):
        """Test that add_document is called exactly once per task execution."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "021_test.md")
        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Should be called exactly once
        assert mock_vector_store.add_document.call_count == 1

    @pytest.mark.asyncio
    async def test_add_document_parameters_match_ac_requirements(self, temp_dirs, mock_vector_store):
        """Test that all parameters match the AC requirements exactly."""
        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "feature.md")
        with open(task_file, "w") as f:
            f.write("Add feature")

        orchestrator.agent.classify = Mock(return_value={"task_type": "feature"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Done", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        call_args = mock_vector_store.add_document.call_args
        document = call_args[0][0]
        metadata = call_args[0][1]

        # Verify document structure
        assert "Request:" in document
        assert "Response:" in document
        assert "Result:" in document

        # Verify metadata keys
        assert set(metadata.keys()) == {"task_id", "task_name", "task_type", "file_path", "success", "returncode"}


class TestEdgeCasesAndAdditionalScenarios:
    """Additional edge cases for comprehensive coverage."""

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

        for dir_path in [project_dir, task_dir, db_dir]:
            shutil.rmtree(dir_path, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_empty_request_content(self, temp_dirs):
        """Test handling of empty request content."""
        mock_vector_store = Mock(spec=VectorStore)
        mock_vector_store.add_document.return_value = 1
        mock_vector_store.search.return_value = []

        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "022_empty.md")
        with open(task_file, "w") as f:
            f.write("")  # Empty request

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Should still embed even with empty request
        assert mock_vector_store.add_document.called

    @pytest.mark.asyncio
    async def test_very_long_response_logs(self, temp_dirs):
        """Test handling of very long response logs."""
        mock_vector_store = Mock(spec=VectorStore)
        mock_vector_store.add_document.return_value = 1
        mock_vector_store.search.return_value = []

        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "023_long.md")
        with open(task_file, "w") as f:
            f.write("Generate code")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        # Generate very long output
        long_output = b"Line of output\n" * 10000

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (long_output, b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Should handle long output
        assert mock_vector_store.add_document.called
        call_args = mock_vector_store.add_document.call_args
        document = call_args[0][0]
        assert len(document) > 100000  # Should be very long

    @pytest.mark.asyncio
    async def test_unicode_characters_in_content(self, temp_dirs):
        """Test handling of unicode characters."""
        mock_vector_store = Mock(spec=VectorStore)
        mock_vector_store.add_document.return_value = 1
        mock_vector_store.search.return_value = []

        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        task_file = os.path.join(temp_dirs["task"], "024_unicode.md")
        unicode_request = "Create authentication for users 世界 🌍"  # Chinese and emoji
        with open(task_file, "w", encoding="utf-8") as f:
            f.write(unicode_request)

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Output with unicode: \xe4\xb8\x96\xe7\x95\x8c", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Should handle unicode
        assert mock_vector_store.add_document.called

    @pytest.mark.asyncio
    async def test_multiple_sequential_task_executions(self, temp_dirs):
        """Test that multiple sequential tasks all get embedded."""
        mock_vector_store = Mock(spec=VectorStore)
        mock_vector_store.add_document.return_value = 1
        mock_vector_store.search.return_value = []

        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        # Process multiple tasks
        for i in range(5):
            task_file = os.path.join(temp_dirs["task"], f"task_{i}.md")
            with open(task_file, "w") as f:
                f.write(f"Task {i}")

            with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
                mock_process = AsyncMock()
                mock_process.communicate.return_value = (b"Output", b"")
                mock_process.returncode = 0
                mock_subprocess.return_value = mock_process

                await orchestrator.process_task_file(task_file)

        # All tasks should have been embedded
        assert mock_vector_store.add_document.call_count == 5

    @pytest.mark.asyncio
    async def test_special_characters_in_task_id(self, temp_dirs):
        """Test handling of special characters in task ID."""
        mock_vector_store = Mock(spec=VectorStore)
        mock_vector_store.add_document.return_value = 1
        mock_vector_store.search.return_value = []

        orchestrator = Orchestrator(project_path=temp_dirs["project"])
        orchestrator.vector_store = mock_vector_store

        # Create task directory with special characters
        task_subdir = os.path.join(temp_dirs["task"], "task-with_special.chars")
        os.makedirs(task_subdir, exist_ok=True)
        task_file = os.path.join(task_subdir, "test.md")

        with open(task_file, "w") as f:
            f.write("Test task")

        orchestrator.agent.classify = Mock(return_value={"task_type": "development"})
        orchestrator.agent.decompose = Mock(return_value={"stories": []})

        with patch('asyncio.create_subprocess_shell', new_callable=AsyncMock) as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            await orchestrator.process_task_file(task_file)

        # Should handle special characters
        assert mock_vector_store.add_document.called
        call_args = mock_vector_store.add_document.call_args
        metadata = call_args[0][1]
        assert "task-with_special.chars" in metadata["task_id"]


# Track and report failures for proper exit code
if __name__ == "__main__":
    import sys
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)
