# tests/utils/test_mautic_client.py
import unittest
from unittest.mock import MagicMock, patch

import requests

from src.utils.mautic_client import MauticClient


class TestMauticClient(unittest.TestCase):
    def setUp(self):
        self.client = MauticClient(api_url="https://fake-mautic.com/api", token="fake-token")

    @patch("requests.patch")
    def test_update_contact_score_success(self, mock_patch):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_patch.return_value = mock_response
        contact_id = 42
        score = 99

        # Act
        result = self.client.update_contact_score(contact_id, score)

        # Assert
        self.assertTrue(result)
        mock_patch.assert_called_once_with(
            f"https://fake-mautic.com/api/contacts/{contact_id}/edit",
            headers={"Authorization": "Bearer fake-token"},
            json={"lead_score": score},
            timeout=30,
        )

    @patch("requests.patch")
    def test_update_contact_score_failure(self, mock_patch):
        # Arrange
        mock_patch.side_effect = requests.RequestException("API call failed")
        contact_id = 43
        score = 88

        # Act
        result = self.client.update_contact_score(contact_id, score)

        # Assert
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
