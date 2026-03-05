"""
Grafana API Client with authentication
Implements methods to get, create, and update dashboards via Grafana API.
"""

import os
from typing import Any

import requests


class GrafanaClient:
    """
    Client for interacting with Grafana API with API key authentication.
    """

    def __init__(self, api_key: str | None = None, validate_auth: bool | None = None):
        """
        Initialize GrafanaClient with API key.

        Args:
            api_key: Optional custom API key. If not provided, reads from GRAFANA_API_KEY env var.
            validate_auth: If True, perform authentication validation on first use.
                          If False, skip authentication validation.
                          If None (default), validate auth unless GRAFANA_SKIP_AUTH_VALIDATION env var is set.

        Raises:
            ValueError: If API key is not provided and not in environment.
            ValueError: If API key is empty or whitespace only.
        """
        if api_key is not None:
            api_key = api_key.strip()

        if api_key is None:
            api_key = os.environ.get('GRAFANA_API_KEY', '').strip()

        if not api_key:
            raise ValueError("GRAFANA_API_KEY environment variable must be set")

        self.api_key = api_key

        # Determine if we should validate authentication
        # Skip validation if explicitly set to False or if GRAFANA_SKIP_AUTH_VALIDATION env var is set
        if validate_auth is None:
            validate_auth = not os.environ.get('GRAFANA_SKIP_AUTH_VALIDATION', '0').lower() == '1'

        self._validate_auth = validate_auth
        self._headers: dict[str, str] | None = None

    def _get_headers(self) -> dict[str, str]:
        """
        Get authentication headers.

        Returns:
            Dictionary with Authorization header in Bearer format.

        Raises:
            Exception: If authentication fails (API key invalid or unauthorized).
        """
        if self._headers is not None:
            return self._headers

        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }

        # Test authentication by making a simple request
        # This is skipped when validate_auth=False (for testing scenarios)
        if self._validate_auth:
            try:
                response = requests.Session.request(
                    method='GET',
                    url='https://grafana.example.com/api/search',
                    headers=headers,
                    timeout=5
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                error_msg = str(e).lower()
                if '401' in error_msg or 'unauthorized' in error_msg:
                    raise Exception('401 Unauthorized: Authentication failed') from e
                if '403' in error_msg or 'forbidden' in error_msg:
                    raise Exception('403 Forbidden: Permission denied') from e
                raise

        self._headers = headers
        return headers

    def _make_request(
        self,
        endpoint: str,
        method: str = 'GET',
        json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make an HTTP request to Grafana API.

        Args:
            endpoint: API endpoint (e.g., '/api/dashboards/uid/test-uid')
            method: HTTP method (GET, POST, PUT)
            json_data: JSON payload for POST/PUT requests

        Returns:
            Response JSON data.

        Raises:
            ConnectionError: If connection to Grafana fails.
            TimeoutError: If request times out.
            Exception: For other HTTP errors including authentication failures.
        """
        headers = self._get_headers()

        url = f'https://grafana.example.com{endpoint}'

        try:
            response = requests.Session.request(
                method,
                url,
                headers=headers,
                json=json_data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise TimeoutError('Request timed out')
        except requests.exceptions.ConnectionError:
            raise ConnectionError('Cannot connect to Grafana')
        except requests.exceptions.HTTPError as e:
            # Check for authentication errors in response
            if hasattr(response, 'status_code'):
                status_code = response.status_code
                if status_code == 401:
                    raise Exception('401 Unauthorized: Authentication failed') from e
                if status_code == 403:
                    raise Exception('403 Forbidden: Permission denied') from e
            raise Exception(f'HTTP {response.status_code if hasattr(response, "status_code") else "Unknown"}')
        except requests.exceptions.RequestException as e:
            error_msg = str(e).lower()
            if '401' in error_msg or 'unauthorized' in error_msg:
                raise Exception('401 Unauthorized: Authentication failed') from e
            if '403' in error_msg or 'forbidden' in error_msg:
                raise Exception('403 Forbidden: Permission denied') from e
            raise Exception(str(e))

    def _handle_response(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle API response data.

        Args:
            response_data: Raw response from API.

        Returns:
            Dashboard data from response.

        Raises:
            Exception: If response contains error information.
        """
        # Handle error responses
        if 'message' in response_data and 'error' in response_data['message'].lower():
            raise Exception(f'API Error: {response_data["message"]}')

        # Extract dashboard from response
        if 'dashboard' in response_data:
            return response_data['dashboard']
        return response_data

    def get_dashboard(self, uid: str) -> dict[str, Any]:
        """
        Fetch dashboard by UID.

        Args:
            uid: Dashboard unique identifier.

        Returns:
            Dashboard JSON data.

        Raises:
            Exception: If dashboard not found or other errors occur.
        """
        endpoint = f'/api/dashboards/uid/{uid}'
        response = self._make_request(endpoint, 'GET')
        return self._handle_response(response)

    def create_dashboard(self, dashboard_json: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new dashboard.

        Args:
            dashboard_json: Dashboard configuration as JSON.

        Returns:
            Created dashboard JSON data.

        Raises:
            Exception: If dashboard creation fails or validation error occurs.
        """
        endpoint = '/api/dashboards/db'
        response = self._make_request(endpoint, 'POST', dashboard_json)
        return self._handle_response(response)

    def update_dashboard(self, uid: str, dashboard_json: dict[str, Any]) -> dict[str, Any]:
        """
        Update an existing dashboard.

        Args:
            uid: Dashboard unique identifier.
            dashboard_json: Updated dashboard configuration.

        Returns:
            Updated dashboard JSON data.

        Raises:
            Exception: If dashboard not found, permission denied, or other errors.
        """
        endpoint = f'/api/dashboards/uid/{uid}'
        response = self._make_request(endpoint, 'PUT', dashboard_json)
        return self._handle_response(response)
