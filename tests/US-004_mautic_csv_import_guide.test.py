"""
IMPLEMENTATION PLAN for US-004 (Documentation Story):

Components:
  - lead-import-guide.md: A new markdown documentation file containing step-by-step instructions for importing leads via Mautic UI.

Data Flow:
  - Input: None (documentation is static content based on requirements)
  - Output: Markdown file at project root with comprehensive import instructions

Integration Points:
  - None - this is a standalone documentation file
  - Verification via tests that validate file existence and content requirements

Test Cases:
  1. AC 1: Import guide created at specified path
     - test_should_create_lead_import_guide_at_project_root: Verify file exists at correct location
  2. AC 2: Steps for Mautic UI navigation described
     - test_should_include_navigation_to_contacts_import: Check for "Contacts > Import" references
  3. AC 3: Instructions for uploading CSV provided
     - test_should_include_csv_upload_instructions: Check for upload-related content
  4. AC 4: Guidance on mapping columns to Mautic fields included
     - test_should_include_column_mapping_instructions: Check for "map" references
  5. AC 5: Details on setting default field values included
     - test_should_include_default_value_settings: Check for "default value" references
  6. AC 6: Instructions for setting import_batch identifier included
     - test_should_include_import_batch_identifier: Check for "import_batch" references
  7. AC 7: Guidance on monitoring import progress provided
     - test_should_include_monitoring_instructions: Check for "monitor" references

Edge Cases:
  - Empty or blank line handling in markdown file
  - Special characters in documentation content
  - File size constraints (documentation files should be reasonably sized)
  - Missing sections validation
"""

import pytest
import os
import sys
from pathlib import Path

# AMENDED BY US-004: Updated path to match story specification and added fixture for content.
DOC_FILE_RELATIVE_PATH = Path("marketing-automation") / "docs" / "lead-import-guide.md"
GUIDE_FILE_PATH = Path(__file__).parent.parent / DOC_FILE_RELATIVE_PATH

@pytest.fixture(scope="class")
def guide_content(self):
    try:
        with open(GUIDE_FILE_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        pytest.fail(f"Documentation file not found at {GUIDE_FILE_PATH}. Ensure the implementation creates it.")
    except Exception as e:
        pytest.fail(f"Error reading documentation file: {e}")

class TestMauticCSVImportGuide:
    """Test suite for verifying the Mautic CSV import documentation."""

    def test_should_create_lead_import_guide_at_correct_path(self):
        """
        AC 1: Verify that the lead import guide file exists at the correct path.
        This test will fail if the file hasn't been created yet.
        """
        # AMENDED BY US-004: Renamed test and updated assertion for correct path.
        assert GUIDE_FILE_PATH.exists(), f"File '{GUIDE_FILE_PATH}' does not exist"

    def test_should_have_valid_markdown_format(self, guide_content):
        """
        Verify that the guide file is a valid markdown file that can be read.
        """
        # AMENDED BY US-004: Using guide_content fixture.
        content = guide_content

        # File should not be empty
        assert len(content) > 0, "Guide file is empty"

        # File should be readable as text
        assert isinstance(content, str), "File content should be a string"

        # File should have some length (documentation should be meaningful)
        assert len(content) > 100, "Guide file seems too short to contain comprehensive instructions"

    def test_should_include_navigation_to_contacts_import(self, guide_content):
        """
        AC 2: Verify that the guide includes navigation steps to Contacts > Import.
        This will fail with a clear error message if the content is missing.
        """
        # AMENDED BY US-004: Using guide_content fixture.
        content = guide_content

        # Check for navigation keywords (case-insensitive)
        assert "Contacts > Import" in content or "Contacts > Import" in content.lower(), \
            "Missing section: Navigation instructions to 'Contacts > Import'"
        assert "Contacts" in content and "Import" in content, \
            "Missing navigation context"

    def test_should_include_csv_upload_instructions(self, guide_content):
        """
        AC 3: Verify that the guide includes instructions for uploading the cleaned CSV.
        """
        # AMENDED BY US-004: Using guide_content fixture.
        content = guide_content

        # Check for upload-related content (case-insensitive)
        assert "upload" in content.lower() or "uploading" in content.lower(), \
            "Missing section: CSV upload instructions"
        assert "file" in content.lower() or "csv" in content.lower(), \
            "Missing upload context"

    def test_should_include_column_mapping_instructions(self, guide_content):
        """
        AC 4: Verify that the guide includes guidance on mapping columns to Mautic fields.
        """
        # AMENDED BY US-004: Using guide_content fixture.
        content = guide_content

        # Check for mapping-related content
        assert "map" in content.lower() or "mapping" in content.lower() or \
               "field" in content.lower(), \
            "Missing section: Column mapping guidance"

    def test_should_include_default_value_settings(self, guide_content):
        """
        AC 5: Verify that the guide includes details on setting default field values.
        """
        # AMENDED BY US-004: Using guide_content fixture.
        content = guide_content

        # Check for default value references
        assert "default value" in content.lower() or "default" in content.lower(), \
            "Missing section: Setting default values"
        assert "lead_source" in content.lower(), \
            "Missing example: 'lead_source' default value"

    def test_should_include_import_batch_identifier(self, guide_content):
        """
        AC 6: Verify that the guide includes instructions for setting import_batch identifier.
        """
        # AMENDED BY US-004: Using guide_content fixture.
        content = guide_content

        # Check for import_batch references
        assert "import_batch" in content.lower(), \
            "Missing section: 'import_batch' identifier"

    def test_should_include_monitoring_instructions(self, guide_content):
        """
        AC 7: Verify that the guide includes guidance on monitoring import progress.
        """
        # AMENDED BY US-004: Using guide_content fixture.
        content = guide_content

        # Check for monitoring-related content
        assert "monitor" in content.lower() or "progress" in content.lower() or \
               "tracking" in content.lower(), \
            "Missing section: Monitoring import progress"

    def test_should_have_clean_markdown_structure(self, guide_content):
        """
        Edge case: Verify that the markdown file has a reasonable structure.
        Check for common markdown headers.
        """
        # AMENDED BY US-004: Using guide_content fixture.
        content = guide_content

        # Check for potential markdown headers (starting with #)
        lines = content.split('\n')
        headers = [line for line in lines if line.strip().startswith('#')]

        # Should have at least one header to indicate structure
        assert len(headers) > 0, "Guide file should have at least one markdown header"

        # Each header should be properly formatted
        for header in headers:
            assert header.startswith('#'), f"Header '{header}' is not properly formatted"

    def test_should_handle_special_characters_in_content(self, guide_content):
        """
        Edge case: Verify that special characters in documentation content are preserved.
        """
        # AMENDED BY US-004: Using guide_content fixture.
        content = guide_content

        # Check that special characters are not stripped
        # (e.g., parentheses, quotes, etc. that might be in instructions)
        assert '"' in content or "'" in content, \
            "Documentation should contain some quoted text for clarity"

        # Check that file encoding is UTF-8
        try:
            content.encode('utf-8')
        except UnicodeEncodeError:
            pytest.fail("File contains non-UTF-8 characters")


