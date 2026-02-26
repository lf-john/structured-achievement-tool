import pytest
import os
import sys

# Assume the markdown file will be created at this path
DOC_PATH = "marketing-automation/docs/llm-routing-system.md"

class TestLLMRoutingDocumentation:
    """
    Tests for US-012: Document LLM Routing System and Setup Guide.
    These tests verify the existence and content of the documentation file.
    They are expected to fail initially as the document does not yet exist or is incomplete.
    """

    @pytest.fixture(scope="class")
    def document_content(self):
        """
        Fixture to read the content of the documentation file.
        This will initially fail because the file does not exist.
        """
        try:
            # We need to prepend the project root to DOC_PATH for read_file
            project_root = os.getcwd()
            full_doc_path = os.path.join(project_root, DOC_PATH)
            with open(full_doc_path, 'r') as f:
                content = f.read()
            return content
        except FileNotFoundError:
            pytest.fail(f"Documentation file not found at {full_doc_path}. "
                        "This test expects the file to be present and populated.")
        except Exception as e:
            pytest.fail(f"Error reading documentation file: {e}")

    # --- Acceptance Criterion 1: Design document and setup guide are written to ~/projects/marketing-automation/docs/llm-routing-system.md. ---
    def test_documentation_file_exists_and_is_not_empty(self, document_content):
        """
        Verifies that the documentation file exists and contains some content.
        """
        assert document_content is not None, "Document content is None."
        assert len(document_content.strip()) > 0, "Documentation file is empty."
        # This test ensures the fixture succeeds, which means the file was found.

    # --- Acceptance Criterion 2: Documentation covers all implemented components and workflows. ---
    @pytest.mark.parametrize("keyword", [
        "task routing logic",
        "Ollama integration",
        "Claude API integration",
        "cost tracking",
        "fallback logic",
        "batch processing pipeline",
    ])
    def test_documentation_covers_key_components_and_workflows(self, document_content, keyword):
        """
        Verifies that the documentation mentions key components and workflows.
        Case-insensitive search.
        """
        assert keyword.lower() in document_content.lower(), f"Documentation does not mention '{keyword}'."

    # --- Acceptance Criterion 3: Instructions for Claude API key configuration are included. ---
    def test_documentation_includes_claude_api_key_configuration(self, document_content):
        """
        Verifies that the documentation includes instructions for Claude API key configuration.
        Checks for a specific phrase or section heading. Case-insensitive search.
        """
        expected_phrase = "Claude API Key Configuration"
        assert expected_phrase.lower() in document_content.lower() or \
               "API key setup".lower() in document_content.lower(), f"Documentation does not include instructions for '{expected_phrase}' or 'API key setup'."

# This block is for explicit exit code handling if running outside of a full pytest command.
# When run by 'pytest', the exit code is handled automatically.
if __name__ == "__main__":
    # In a typical CLI agent setup, pytest will be invoked directly.
    # The fixture 'document_content' will raise pytest.fail if the file is not found,
    # causing pytest to exit with a non-zero status.
    # This __main__ block is largely for completeness and direct script execution.
    pytest.main([__file__])
