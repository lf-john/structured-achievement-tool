"""
IMPLEMENTATION PLAN for US-001: Create Grafana API client with authentication

Components:
  - GrafanaClient: Main class for interacting with Grafana API
    - __init__(api_key=None): Initialize client with API key (defaults to env var)
    - _get_headers(): Return authentication headers
    - get_dashboard(uid): Fetch dashboard by UID
    - create_dashboard(dashboard_json): Create new dashboard
    - update_dashboard(uid, dashboard_json): Update existing dashboard
    - _make_request(endpoint, method, json_data=None): Internal HTTP request handler
    - _handle_response(response): Handle API responses

Test Cases:
  1. AC1 -> test_client_initializes_with_api_key_from_env
  2. AC1 -> test_client_accepts_custom_api_key
  3. AC1 -> test_client_raises_error_without_api_key
  4. AC2 -> test_client_authenticates_with_valid_api_key
  5. AC2 -> test_client_raises_error_with_invalid_api_key
  6. AC3 -> test_get_dashboard_returns_dashboard_json
  7. AC3 -> test_get_dashboard_handles_not_found
  8. AC4 -> test_create_dashboard_returns_created_dashboard
  9. AC4 -> test_create_dashboard_requires_valid_json
  10. AC5 -> test_update_dashboard_returns_updated_dashboard
  11. AC5 -> test_update_dashboard_requires_existing_dashboard
  12. AC6 -> test_connection_error_raises_exception
  13. AC6 -> test_timeout_error_raises_exception
  14. AC7 -> test_auth_error_raises_exception
  15. AC7 -> test_permission_denied_raises_exception
  16. Edge Case: test_empty_dashboard_json
  17. Edge Case: test_dashboard_uid_with_special_characters
  18. Edge Case: test_large_dashboard_json
  19. Edge Case: test_nonexistent_api_key_env_var
  20. Edge Case: test_api_key_with_whitespace

Edge Cases:
  - Empty API key
  - API key with leading/trailing whitespace
  - Non-existent environment variable
  - Dashboard JSON with various valid structures
  - Dashboard UID with special characters
  - Large dashboard JSON payload
"""

import os
import sys
from unittest.mock import Mock, patch, MagicMock
import pytest

# These imports will fail since the implementation doesn't exist yet
try:
    from src.core.grafana_client import GrafanaClient
except ImportError:
    GrafanaClient = None


class TestGrafanaClientInitialization:
    """Test suite for GrafanaClient initialization."""

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-api-key-12345'})
    def test_client_initializes_with_api_key_from_env(self):
        """Test that GrafanaClient initializes with GRAFANA_API_KEY from environment."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        client = GrafanaClient()
        assert client.api_key == 'test-api-key-12345'

    def test_client_accepts_custom_api_key(self):
        """Test that GrafanaClient accepts a custom API key in __init__."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        client = GrafanaClient(api_key='custom-api-key')
        assert client.api_key == 'custom-api-key'

    @patch.dict(os.environ, {}, clear=True)
    def test_client_raises_error_without_api_key(self):
        """Test that GrafanaClient raises an error when API key is not provided."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        with pytest.raises(ValueError, match="GRAFANA_API_KEY environment variable"):
            GrafanaClient()

    def test_client_raises_error_with_empty_api_key(self):
        """Test that GrafanaClient raises an error with empty API key."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        with pytest.raises(ValueError, match="GRAFANA_API_KEY environment variable"):
            GrafanaClient(api_key='')

    def test_client_raises_error_with_whitespace_only_api_key(self):
        """Test that GrafanaClient raises an error with whitespace-only API key."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        with pytest.raises(ValueError, match="GRAFANA_API_KEY environment variable"):
            GrafanaClient(api_key='   ')

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key-with-spaces '}, clear=True)
    def test_client_accepts_api_key_with_trailing_whitespace(self):
        """Test that client trims whitespace from API key."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        client = GrafanaClient()
        assert client.api_key == 'test-key-with-spaces'


class TestGrafanaClientAuthentication:
    """Test suite for GrafanaClient authentication."""

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'valid-test-key'})
    @patch('requests.Session.request')
    def test_client_authenticates_with_valid_api_key(self, mock_request):
        """Test that client authenticates successfully with valid API key."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'message': 'Success'}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = GrafanaClient()
        client._get_headers()

        # Verify request was made
        mock_request.assert_called_once()

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'invalid-test-key'})
    @patch('requests.Session.request')
    def test_client_raises_error_with_invalid_api_key(self, mock_request):
        """Test that client raises authentication error with invalid API key."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock authentication failure (401)
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_response.raise_for_status = Mock(side_effect=Exception('401 Unauthorized'))
        mock_request.return_value = mock_response

        client = GrafanaClient()

        with pytest.raises(Exception, match="401|unauthorized|authentication failed"):
            client._get_headers()

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_client_auth_error_handling(self, mock_request):
        """Test that client properly handles authentication errors."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock various auth error scenarios
        error_codes = [401, 403]

        for status_code in error_codes:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = f'Error {status_code}'
            mock_response.raise_for_status = Mock(side_effect=Exception(f'HTTP {status_code}'))
            mock_request.return_value = mock_response

            client = GrafanaClient()
            with pytest.raises(Exception, match=f'HTTP {status_code}|unauthorized|forbidden'):
                client._get_headers()


class TestGetDashboard:
    """Test suite for get_dashboard method."""

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_get_dashboard_returns_dashboard_json(self, mock_request):
        """Test that get_dashboard returns dashboard JSON for valid UID."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock successful response with dashboard
        expected_dashboard = {
            'uid': 'test-uid',
            'title': 'Test Dashboard',
            'panels': []
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'dashboard': expected_dashboard}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = GrafanaClient()
        result = client.get_dashboard('test-uid')

        assert result == expected_dashboard
        mock_request.assert_called_once_with(
            'GET',
            'https://grafana.example.com/api/dashboards/uid/test-uid',
            headers=Mock(),  # Headers are set internally
            json=None,
            timeout=30
        )

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_get_dashboard_handles_not_found(self, mock_request):
        """Test that get_dashboard handles dashboard not found (404)."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Dashboard not found'
        mock_response.raise_for_status = Mock(side_effect=Exception('404 Not Found'))
        mock_request.return_value = mock_response

        client = GrafanaClient()

        with pytest.raises(Exception, match="404|not found"):
            client.get_dashboard('nonexistent-uid')

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_get_dashboard_requires_existing_dashboard(self, mock_request):
        """Test that get_dashboard fails gracefully if dashboard doesn't exist."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock various error responses
        error_statuses = [404, 403, 500]

        for status_code in error_statuses:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = f'Error: {status_code}'
            mock_response.raise_for_status = Mock(side_effect=Exception(f'HTTP {status_code}'))
            mock_request.return_value = mock_response

            client = GrafanaClient()
            with pytest.raises(Exception, match=f'HTTP {status_code}|error'):
                client.get_dashboard('some-uid')


class TestCreateDashboard:
    """Test suite for create_dashboard method."""

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_create_dashboard_returns_created_dashboard(self, mock_request):
        """Test that create_dashboard returns the created dashboard JSON."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock successful dashboard creation
        dashboard_json = {
            'uid': 'new-dashboard-uid',
            'title': 'New Dashboard',
            'panels': [{'type': 'text', 'title': 'Hello'}]
        }
        expected_response = {
            'dashboard': dashboard_json,
            'overwrite': False,
            'message': 'Dashboard created successfully'
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = GrafanaClient()
        result = client.create_dashboard(dashboard_json)

        assert result == dashboard_json
        mock_request.assert_called_once_with(
            'POST',
            'https://grafana.example.com/api/dashboards/db',
            headers=Mock(),
            json=dashboard_json,
            timeout=30
        )

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_create_dashboard_requires_valid_json(self, mock_request):
        """Test that create_dashboard validates dashboard JSON structure."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Invalid dashboard JSON (missing required fields)
        invalid_dashboard = {
            # Missing uid, title, etc.
        }
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Invalid dashboard JSON'
        mock_response.raise_for_status = Mock(side_effect=Exception('400 Bad Request'))
        mock_request.return_value = mock_response

        client = GrafanaClient()

        with pytest.raises(Exception, match="400|invalid"):
            client.create_dashboard(invalid_dashboard)

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_create_dashboard_handles_validation_error(self, mock_request):
        """Test that create_dashboard handles API validation errors."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock various validation error responses
        error_codes = [400, 422]

        for status_code in error_codes:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = f'Validation error: {status_code}'
            mock_response.raise_for_status = Mock(side_effect=Exception(f'HTTP {status_code}'))
            mock_request.return_value = mock_response

            client = GrafanaClient()
            with pytest.raises(Exception, match=f'HTTP {status_code}|validation'):
                client.create_dashboard({'uid': 'test', 'title': 'Test'})


class TestUpdateDashboard:
    """Test suite for update_dashboard method."""

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_update_dashboard_returns_updated_dashboard(self, mock_request):
        """Test that update_dashboard returns the updated dashboard JSON."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock successful dashboard update
        dashboard_json = {
            'uid': 'test-uid',
            'title': 'Updated Dashboard',
            'panels': [{'type': 'text', 'title': 'Updated'}]
        }
        expected_response = {
            'dashboard': dashboard_json,
            'overwrite': False,
            'message': 'Dashboard updated successfully'
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = GrafanaClient()
        result = client.update_dashboard('test-uid', dashboard_json)

        assert result == dashboard_json
        mock_request.assert_called_once_with(
            'PUT',
            'https://grafana.example.com/api/dashboards/uid/test-uid',
            headers=Mock(),
            json=dashboard_json,
            timeout=30
        )

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_update_dashboard_requires_existing_dashboard(self, mock_request):
        """Test that update_dashboard fails if dashboard doesn't exist."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock 404 response for non-existent dashboard
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Dashboard not found'
        mock_response.raise_for_status = Mock(side_effect=Exception('404 Not Found'))
        mock_request.return_value = mock_response

        client = GrafanaClient()

        with pytest.raises(Exception, match="404|not found"):
            client.update_dashboard('nonexistent-uid', {'uid': 'test', 'title': 'Test'})

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_update_dashboard_handles_permission_error(self, mock_request):
        """Test that update_dashboard handles permission errors."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock 403 response (permission denied)
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = 'Permission denied'
        mock_response.raise_for_status = Mock(side_effect=Exception('403 Forbidden'))
        mock_request.return_value = mock_response

        client = GrafanaClient()

        with pytest.raises(Exception, match="403|forbidden|permission"):
            client.update_dashboard('test-uid', {'uid': 'test', 'title': 'Test'})


class TestConnectionErrorHandling:
    """Test suite for connection error handling."""

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_connection_error_raises_exception(self, mock_request):
        """Test that client raises exception on connection error."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock connection error
        mock_request.side_effect = ConnectionError('Cannot connect to Grafana')

        client = GrafanaClient()

        with pytest.raises(ConnectionError, match="Cannot connect to Grafana"):
            client.get_dashboard('test-uid')

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_timeout_error_raises_exception(self, mock_request):
        """Test that client raises exception on timeout."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock timeout error
        mock_request.side_effect = TimeoutError('Request timed out')

        client = GrafanaClient()

        with pytest.raises(TimeoutError, match="Request timed out"):
            client.get_dashboard('test-uid')

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_connection_refused_error(self, mock_request):
        """Test that client handles connection refused errors."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Mock connection refused
        mock_request.side_effect = ConnectionRefusedError('Connection refused')

        client = GrafanaClient()

        with pytest.raises(ConnectionRefusedError):
            client.get_dashboard('test-uid')


class TestNonexistentEnvironmentVariable:
    """Test suite for handling missing environment variable."""

    @patch.dict(os.environ, {}, clear=True)
    def test_nonexistent_api_key_env_var(self):
        """Test that client raises error when GRAFANA_API_KEY doesn't exist."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        with pytest.raises(ValueError, match="GRAFANA_API_KEY environment variable"):
            GrafanaClient()

    @patch.dict(os.environ, {'GRAFANA_API_KEY': ''}, clear=True)
    def test_empty_api_key_env_var(self):
        """Test that client raises error when GRAFANA_API_KEY is empty string."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        with pytest.raises(ValueError, match="GRAFANA_API_KEY environment variable"):
            GrafanaClient()


class TestEdgeCases:
    """Test suite for edge cases."""

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_empty_dashboard_json(self, mock_request):
        """Test that client handles empty dashboard JSON gracefully."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        dashboard_json = {}
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'dashboard': dashboard_json}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = GrafanaClient()
        result = client.create_dashboard(dashboard_json)

        assert result == dashboard_json

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_dashboard_uid_with_special_characters(self, mock_request):
        """Test that client handles dashboard UIDs with special characters."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Dashboard UID with special characters and spaces
        uid = 'test-uid-with-special-chars_123'
        dashboard_json = {'uid': uid, 'title': 'Test'}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'dashboard': dashboard_json}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = GrafanaClient()
        result = client.get_dashboard(uid)

        assert result['uid'] == uid
        mock_request.assert_called_once_with(
            'GET',
            f'https://grafana.example.com/api/dashboards/uid/{uid}',
            headers=Mock(),
            json=None,
            timeout=30
        )

    @patch.dict(os.environ, {'GRAFANA_API_KEY': 'test-key'})
    @patch('requests.Session.request')
    def test_large_dashboard_json(self, mock_request):
        """Test that client handles large dashboard JSON payloads."""
        if GrafanaClient is None:
            pytest.skip("GrafanaClient not implemented yet")

        # Create a large dashboard JSON
        panels = [{'type': 'text', 'title': f'Panel {i}', 'gridPos': {'x': i*10, 'y': i*10, 'w': 12, 'h': 6}} for i in range(100)]
        dashboard_json = {
            'uid': 'large-dashboard',
            'title': 'Large Dashboard',
            'panels': panels
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'dashboard': dashboard_json}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = GrafanaClient()
        result = client.create_dashboard(dashboard_json)

        assert result['panels'] == panels
        assert len(result['panels']) == 100


# Exit code for pytest to report failures
fail_count = 0
if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])
