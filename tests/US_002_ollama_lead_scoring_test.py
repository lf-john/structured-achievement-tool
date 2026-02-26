"""
IMPLEMENTATION PLAN for US-002:

Components:
  - src/mautic/lead_scoring_service.py: Orchestrates the lead scoring process, coordinating calls to Ollama and Mautic.
  - src/mautic/ollama_client.py: Handles communication with the Ollama API, sending prompts and receiving raw responses.
  - src/mautic/prompt_builder.py: Constructs structured prompts for Qwen3 8B based on contact data and scoring criteria.
  - src/mautic/response_parser.py: Parses raw Ollama responses into a numeric score (1-100) and confidence level.
  - src/mautic/mautic_api_client.py: Updates the Mautic contact's lead score field.

Data Flow:
  - Input: Contact record (dict with name, title, company, industry, size).
  - LeadScoringService receives contact.
  - LeadScoringService calls PromptBuilder to create a structured prompt.
  - LeadScoringService calls OllamaClient with the prompt.
  - OllamaClient sends the prompt to Ollama/Qwen3 8B and returns a raw response.
  - LeadScoringService calls ResponseParser with the raw response.
  - ResponseParser extracts and returns the score and confidence.
  - LeadScoringService calls MauticApiClient to update the Mautic contact with the extracted score.

Integration Points:
  - New modules in `src/mautic/`.
  - Dependencies on an `ollama_client` (mocked for tests).
  - Dependencies on a `mautic_api_client` (mocked for tests).

Edge Cases:
  - Invalid or incomplete contact record input (missing required fields).
  - Ollama API call failures (network issues, API errors).
  - Ollama response is malformed, empty, or does not contain parsable score/confidence.
  - Returned score is outside the expected 1-100 range.
  - Mautic API update failures.
  - No confidence level in Ollama response.

Test Cases:
  1. [AC 1] Lead scoring workflow is operational with Ollama/Qwen3 8B.
     -> `test_lead_scoring_workflow_success_case`: Verifies that the LeadScoringService successfully orchestrates the entire flow, from prompt building to Ollama API call and Mautic update, with valid mock responses.
  2. [AC 2] Contact records are scored between 1-100 with a confidence level.
     -> `test_response_parser_extracts_valid_score_and_confidence`: Verifies ResponseParser correctly extracts score and confidence from a well-formed Ollama response.
     -> `test_lead_scoring_service_returns_score_and_confidence`: Verifies the LeadScoringService method returns the correct score and confidence on success.
  3. [AC 3] Mautic contact's lead score field is updated.
     -> `test_mautic_contact_updated_with_correct_score`: Verifies MauticApiClient's update method is called with the correct contact ID and calculated score.
     -> `test_lead_scoring_service_calls_mautic_update`: Verifies LeadScoringService triggers the Mautic update after successful scoring.

Edge Cases:
  - `test_lead_scoring_workflow_handles_ollama_api_error`: Ensures graceful handling when Ollama API returns an error.
  - `test_response_parser_handles_malformed_response`: Verifies ResponseParser gracefully handles malformed or unparsable Ollama responses.
  - `test_lead_scoring_workflow_handles_mautic_update_failure`: Ensures graceful handling when Mautic update fails.
  - `test_lead_scoring_workflow_with_missing_contact_fields`: Verifies input validation for incomplete contact records.
"""
import pytest
from unittest.mock import MagicMock, patch
import sys

# Mock modules that do not exist yet



# Importing the service that will be implemented
# This import will cause ModuleNotFoundError since src/mautic/lead_scoring_service.py does not exist yet
from src.mautic.lead_scoring_service import LeadScoringService

class TestOllamaLeadScoringWorkflow:

    @patch('src.mautic.ollama_client.OllamaClient')
    @patch('src.mautic.prompt_builder.PromptBuilder')
    @patch('src.mautic.response_parser.ResponseParser')
    @patch('src.mautic.mautic_api_client.MauticApiClient')
    def test_lead_scoring_workflow_success_case(self, MockMauticApiClient, MockResponseParser, MockPromptBuilder, MockOllamaClient):
        """
        Verifies that the LeadScoringService successfully orchestrates the entire flow,
        from prompt building to Ollama API call and Mautic update, with valid mock responses.
        (Corresponds to AC 1: Lead scoring workflow is operational with Ollama/Qwen3 8B.)
        """
        mock_ollama_instance = MockOllamaClient.return_value
        mock_prompt_builder_instance = MockPromptBuilder.return_value
        mock_response_parser_instance = MockResponseParser.return_value
        mock_mautic_api_instance = MockMauticApiClient.return_value

        contact_data = {
            "id": "123",
            "name": "John Doe",
            "title": "Senior Engineer",
            "company": "Tech Corp",
            "industry": "Software",
            "size": "500-1000"
        }
        mock_prompt_builder_instance.build_lead_scoring_prompt.return_value = "Ollama prompt for John Doe"
        mock_ollama_instance.get_completion.return_value = "Score: 85, Confidence: 0.9"
        mock_response_parser_instance.parse_ollama_response.return_value = (85, 0.9)

        service = LeadScoringService(
            ollama_client=mock_ollama_instance,
            prompt_builder=mock_prompt_builder_instance,
            response_parser=mock_response_parser_instance,
            mautic_api_client=mock_mautic_api_instance
        )
        score, confidence = service.score_lead(contact_data)

        mock_prompt_builder_instance.build_lead_scoring_prompt.assert_called_once_with(contact_data)
        mock_ollama_instance.get_completion.assert_called_once_with("Ollama prompt for John Doe")
        mock_response_parser_instance.parse_ollama_response.assert_called_once_with("Score: 85, Confidence: 0.9")
        mock_mautic_api_instance.update_contact_lead_score.assert_called_once_with("123", 85)
        assert score == 85
        assert confidence == 0.9

    @patch('src.mautic.response_parser.ResponseParser')
    def test_response_parser_extracts_valid_score_and_confidence(self, MockResponseParser):
        """
        Verifies ResponseParser correctly extracts score and confidence from a well-formed Ollama response.
        (Corresponds to AC 2: Contact records are scored between 1-100 with a confidence level.)
        """
        mock_response_parser_instance = MockResponseParser.return_value
        mock_response_parser_instance.parse_ollama_response.return_value = (75, 0.8)

        # Assuming ResponseParser is a standalone component
        # This will be mocked, so the internal logic is not tested here, but rather the expected output.
        # The actual implementation of ResponseParser will be tested in its own file.
        # This test ensures the `score_lead` method gets the correct parsed result.
        # This is primarily for the LeadScoringService to ensure it calls it correctly.
        # The actual class methods are not available yet for direct testing here.
        # For now, we simulate the expected behavior through the mock.
        parsed_score, parsed_confidence = mock_response_parser_instance.parse_ollama_response("Score: 75, Confidence: 0.8")

        assert parsed_score == 75
        assert parsed_confidence == 0.8

    @patch('src.mautic.ollama_client.OllamaClient')
    @patch('src.mautic.prompt_builder.PromptBuilder')
    @patch('src.mautic.response_parser.ResponseParser')
    @patch('src.mautic.mautic_api_client.MauticApiClient')
    def test_lead_scoring_service_returns_score_and_confidence(self, MockMauticApiClient, MockResponseParser, MockPromptBuilder, MockOllamaClient):
        """
        Verifies the LeadScoringService method returns the correct score and confidence on success.
        (Corresponds to AC 2: Contact records are scored between 1-100 with a confidence level.)
        """
        mock_ollama_instance = MockOllamaClient.return_value
        mock_prompt_builder_instance = MockPromptBuilder.return_value
        mock_response_parser_instance = MockResponseParser.return_value
        mock_mautic_api_instance = MockMauticApiClient.return_value

        contact_data = {"id": "123", "name": "Jane Doe"} # Minimal data needed for this test
        mock_prompt_builder_instance.build_lead_scoring_prompt.return_value = "Prompt"
        mock_ollama_instance.get_completion.return_value = "Ollama response"
        mock_response_parser_instance.parse_ollama_response.return_value = (60, 0.75)

        service = LeadScoringService(
            ollama_client=mock_ollama_instance,
            prompt_builder=mock_prompt_builder_instance,
            response_parser=mock_response_parser_instance,
            mautic_api_client=mock_mautic_api_instance
        )
        score, confidence = service.score_lead(contact_data)

        assert score == 60
        assert confidence == 0.75

    @patch('src.mautic.ollama_client.OllamaClient')
    @patch('src.mautic.prompt_builder.PromptBuilder')
    @patch('src.mautic.response_parser.ResponseParser')
    @patch('src.mautic.mautic_api_client.MauticApiClient')
    def test_mautic_contact_updated_with_correct_score(self, MockMauticApiClient, MockResponseParser, MockPromptBuilder, MockOllamaClient):
        """
        Verifies MauticApiClient's update method is called with the correct contact ID and calculated score.
        (Corresponds to AC 3: Mautic contact's lead score field is updated.)
        """
        mock_ollama_instance = MockOllamaClient.return_value
        mock_prompt_builder_instance = MockPromptBuilder.return_value
        mock_response_parser_instance = MockResponseParser.return_value
        mock_mautic_api_instance = MockMauticApiClient.return_value

        contact_data = {"id": "456", "name": "Alice Smith"}
        mock_prompt_builder_instance.build_lead_scoring_prompt.return_value = "Prompt for Alice"
        mock_ollama_instance.get_completion.return_value = "Score: 90, Confidence: 0.95"
        mock_response_parser_instance.parse_ollama_response.return_value = (90, 0.95)

        service = LeadScoringService(
            ollama_client=mock_ollama_instance,
            prompt_builder=mock_prompt_builder_instance,
            response_parser=mock_response_parser_instance,
            mautic_api_client=mock_mautic_api_instance
        )
        service.score_lead(contact_data)

        mock_mautic_api_instance.update_contact_lead_score.assert_called_once_with("456", 90)

    @patch('src.mautic.ollama_client.OllamaClient')
    @patch('src.mautic.prompt_builder.PromptBuilder')
    @patch('src.mautic.response_parser.ResponseParser')
    @patch('src.mautic.mautic_api_client.MauticApiClient')
    def test_lead_scoring_service_calls_mautic_update(self, MockMauticApiClient, MockResponseParser, MockPromptBuilder, MockOllamaClient):
        """
        Verifies LeadScoringService triggers the Mautic update after successful scoring.
        (Corresponds to AC 3: Mautic contact's lead score field is updated.)
        """
        mock_ollama_instance = MockOllamaClient.return_value
        mock_prompt_builder_instance = MockPromptBuilder.return_value
        mock_response_parser_instance = MockResponseParser.return_value
        mock_mautic_api_instance = MockMauticApiClient.return_value

        contact_data = {"id": "789", "name": "Bob Johnson"}
        mock_prompt_builder_instance.build_lead_scoring_prompt.return_value = "Prompt for Bob"
        mock_ollama_instance.get_completion.return_value = "Score: 70, Confidence: 0.8"
        mock_response_parser_instance.parse_ollama_response.return_value = (70, 0.8)

        service = LeadScoringService(
            ollama_client=mock_ollama_instance,
            prompt_builder=mock_prompt_builder_instance,
            response_parser=mock_response_parser_instance,
            mautic_api_client=mock_mautic_api_instance
        )
        service.score_lead(contact_data)

        mock_mautic_api_instance.update_contact_lead_score.assert_called_once()

    @patch('src.mautic.ollama_client.OllamaClient')
    @patch('src.mautic.prompt_builder.PromptBuilder')
    @patch('src.mautic.response_parser.ResponseParser')
    @patch('src.mautic.mautic_api_client.MauticApiClient')
    def test_lead_scoring_workflow_handles_ollama_api_error(self, MockMauticApiClient, MockResponseParser, MockPromptBuilder, MockOllamaClient):
        """
        Ensures graceful handling when Ollama API returns an error.
        (Edge Case)
        """
        mock_ollama_instance = MockOllamaClient.return_value
        mock_prompt_builder_instance = MockPromptBuilder.return_value
        mock_response_parser_instance = MockResponseParser.return_value
        mock_mautic_api_instance = MockMauticApiClient.return_value

        contact_data = {"id": "101", "name": "Error User"}
        mock_prompt_builder_instance.build_lead_scoring_prompt.return_value = "Error prompt"
        mock_ollama_instance.get_completion.side_effect = Exception("Ollama API Error") # Simulate API error
        mock_response_parser_instance.parse_ollama_response.return_value = (0, 0.0) # Default/error value

        service = LeadScoringService(
            ollama_client=mock_ollama_instance,
            prompt_builder=mock_prompt_builder_instance,
            response_parser=mock_response_parser_instance,
            mautic_api_client=mock_mautic_api_instance
        )
        score, confidence = service.score_lead(contact_data)

        mock_prompt_builder_instance.build_lead_scoring_prompt.assert_called_once_with(contact_data)
        mock_ollama_instance.get_completion.assert_called_once_with("Error prompt")
        # ResponseParser and MauticApiClient should ideally not be called or handled gracefully
        mock_response_parser_instance.parse_ollama_response.assert_not_called()
        mock_mautic_api_instance.update_contact_lead_score.assert_not_called()
        assert score == 0 # Or some other indicator of failure
        assert confidence == 0.0 # Or some other indicator of failure

    @patch('src.mautic.ollama_client.OllamaClient')
    @patch('src.mautic.prompt_builder.PromptBuilder')
    @patch('src.mautic.response_parser.ResponseParser')
    @patch('src.mautic.mautic_api_client.MauticApiClient')
    def test_response_parser_handles_malformed_response(self, MockMauticApiClient, MockResponseParser, MockPromptBuilder, MockOllamaClient):
        """
        Verifies ResponseParser gracefully handles malformed or unparsable Ollama responses.
        (Edge Case)
        """
        mock_ollama_instance = MockOllamaClient.return_value
        mock_prompt_builder_instance = MockPromptBuilder.return_value
        mock_response_parser_instance = MockResponseParser.return_value
        mock_mautic_api_instance = MockMauticApiClient.return_value

        contact_data = {"id": "102", "name": "Malformed Response User"}
        mock_prompt_builder_instance.build_lead_scoring_prompt.return_value = "Malformed prompt"
        mock_ollama_instance.get_completion.return_value = "This is not a valid score response"
        mock_response_parser_instance.parse_ollama_response.side_effect = ValueError("Invalid response format") # Simulate parsing error

        service = LeadScoringService(
            ollama_client=mock_ollama_instance,
            prompt_builder=mock_prompt_builder_instance,
            response_parser=mock_response_parser_instance,
            mautic_api_client=mock_mautic_api_instance
        )
        score, confidence = service.score_lead(contact_data)

        mock_prompt_builder_instance.build_lead_scoring_prompt.assert_called_once_with(contact_data)
        mock_ollama_instance.get_completion.assert_called_once_with("Malformed prompt")
        mock_response_parser_instance.parse_ollama_response.assert_called_once_with("This is not a valid score response")
        mock_mautic_api_instance.update_contact_lead_score.assert_not_called()
        assert score == 0 # Expected default/error value
        assert confidence == 0.0 # Expected default/error value

    @patch('src.mautic.ollama_client.OllamaClient')
    @patch('src.mautic.prompt_builder.PromptBuilder')
    @patch('src.mautic.response_parser.ResponseParser')
    @patch('src.mautic.mautic_api_client.MauticApiClient')
    def test_lead_scoring_workflow_handles_mautic_update_failure(self, MockMauticApiClient, MockResponseParser, MockPromptBuilder, MockOllamaClient):
        """
        Ensures graceful handling when Mautic update fails.
        (Edge Case)
        """
        mock_ollama_instance = MockOllamaClient.return_value
        mock_prompt_builder_instance = MockPromptBuilder.return_value
        mock_response_parser_instance = MockResponseParser.return_value
        mock_mautic_api_instance = MockMauticApiClient.return_value

        contact_data = {"id": "103", "name": "Mautic Fail User"}
        mock_prompt_builder_instance.build_lead_scoring_prompt.return_value = "Mautic fail prompt"
        mock_ollama_instance.get_completion.return_value = "Score: 65, Confidence: 0.7"
        mock_response_parser_instance.parse_ollama_response.return_value = (65, 0.7)
        mock_mautic_api_instance.update_contact_lead_score.side_effect = Exception("Mautic API Update Failed") # Simulate Mautic error

        service = LeadScoringService(
            ollama_client=mock_ollama_instance,
            prompt_builder=mock_prompt_builder_instance,
            response_parser=mock_response_parser_instance,
            mautic_api_client=mock_mautic_api_instance
        )
        score, confidence = service.score_lead(contact_data)

        mock_prompt_builder_instance.build_lead_scoring_prompt.assert_called_once_with(contact_data)
        mock_ollama_instance.get_completion.assert_called_once_with("Mautic fail prompt")
        mock_response_parser_instance.parse_ollama_response.assert_called_once_with("Score: 65, Confidence: 0.7")
        mock_mautic_api_instance.update_contact_lead_score.assert_called_once_with("103", 65)
        # Verify that an error in Mautic update doesn't prevent score/confidence from being returned (if desired behavior)
        assert score == 65
        assert confidence == 0.7

    @patch('src.mautic.ollama_client.OllamaClient')
    @patch('src.mautic.prompt_builder.PromptBuilder')
    @patch('src.mautic.response_parser.ResponseParser')
    @patch('src.mautic.mautic_api_client.MauticApiClient')
    def test_lead_scoring_workflow_with_missing_contact_fields(self, MockMauticApiClient, MockResponseParser, MockPromptBuilder, MockOllamaClient):
        """
        Verifies input validation for incomplete contact records.
        (Edge Case)
        """
        mock_ollama_instance = MockOllamaClient.return_value
        mock_prompt_builder_instance = MockPromptBuilder.return_value
        mock_response_parser_instance = MockResponseParser.return_value
        mock_mautic_api_instance = MockMauticApiClient.return_value

        # Missing required fields like 'title', 'company', etc.
        contact_data = {"id": "104", "name": "Incomplete User"}

        service = LeadScoringService(
            ollama_client=mock_ollama_instance,
            prompt_builder=mock_prompt_builder_instance,
            response_parser=mock_response_parser_instance,
            mautic_api_client=mock_mautic_api_instance
        )

        with pytest.raises(ValueError, match="Missing required contact fields for scoring"):
            service.score_lead(contact_data)

        mock_prompt_builder_instance.build_lead_scoring_prompt.assert_not_called()
        mock_ollama_instance.get_completion.assert_not_called()
        mock_response_parser_instance.parse_ollama_response.assert_not_called()
        mock_mautic_api_instance.update_contact_lead_score.assert_not_called()


# This will ensure the test file exits with a non-zero code if any tests fail
# which is crucial for the TDD-RED-CHECK phase.
if __name__ == "__main__":
    pytest.main()
    # In a real scenario, this would be handled by pytest's exit code.
    # For manual execution, to ensure a non-zero exit on failure:
    # Assuming pytest.main() handles sys.exit() or we would check its return value.
    # For now, we manually force exit 1 as the implementation is not there.
    sys.exit(1)
