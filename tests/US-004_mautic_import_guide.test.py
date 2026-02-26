"""
IMPLEMENTATION PLAN for US-004:

Components:
  - lead-import-guide.md: Markdown file containing the documentation for Mautic CSV import process.

Test Cases:
  1. [Import guide `lead-import-guide.md` created at specified path] -> Test if the file exists at the correct path.
  2. [Steps for Mautic UI navigation to import clearly described] -> Test for a heading or specific text describing navigation to Contacts > Import.
  3. [Instructions for uploading cleaned CSV provided] -> Test for text related to uploading the CSV file.
  4. [Guidance on mapping columns to Mautic fields included] -> Test for text describing column mapping.
  5. [Details on setting default field values (e.g., `lead_source`) included] -> Test for instructions on setting default values like `lead_source=purchased_list`.
  6. [Instructions for setting `import_batch` identifier included] -> Test for instructions on setting the `import_batch` field with a date-stamped identifier.
  7. [Guidance on monitoring import progress via Mautic UI provided] -> Test for text describing how to monitor import progress.

Edge Cases:
  - File not found: The tests will inherently fail if the file doesn't exist, which is the expected TDD-RED state.
  - Missing content: If the file exists but lacks specific instructions, the content assertions will fail.
"""

import os
import pytest

# Define the expected path for the documentation file
# This assumes the current working directory is the project root
DOC_FILE_PATH = os.path.join(
    os.path.expanduser("~"),
    "projects",
    "structured-achievement-tool",
    "marketing-automation",
    "docs",
    "lead-import-guide.md"
)

class TestMauticCSVImportGuide:
    def test_import_guide_file_exists(self):
        """
        Verify that the lead-import-guide.md file is created at the specified path.
        """
        assert os.path.exists(DOC_FILE_PATH), (
            f"Documentation file not found at: {DOC_FILE_PATH}"
        )

    @pytest.fixture(scope="class")
    def doc_content(self):
        """
        Fixture to read the content of the documentation file once for all tests in the class.
        This fixture will cause tests to fail if the file does not exist,
        which is expected in the TDD-RED phase.
        """
        if not os.path.exists(DOC_FILE_PATH):
            pytest.fail(f"Documentation file not found at: {DOC_FILE_PATH}")
        with open(DOC_FILE_PATH, "r") as f:
            return f.read()

    def test_ui_navigation_steps_described(self, doc_content):
        """
        Verify that steps for Mautic UI navigation to Contacts > Import are described.
        """
        assert "Contacts > Import" in doc_content, (
            "Mautic UI navigation steps (Contacts > Import) not found in the documentation."
        )
        assert "navigate to" in doc_content.lower(), (
            "Phrase 'navigate to' not found in UI navigation steps."
        )

    def test_upload_cleaned_csv_instructions_provided(self, doc_content):
        """
        Verify that instructions for uploading a cleaned CSV are provided.
        """
        assert "upload" in doc_content.lower() and "csv" in doc_content.lower(), (
            "Instructions for uploading cleaned CSV not found in the documentation."
        )
        assert "cleaned csv" in doc_content.lower(), (
            "Specific mention of 'cleaned CSV' not found."
        )

    def test_column_mapping_guidance_included(self, doc_content):
        """
        Verify that guidance on mapping columns to Mautic fields is included.
        """
        assert "map columns" in doc_content.lower() or "column mapping" in doc_content.lower(), (
            "Guidance on mapping columns to Mautic fields not found in the documentation."
        )
        assert "mautic fields" in doc_content.lower(), (
            "Specific mention of 'Mautic fields' in column mapping guidance not found."
        )

    def test_default_field_values_details_included(self, doc_content):
        """
        Verify that details on setting default field values (e.g., lead_source=purchased_list) are included.
        """
        assert "default values" in doc_content.lower(), (
            "Details on setting default field values not found in the documentation."
        )
        assert "lead_source=purchased_list" in doc_content, (
            "Specific example 'lead_source=purchased_list' not found for default values."
        )

    def test_import_batch_identifier_instructions_included(self, doc_content):
        """
        Verify that instructions for setting the `import_batch` identifier are included.
        """
        assert "`import_batch`" in doc_content, (
            "Instructions for setting `import_batch` identifier not found in the documentation."
        )
        assert "date-stamped identifier" in doc_content.lower(), (
            "Mention of 'date-stamped identifier' for `import_batch` not found."
        )

    def test_monitoring_import_progress_guidance_provided(self, doc_content):
        """
        Verify that guidance on monitoring import progress via Mautic UI is provided.
        """
        assert "monitor import progress" in doc_content.lower(), (
            "Guidance on monitoring import progress not found in the documentation."
        )
        assert "mautic ui" in doc_content.lower(), (
            "Specific mention of 'Mautic UI' for monitoring import progress not found."
        )
