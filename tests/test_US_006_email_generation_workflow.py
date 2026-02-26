"""
IMPLEMENTATION PLAN for US-006:

Components:
  - claude_email_generator: A module in `src/email_automation` to handle Claude API interaction for email generation.
    - `generate_email_copy(template_name, contact_data, api_key)`: Generates email body and subject line variants.
    - `_apply_personalization_tokens(template_content, contact_data)`: Helper to replace tokens in email templates.
  - mautic_draft_saver: A module in `src/email_automation` to interact with Mautic API to save drafts.
    - `save_email_as_draft(email_data, mautic_api_config)`: Saves generated email to Mautic.

Test Cases:
  1. [AC 1] Email generation workflow is operational with Claude API (or placeholder). -> `test_should_generate_email_successfully_with_valid_inputs`
  2. [AC 2] Generates personalized email copy using Claude API. -> `test_should_personalize_email_copy_with_contact_data`
  3. [AC 3] Supports multiple email templates/sequences as specified. -> `test_should_support_multiple_email_templates`
  4. [AC 4] Includes personalization tokens and generates subject line variants. -> `test_should_generate_subject_line_variants_and_personalize_content`
  5. [AC 5] Stores generated emails in Mautic as drafts. -> `test_should_save_generated_email_as_mautic_draft`
  6. [AC 6] Placeholder for Claude API key is present. -> `test_should_use_claude_api_key_placeholder`

Edge Cases:
  - Empty contact data: `test_should_handle_empty_contact_data_gracefully`
  - Invalid template name: `test_should_raise_error_for_invalid_template_name`
  - Claude API error: `test_should_handle_claude_api_error`
  - Mautic API error: `test_should_handle_mautic_api_error`
  - Template with no tokens: `test_should_handle_template_with_no_tokens`
"""
import pytest
from unittest.mock import patch, MagicMock
import sys

# Assume these modules will be created in src/email_automation/
# The imports will fail, which is expected for TDD-RED phase.
from src.email_automation.claude_email_generator import generate_email_copy
from src.email_automation.mautic_draft_saver import save_email_as_draft

class TestEmailGenerationWorkflow:

    @pytest.fixture
    def mock_claude_response(self):
        """Mocks a successful Claude API response for email generation."""
        return {
            "email_body": """Hello {first_name},

This is a personalized email about {product_name}.""",
            "subject_lines": ["Subject 1: {product_name}", "Subject 2: {product_name} - Special Offer"]
        }

    @pytest.fixture
    def mock_contact_data(self):
        """Provides sample contact data for personalization."""
        return {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "product_name": "Awesome Widget"
        }

    @pytest.fixture
    def mock_mautic_config(self):
        """Provides sample Mautic API configuration."""
        return {
            "base_url": "https://mautic.example.com",
            "api_key": "MAUTIC_TEST_API_KEY"
        }

    # AC 1: Email generation workflow is operational with Claude API (or placeholder).
    @patch('''src.email_automation.claude_email_generator.call_claude_api''')
    @patch('''src.email_automation.mautic_draft_saver.call_mautic_api_to_save_draft''')
    def test_should_generate_email_successfully_with_valid_inputs(
        self, mock_save_draft, mock_claude_api, mock_claude_response, mock_contact_data, mock_mautic_config
    ):
        mock_claude_api.return_value = mock_claude_response
        mock_save_draft.return_value = {"success": True, "id": 123}

        email_data = generate_email_copy(
            template_name="initial_outreach",
            contact_data=mock_contact_data,
            api_key="CLAUDE_TEST_API_KEY"
        )
        save_email_as_draft(email_data, mock_mautic_config)

        mock_claude_api.assert_called_once()
        mock_save_draft.assert_called_once_with(
            email_data={
                "email_body": """Hello John,

This is a personalized email about Awesome Widget.""",
                "subject_lines": ["Subject 1: Awesome Widget", "Subject 2: Awesome Widget - Special Offer"]
            },
            mautic_api_config=mock_mautic_config
        )

    # AC 2: Generates personalized email copy using Claude API.
    @patch('''src.email_automation.claude_email_generator.call_claude_api''')
    def test_should_personalize_email_copy_with_contact_data(self, mock_claude_api, mock_claude_response, mock_contact_data):
        mock_claude_api.return_value = mock_claude_response
        
        email_data = generate_email_copy(
            template_name="initial_outreach",
            contact_data=mock_contact_data,
            api_key="CLAUDE_TEST_API_KEY"
        )
        
        assert "Hello John" in email_data["email_body"]
        assert "about Awesome Widget" in email_data["email_body"]
        assert "Subject 1: Awesome Widget" in email_data["subject_lines"]

    # AC 3: Supports multiple email templates/sequences as specified.
    @patch('''src.email_automation.claude_email_generator.call_claude_api''')
    def test_should_support_multiple_email_templates(self, mock_claude_api, mock_contact_data):
        mock_claude_api.side_effect = [
            {
                "email_body": "Initial outreach for {first_name}.",
                "subject_lines": ["Initial: {first_name}"]
            },
            {
                "email_body": "Follow-up for {first_name} after website visit.",
                "subject_lines": ["Follow-up: {first_name}"]
            }
        ]

        email_data_initial = generate_email_copy(
            template_name="initial_outreach",
            contact_data=mock_contact_data,
            api_key="CLAUDE_TEST_API_KEY"
        )
        email_data_followup = generate_email_copy(
            template_name="follow_up_website",
            contact_data=mock_contact_data,
            api_key="CLAUDE_TEST_API_KEY"
        )

        assert "Initial outreach" in email_data_initial["email_body"]
        assert "Follow-up for John after website visit." in email_data_followup["email_body"]
        assert mock_claude_api.call_count == 2
        
    # AC 4: Includes personalization tokens and generates subject line variants.
    @patch('''src.email_automation.claude_email_generator.call_claude_api''')
    def test_should_generate_subject_line_variants_and_personalize_content(
        self, mock_claude_api, mock_contact_data
    ):
        mock_claude_api.return_value = {
            "email_body": "Hi {first_name}, check out {product_name}.",
            "subject_lines": [
                "New: {product_name} just for you!",
                "Exclusive Offer on {product_name}!"
            ]
        }

        email_data = generate_email_copy(
            template_name="promo_email",
            contact_data=mock_contact_data,
            api_key="CLAUDE_TEST_API_KEY"
        )

        assert "Hi John, check out Awesome Widget." in email_data["email_body"]
        assert len(email_data["subject_lines"]) == 2
        assert "New: Awesome Widget just for you!" in email_data["subject_lines"]
        assert "Exclusive Offer on Awesome Widget!" in email_data["subject_lines"]

    # AC 5: Stores generated emails in Mautic as drafts.
    @patch('''src.email_automation.mautic_draft_saver.call_mautic_api_to_save_draft''')
    def test_should_save_generated_email_as_mautic_draft(self, mock_save_draft, mock_mautic_config):
        mock_save_draft.return_value = {"success": True, "id": 456}
        
        email_to_save = {
            "email_body": "Test email body.",
            "subject_lines": ["Test Subject"]
        }

        save_email_as_draft(email_to_save, mock_mautic_config)

        mock_save_draft.assert_called_once_with(
            email_data=email_to_save,
            mautic_api_config=mock_mautic_config
        )

    # AC 6: Placeholder for Claude API key is present.
    @patch('''src.email_automation.claude_email_generator.call_claude_api''')
    def test_should_use_claude_api_key_placeholder(self, mock_claude_api, mock_contact_data):
        mock_claude_api.return_value = {"email_body": "...", "subject_lines": ["..."]}
        
        # Test directly passing the placeholder
        generate_email_copy(
            template_name="any_template",
            contact_data=mock_contact_data,
            api_key="CLAUDE_API_KEY_PLACEHOLDER"
        )
        mock_claude_api.assert_called_once_with(
            template_name="any_template",
            contact_data=mock_contact_data,
            api_key="CLAUDE_API_KEY_PLACEHOLDER"
        )

    # Edge Cases
    @patch('''src.email_automation.claude_email_generator.call_claude_api''')
    def test_should_handle_empty_contact_data_gracefully(self, mock_claude_api):
        mock_claude_api.return_value = {
            "email_body": """Hello ,

This is a generic email.""",
            "subject_lines": ["Generic Subject"]
        }
        
        email_data = generate_email_copy(
            template_name="generic",
            contact_data={},
            api_key="CLAUDE_TEST_API_KEY"
        )
        assert "Hello ," in email_data["email_body"] # Check for incomplete personalization if tokens are missing
        mock_claude_api.assert_called_once()

    def test_should_raise_error_for_invalid_template_name(self):
        with pytest.raises(ValueError): # Assuming a ValueError for invalid templates
            generate_email_copy(
                template_name="non_existent_template",
                contact_data={"first_name": "Test"},
                api_key="CLAUDE_TEST_API_KEY"
            )

    @patch('''src.email_automation.claude_email_generator.call_claude_api''')
    def test_should_handle_claude_api_error(self, mock_claude_api, mock_contact_data):
        mock_claude_api.side_effect = Exception("Claude API Error") # Simulate API failure
        
        with pytest.raises(Exception, match="Claude API Error"):
            generate_email_copy(
                template_name="initial_outreach",
                contact_data=mock_contact_data,
                api_key="CLAUDE_TEST_API_KEY"
            )

    @patch('''src.email_automation.mautic_draft_saver.call_mautic_api_to_save_draft''')
    def test_should_handle_mautic_api_error(self, mock_save_draft, mock_mautic_config):
        mock_save_draft.side_effect = Exception("Mautic API Error") # Simulate API failure
        
        email_to_save = {
            "email_body": "Test email body.",
            "subject_lines": ["Test Subject"]
        }

        with pytest.raises(Exception, match="Mautic API Error"):
            save_email_as_draft(email_to_save, mock_mautic_config)

    @patch('''src.email_automation.claude_email_generator.call_claude_api''')
    def test_should_handle_template_with_no_tokens(self, mock_claude_api):
        mock_claude_api.return_value = {
            "email_body": "This email has no tokens.",
            "subject_lines": ["No Token Subject"]
        }
        
        email_data = generate_email_copy(
            template_name="no_tokens",
            contact_data={"first_name": "John"}, # Provide data, but it won't be used
            api_key="CLAUDE_TEST_API_KEY"
        )
        assert "This email has no tokens." in email_data["email_body"]
        assert "No Token Subject" in email_data["subject_lines"]

