# tests/utils/test_ollama_client.py
import unittest
from unittest.mock import patch, MagicMock
from src.utils.ollama_client import OllamaClient

class TestOllamaClient(unittest.TestCase):

    def setUp(self):
        self.client = OllamaClient(api_url="http://fake-ollama:11434/api", model="test-model")
        self.contact_data = {
            "name": "John Smith",
            "title": "Director of Engineering",
            "company": "Innovate LLC",
            "industry": "Technology",
            "company_size": 150,
            "location": "London, UK"
        }

    @patch('requests.post')
    def test_score_lead_success(self, mock_post):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        # The response from Ollama is a JSON object where the 'response' key contains a string,
        # which itself is the JSON payload we want.
        mock_response.json.return_value = {
            "response": '{"score": 92, "confidence": "high"}'
        }
        mock_post.return_value = mock_response

        # Act
        result = self.client.score_lead(self.contact_data)

        # Assert
        self.assertEqual(result, {"score": 92, "confidence": "high"})
        mock_post.assert_called_once()
        # You could add more assertions here to check the prompt sent to Ollama

    @patch('requests.post')
    def test_score_lead_api_error(self, mock_post):
        # Arrange
        mock_post.side_effect = requests.RequestException("Connection error")

        # Act
        result = self.client.score_lead(self.contact_data)

        # Assert
        self.assertEqual(result['score'], 0)
        self.assertEqual(result['confidence'], 'low')
        self.assertIn('error', result)

    def test_parse_response_valid(self):
        # Arrange
        response_text = 'Here is the JSON you requested: {"score": 78, "confidence": "medium"}. Let me know if you need more.'
        
        # Act
        result = self.client._parse_response(response_text)

        # Assert
        self.assertEqual(result, {"score": 78, "confidence": "medium"})

    def test_parse_response_invalid_json(self):
        # Arrange
        response_text = 'I am unable to provide a score. The format is wrong.'
        
        # Act
        result = self.client._parse_response(response_text)

        # Assert
        self.assertEqual(result['score'], 0)
        self.assertIn('Failed to parse response', result['error'])

    def test_parse_response_incomplete_json(self):
        # Arrange
        response_text = '{"score": 50'
        
        # Act
        result = self.client._parse_response(response_text)
        
        # Assert
        self.assertEqual(result['score'], 0)
        self.assertIn('Failed to parse response', result['error'])
        
    def test_build_prompt(self):
        # Arrange
        prompt = self._get_expected_prompt()

        # Act
        result = self.client._build_prompt(self.contact_data)
        
        # Assert
        # Using strip and replacing spaces to make the comparison less brittle to whitespace changes
        self.assertEqual("".join(result.split()), "".join(prompt.split()))

    def _get_expected_prompt(self):
        return f"""
        Analyze the following contact and score them from 1 to 100 based on their fit for our Ideal Customer Profile (ICP).

        ICP Criteria:
        - Title/Seniority: Director, VP, C-level in Marketing, Sales, or Technology.
        - Company Size: 50 - 1000 employees.
        - Industry: SaaS, Technology, Marketing Agencies, E-commerce.
        - Geography: North America, Europe.

        Contact Details:
        - Name: {self.contact_data.get('name', 'N/A')}
        - Title: {self.contact_data.get('title', 'N/A')}
        - Company: {self.contact_data.get('company', 'N/A')}
        - Industry: {self.contact_data.get('industry', 'N/A')}
        - Company Size: {self.contact_data.get('company_size', 'N/A')}
        - Location: {self.contact_data.get('location', 'N/A')}

        Output your response as a JSON object with two keys: "score" (an integer from 1 to 100) and "confidence" (a string: "high", "medium", or "low").
        Do not include any other text or explanation.

        Example Response:
        {{"score": 85, "confidence": "high"}}

        JSON Response:
        """

if __name__ == '__main__':
    unittest.main()
