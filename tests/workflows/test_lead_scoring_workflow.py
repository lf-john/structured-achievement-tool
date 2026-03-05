# tests/workflows/test_lead_scoring_workflow.py
import json
import unittest
from unittest.mock import patch

from src.workflows.lead_scoring_workflow import LeadScoringWorkflow


class TestLeadScoringWorkflow(unittest.TestCase):

    def setUp(self):
        # Create a dummy config for tests
        self.config = {
            "ollama_api_url": "http://fake-ollama",
            "ollama_model": "fake-model",
            "mautic_api_url": "http://fake-mautic",
            "mautic_api_token": "fake-token"
        }
        with open("test_config.json", "w") as f:
            json.dump(self.config, f)

        # Patch the clients within the workflow's scope
        self.ollama_client_patcher = patch('src.workflows.lead_scoring_workflow.OllamaClient')
        self.mautic_client_patcher = patch('src.workflows.lead_scoring_workflow.MauticClient')

        self.MockOllamaClient = self.ollama_client_patcher.start()
        self.MockMauticClient = self.mautic_client_patcher.start()

        self.mock_ollama_instance = self.MockOllamaClient.return_value
        self.mock_mautic_instance = self.MockMauticClient.return_value

    def tearDown(self):
        import os
        os.remove("test_config.json")
        self.ollama_client_patcher.stop()
        self.mautic_client_patcher.stop()

    def test_run_success(self):
        # Arrange
        self.mock_ollama_instance.score_lead.return_value = {"score": 85, "confidence": "high"}
        self.mock_mautic_instance.update_contact_score.return_value = True

        workflow = LeadScoringWorkflow(config_path="test_config.json")
        contact_id = 101
        contact_data = {"name": "Test User"}

        # Act
        result = workflow.run(contact_id, contact_data)

        # Assert
        self.assertTrue(result)
        self.mock_ollama_instance.score_lead.assert_called_once_with(contact_data)
        self.mock_mautic_instance.update_contact_score.assert_called_once_with(contact_id, 85)

    def test_run_ollama_failure(self):
        # Arrange
        self.mock_ollama_instance.score_lead.return_value = {"error": "Ollama is down"}

        workflow = LeadScoringWorkflow(config_path="test_config.json")
        contact_id = 102
        contact_data = {"name": "Test User 2"}

        # Act
        result = workflow.run(contact_id, contact_data)

        # Assert
        self.assertFalse(result)
        self.mock_mautic_instance.update_contact_score.assert_not_called()

    def test_run_mautic_failure(self):
        # Arrange
        self.mock_ollama_instance.score_lead.return_value = {"score": 70, "confidence": "medium"}
        self.mock_mautic_instance.update_contact_score.return_value = False

        workflow = LeadScoringWorkflow(config_path="test_config.json")
        contact_id = 103
        contact_data = {"name": "Test User 3"}

        # Act
        result = workflow.run(contact_id, contact_data)

        # Assert
        self.assertFalse(result)
        self.mock_mautic_instance.update_contact_score.assert_called_once_with(contact_id, 70)


if __name__ == '__main__':
    unittest.main()
