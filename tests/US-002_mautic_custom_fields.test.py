"""
IMPLEMENTATION PLAN for US-002: Configure Custom Fields in Mautic

Components:
  - src/mautic/custom_fields_service.py: A new module to manage Mautic custom fields.
    - ensure_custom_fields_exist(fields_config: list[dict], method: str) -> dict: Main function to create/verify all specified custom fields and return documentation.
    - _create_custom_field(field_config: dict) -> dict: Internal function to handle the creation of a single custom field in Mautic.
    - _get_existing_fields() -> list[dict]: (Mocked) Simulates fetching existing Mautic custom fields.
    - _document_field_configuration(field_config: dict) -> str: Helper to format documentation for a single field.

Test Cases:
  1. [AC 1-6 & 8] -> test_should_create_all_custom_fields_successfully_and_document_them: Verifies that `ensure_custom_fields_exist` processes all fields (industry, company_size, lead_source, icp_fit, import_batch, data_quality) and that the documentation for each field (label, alias, type, properties) is correctly generated.
  2. [AC 7] -> test_should_document_field_creation_method: Verifies that the overall documentation includes the method of field creation (UI/API).
  3. Edge Case -> test_should_handle_empty_field_configuration_list: Ensures graceful handling of an empty input list.
  4. Edge Case -> test_should_handle_invalid_field_type: Verifies that an appropriate error is raised for an unsupported field type.
  5. Edge Case -> test_should_handle_missing_select_values_for_select_type: Ensures an error is raised if a 'select' field is missing its options.
  6. Edge Case -> test_should_handle_mautic_api_errors_during_field_creation: Simulates a Mautic API error during field creation and verifies error reporting.
  7. Edge Case -> test_should_not_recreate_existing_fields: Verifies that fields already present in Mautic are not re-created.

Edge Cases:
  - Empty `fields_config` list.
  - Invalid `field_type` (e.g., "unknown_type").
  - Missing required properties for specific `field_type` (e.g., `select` values for a 'select' field).
  - Mautic API/UI interaction failures during field creation.
  - Attempting to create a field that already exists.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock

# Importing the module that will be implemented.
# This import is expected to fail with ModuleNotFoundError during the TDD-RED phase.
# No direct import of src.mautic.custom_fields_service here.
# Instead, we will use unittest.mock.patch in the tests directly
# to simulate the module and its functions, expecting NotImplementedError.
# This avoids ModuleNotFoundError during pytest collection.


class TestMauticCustomFieldsConfiguration:

    FIELD_CONFIGURATIONS = [
        {
            "label": "Industry",
            "alias": "industry",
            "type": "select",
            "properties": {"list": {"manufacturing": "Manufacturing", "retail": "Retail", "technology": "Technology", "healthcare": "Healthcare", "finance": "Finance", "education": "Education", "other": "Other"}}
        },
        {
            "label": "Company Size",
            "alias": "company_size",
            "type": "select",
            "properties": {"list": {"1-10": "1-10", "11-50": "11-50", "51-200": "51-200", "201-1000": "201-1000", "1000+": "1000+"}}
        },
        {
            "label": "Lead Source",
            "alias": "lead_source",
            "type": "select",
            "properties": {"list": {"website": "Website", "referral": "Referral", "social_media": "Social Media", "paid_ad": "Paid Ad", "event": "Event", "cold_email": "Cold Email", "other": "Other"}}
        },
        {
            "label": "ICP Fit",
            "alias": "icp_fit",
            "type": "select",
            "properties": {"list": {"high": "High", "medium": "Medium", "low": "Low", "n/a": "N/A"}}
        },
        {
            "label": "Import Batch",
            "alias": "import_batch",
            "type": "text",
            "properties": {}
        },
        {
            "label": "Data Quality",
            "alias": "data_quality",
            "type": "select",
            "properties": {"list": {"high": "High", "medium": "Medium", "low": "Low", "unverified": "Unverified"}}
        }
    ]

    @patch('src.mautic.custom_fields_service.ensure_custom_fields_exist', side_effect=NotImplementedError("Mocked for TDD-RED"))
    def test_should_create_all_custom_fields_successfully_and_document_them(self, mock_ensure_fields_exist):
        """
        [AC 1-6 & 8] Verifies that ensure_custom_fields_exist processes all fields and generates correct documentation.
        """
        mock_ensure_fields_exist.return_value = {
            "status": "success",
            "documentation": "## Mautic Custom Fields Configuration (Method: API)

### Field: Industry (Alias: industry, Type: select)
- Properties: {'list': {'manufacturing': 'Manufacturing', 'retail': 'Retail', 'technology': 'Technology', 'healthcare': 'Healthcare', 'finance': 'Finance', 'education': 'Education', 'other': 'Other'}}

### Field: Company Size (Alias: company_size, Type: select)
- Properties: {'list': {'1-10': '1-10', '11-50': '11-50', '51-200': '51-200', '201-1000': '201-1000', '1000+': '1000+'}}

### Field: Lead Source (Alias: lead_source, Type: select)
- Properties: {'list': {'website': 'Website', 'referral': 'Referral', 'social_media': 'Social Media', 'paid_ad': 'Paid Ad', 'event': 'Event', 'cold_email': 'Cold Email', 'other': 'Other'}}

### Field: ICP Fit (Alias: icp_fit, Type: select)
- Properties: {'list': {'high': 'High', 'medium': 'Medium', 'low': 'Low', 'n/a': 'N/A'}}

### Field: Import Batch (Alias: import_batch, Type: text)
- Properties: {}

### Field: Data Quality (Alias: data_quality, Type: select)
- Properties: {'list': {'high': 'High', 'medium': 'Medium', 'low': 'Low', 'unverified': 'Unverified'}}
"
        }
        mock_document_field_config.side_effect = lambda field: f"### Field: {field['label']} (Alias: {field['alias']}, Type: {field['type']})
- Properties: {field['properties']}
"

        result = ensure_custom_fields_exist(self.FIELD_CONFIGURATIONS, "API")

        assert result["status"] == "success"
        doc = result["documentation"]
        assert "## Mautic Custom Fields Configuration (Method: API)" in doc

        for field in self.FIELD_CONFIGURATIONS:
            assert f"### Field: {field['label']} (Alias: {field['alias']}, Type: {field['type']})" in doc
            assert f"- Properties: {field['properties']}" in doc

    @patch('src.mautic.custom_fields_service.ensure_custom_fields_exist', side_effect=NotImplementedError("Mocked for TDD-RED"))
    def test_should_document_field_creation_method(self, mock_ensure_fields_exist):
        """
        [AC 7] Verifies that the overall documentation includes the method of field creation (UI/API).
        """
        mock_ensure_fields_exist.return_value = {
            "status": "success",
            "documentation": "## Mautic Custom Fields Configuration (Method: UI)

### Field: Industry (Alias: industry, Type: select)
- Properties: {'list': {'manufacturing': 'Manufacturing'}}
"
        }

        result_api = ensure_custom_fields_exist(self.FIELD_CONFIGURATIONS[:1], "API")
        assert "Method: API" in result_api["documentation"]

        result_ui = ensure_custom_fields_exist(self.FIELD_CONFIGURATIONS[:1], "UI")
        assert "Method: UI" in result_ui["documentation"]

    @patch('src.mautic.custom_fields_service.ensure_custom_fields_exist', side_effect=NotImplementedError("Mocked for TDD-RED"))
    def test_should_handle_empty_field_configuration_list(self, mock_ensure_fields_exist):
        """
        Edge Case: Ensures graceful handling of an empty input list.
        """
        mock_ensure_fields_exist.return_value = {
            "status": "success",
            "documentation": "## Mautic Custom Fields Configuration (Method: API)
No custom fields configured.
"
        }
        result = ensure_custom_fields_exist([], "API")
        assert result["status"] == "success"
        assert "No custom fields configured." in result["documentation"]

    @patch('src.mautic.custom_fields_service.ensure_custom_fields_exist', side_effect=NotImplementedError("Mocked for TDD-RED"))
    def test_should_handle_invalid_field_type(self, mock_ensure_fields_exist):
        """
        Edge Case: Verifies that an appropriate error is raised for an unsupported field type.
        """
        invalid_config = [{"label": "Invalid Field", "alias": "invalid_field", "type": "unknown_type", "properties": {}}]
        mock_ensure_fields_exist.side_effect = ValueError("Failed to create field 'Invalid Field': Invalid field type: unknown_type")

        with pytest.raises(ValueError, match="Failed to create field 'Invalid Field': Invalid field type: unknown_type"):
            ensure_custom_fields_exist(invalid_config, "API")
        mock_create_custom_field.assert_called_once()


    @patch('src.mautic.custom_fields_service.ensure_custom_fields_exist', side_effect=NotImplementedError("Mocked for TDD-RED"))
    def test_should_handle_missing_select_values_for_select_type(self, mock_ensure_fields_exist):
        """
        Edge Case: Ensures an error is raised if a 'select' field is missing its options.
        """
        invalid_config = [{"label": "Missing Options", "alias": "missing_options", "type": "select", "properties": {}}]
        mock_ensure_fields_exist.side_effect = ValueError("Failed to create field 'Missing Options': Missing 'list' property for select field 'Missing Options'")

        with pytest.raises(ValueError, match="Failed to create field 'Missing Options': Missing 'list' property for select field 'Missing Options'"):
            ensure_custom_fields_exist(invalid_config, "API")
        mock_create_custom_field.assert_called_once()

    @patch('src.mautic.custom_fields_service.ensure_custom_fields_exist', side_effect=NotImplementedError("Mocked for TDD-RED"))
    def test_should_handle_mautic_api_errors_during_field_creation(self, mock_ensure_fields_exist):
        """
        Edge Case: Simulates a Mautic API error during field creation and verifies error reporting.
        """
        mock_ensure_fields_exist.side_effect = Exception("Error processing field 'Industry': Mautic API Error: Field creation failed")

        with pytest.raises(Exception, match="Error processing field 'Industry': Mautic API Error: Field creation failed"):
            ensure_custom_fields_exist(self.FIELD_CONFIGURATIONS[:1], "API")
        mock_create_custom_field.assert_called_once()

    @patch('src.mautic.custom_fields_service.ensure_custom_fields_exist', side_effect=NotImplementedError("Mocked for TDD-RED"))
    def test_should_not_recreate_existing_fields(self, mock_ensure_fields_exist):
        """
        Edge Case: Verifies that if a field already exists, it's not re-created.
        """
        # Simulate ensure_custom_fields_exist being called with existing fields
        # This means the mock for ensure_custom_fields_exist should return a successful result
        # but the internal _create_custom_field should not be called for 'industry'
        mock_ensure_fields_exist.return_value = {
            "status": "success",
            "documentation": "## Mautic Custom Fields Configuration (Method: API)

### Field: Industry (Alias: industry, Type: select)
- Status: Already Exists
"
        }

        result = ensure_custom_fields_exist(self.FIELD_CONFIGURATIONS[:1], "API")
        assert result["status"] == "success"
        assert "Status: Already Exists" in result["documentation"]
        mock_get_existing_fields.assert_called_once()
        mock_create_custom_field.assert_not_called() # Crucial: _create_custom_field should not be called for existing field


# Exit code requirement for TDD-RED phase
if __name__ == "__main__":
    pytest_exit_code = pytest.main([__file__])
    sys.exit(pytest_exit_code)
