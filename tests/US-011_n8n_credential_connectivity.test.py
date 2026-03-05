"""
IMPLEMENTATION PLAN for US-011:
Configure N8N Credentials and Verify Connectivity

Components:
  - src/n8n/credential_manager.py: N8NCredentialManager
      - create_credential(name, credential_type, data) -> str  (credential_id)
      - create_apollo_credential(api_key) -> str
      - create_ipinfo_credential(token) -> str
      - create_apify_credential(api_token) -> str
      - create_mautic_credential(api_url, username, password) -> str
      - verify_apollo_connectivity(api_key) -> bool
      - verify_ipinfo_connectivity(token) -> bool
      - verify_apify_connectivity(api_token) -> bool
      - verify_mautic_connectivity(api_url, username, password) -> bool
      - verify_all_credentials(credential_map) -> dict[str, bool]
      - replace_workflow_placeholders(workflow_id, credential_map) -> bool
      - N8NCredentialError exception class

Data Flow:
  1. Manager creates each credential via POST /api/v1/credentials
  2. Manager calls each service's test endpoint to verify connectivity
  3. Manager patches N8N workflow to replace placeholder credential references
  4. verify_all_credentials returns a dict keyed by service name with bool values

Integration Points:
  - N8N REST API at http://localhost:8090/api/v1/
  - Apollo.io API: GET https://api.apollo.io/v1/auth/health
  - IPinfo API: GET https://ipinfo.io/1.1.1.1?token=...
  - Apify API: GET https://api.apify.com/v2/users/me?token=...
  - Mautic API: GET {api_url}/api/users/self (Basic Auth)

Edge Cases:
  - N8N API returns 401/403 → N8NCredentialError raised
  - External service returns non-2xx → verify returns False (not exception)
  - Network timeout on connectivity check → verify returns False
  - credential_map contains unknown service name → skip silently
  - Workflow ID not found when replacing placeholders → N8NCredentialError
  - Empty api_key / token → verify returns False immediately

Test Cases:
  1. [AC 1] Apollo.io credential created in N8N → test_create_apollo_credential_calls_n8n_api
  2. [AC 1] Apollo.io test call succeeds → test_verify_apollo_connectivity_success
  3. [AC 2] IPinfo credential created in N8N → test_create_ipinfo_credential_calls_n8n_api
  4. [AC 2] IPinfo test call succeeds → test_verify_ipinfo_connectivity_success
  5. [AC 3] Apify credential created in N8N → test_create_apify_credential_calls_n8n_api
  6. [AC 3] Apify test call succeeds → test_verify_apify_connectivity_success
  7. [AC 4] Mautic credential created in N8N → test_create_mautic_credential_calls_n8n_api
  8. [AC 4] Mautic test call succeeds → test_verify_mautic_connectivity_success
  9. [AC 5] verify_all_credentials returns dict with all four services → test_verify_all_credentials_returns_complete_dict
  10. [AC 5] All services return True when connectivity succeeds → test_verify_all_credentials_all_pass
  11. [AC 6] replace_workflow_placeholders patches workflow via N8N API → test_replace_workflow_placeholders_calls_patch
  12. Edge: Empty API key returns False from verify → test_empty_api_key_returns_false
  13. Edge: Network error on connectivity check returns False → test_network_error_returns_false
  14. Edge: N8N 401 on create raises N8NCredentialError → test_n8n_401_raises_credential_error
  15. Edge: Unknown workflow ID raises N8NCredentialError → test_unknown_workflow_raises_error
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Imports under test — will fail with ImportError until implemented (TDD-RED)
# ---------------------------------------------------------------------------
from src.n8n.credential_manager import N8NCredentialError, N8NCredentialManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
N8N_BASE_URL = "http://localhost:8090"
N8N_API_URL = f"{N8N_BASE_URL}/api/v1"
N8N_API_KEY = "test-n8n-api-key"

APOLLO_API_KEY = "test-apollo-key-abc123"
IPINFO_TOKEN = "test-ipinfo-token-xyz"
APIFY_API_TOKEN = "test-apify-token-def456"
MAUTIC_API_URL = "http://mautic.example.com"
MAUTIC_USERNAME = "api_user"
MAUTIC_PASSWORD = "api_pass_secure"


# ---------------------------------------------------------------------------
# AC 1 — Apollo.io credential created in N8N and test call succeeds
# ---------------------------------------------------------------------------
class TestApolloCredential(unittest.TestCase):
    """Tests for Apollo.io credential creation and connectivity verification."""

    def setUp(self):
        self.manager = N8NCredentialManager(api_url=N8N_API_URL, api_key=N8N_API_KEY)

    @patch("requests.post")
    def test_create_apollo_credential_calls_n8n_api(self, mock_post):
        """Creating Apollo credential posts to N8N /credentials endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "cred-apollo-001", "name": "Apollo.io API Key"}
        mock_post.return_value = mock_response

        credential_id = self.manager.create_apollo_credential(APOLLO_API_KEY)

        self.assertEqual(credential_id, "cred-apollo-001")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("/credentials", call_args[0][0])
        # Verify API key is in the posted data
        posted_json = call_args[1].get("json", call_args[0][1] if len(call_args[0]) > 1 else {})
        self.assertIn(APOLLO_API_KEY, str(posted_json))

    @patch("requests.get")
    def test_verify_apollo_connectivity_success(self, mock_get):
        """Apollo connectivity check returns True when service responds 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"is_logged_in": True}
        mock_get.return_value = mock_response

        result = self.manager.verify_apollo_connectivity(APOLLO_API_KEY)

        self.assertTrue(result)
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertIn("apollo.io", call_url)

    @patch("requests.get")
    def test_verify_apollo_connectivity_failure(self, mock_get):
        """Apollo connectivity check returns False when service responds non-2xx."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = self.manager.verify_apollo_connectivity(APOLLO_API_KEY)

        self.assertFalse(result)


# ---------------------------------------------------------------------------
# AC 2 — IPinfo token credential created in N8N and test call succeeds
# ---------------------------------------------------------------------------
class TestIPinfoCredential(unittest.TestCase):
    """Tests for IPinfo credential creation and connectivity verification."""

    def setUp(self):
        self.manager = N8NCredentialManager(api_url=N8N_API_URL, api_key=N8N_API_KEY)

    @patch("requests.post")
    def test_create_ipinfo_credential_calls_n8n_api(self, mock_post):
        """Creating IPinfo credential posts to N8N /credentials endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "cred-ipinfo-001", "name": "IPinfo Token"}
        mock_post.return_value = mock_response

        credential_id = self.manager.create_ipinfo_credential(IPINFO_TOKEN)

        self.assertEqual(credential_id, "cred-ipinfo-001")
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        self.assertIn("/credentials", call_url)

    @patch("requests.get")
    def test_verify_ipinfo_connectivity_success(self, mock_get):
        """IPinfo connectivity check returns True when service responds 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ip": "1.1.1.1", "country": "AU"}
        mock_get.return_value = mock_response

        result = self.manager.verify_ipinfo_connectivity(IPINFO_TOKEN)

        self.assertTrue(result)
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertIn("ipinfo.io", call_url)

    @patch("requests.get")
    def test_verify_ipinfo_connectivity_failure(self, mock_get):
        """IPinfo connectivity check returns False when service responds non-2xx."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        result = self.manager.verify_ipinfo_connectivity(IPINFO_TOKEN)

        self.assertFalse(result)


# ---------------------------------------------------------------------------
# AC 3 — Apify API token credential created in N8N and test call succeeds
# ---------------------------------------------------------------------------
class TestApifyCredential(unittest.TestCase):
    """Tests for Apify credential creation and connectivity verification."""

    def setUp(self):
        self.manager = N8NCredentialManager(api_url=N8N_API_URL, api_key=N8N_API_KEY)

    @patch("requests.post")
    def test_create_apify_credential_calls_n8n_api(self, mock_post):
        """Creating Apify credential posts to N8N /credentials endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "cred-apify-001", "name": "Apify API Token"}
        mock_post.return_value = mock_response

        credential_id = self.manager.create_apify_credential(APIFY_API_TOKEN)

        self.assertEqual(credential_id, "cred-apify-001")
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        self.assertIn("/credentials", call_url)

    @patch("requests.get")
    def test_verify_apify_connectivity_success(self, mock_get):
        """Apify connectivity check returns True when service responds 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"id": "user123", "username": "testuser"}}
        mock_get.return_value = mock_response

        result = self.manager.verify_apify_connectivity(APIFY_API_TOKEN)

        self.assertTrue(result)
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertIn("apify.com", call_url)

    @patch("requests.get")
    def test_verify_apify_connectivity_failure(self, mock_get):
        """Apify connectivity check returns False when service responds non-2xx."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = self.manager.verify_apify_connectivity(APIFY_API_TOKEN)

        self.assertFalse(result)


# ---------------------------------------------------------------------------
# AC 4 — Mautic API authentication configured and test call succeeds
# ---------------------------------------------------------------------------
class TestMauticCredential(unittest.TestCase):
    """Tests for Mautic credential creation and connectivity verification."""

    def setUp(self):
        self.manager = N8NCredentialManager(api_url=N8N_API_URL, api_key=N8N_API_KEY)

    @patch("requests.post")
    def test_create_mautic_credential_calls_n8n_api(self, mock_post):
        """Creating Mautic credential posts to N8N /credentials endpoint with URL+auth."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "cred-mautic-001", "name": "Mautic API"}
        mock_post.return_value = mock_response

        credential_id = self.manager.create_mautic_credential(
            MAUTIC_API_URL, MAUTIC_USERNAME, MAUTIC_PASSWORD
        )

        self.assertEqual(credential_id, "cred-mautic-001")
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        self.assertIn("/credentials", call_url)
        # Mautic requires URL to be stored with credential
        posted_json = mock_post.call_args[1].get("json", {})
        self.assertIn(MAUTIC_API_URL, str(posted_json))

    @patch("requests.get")
    def test_verify_mautic_connectivity_success(self, mock_get):
        """Mautic connectivity check returns True when /api/users/self responds 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "username": MAUTIC_USERNAME}
        mock_get.return_value = mock_response

        result = self.manager.verify_mautic_connectivity(
            MAUTIC_API_URL, MAUTIC_USERNAME, MAUTIC_PASSWORD
        )

        self.assertTrue(result)
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertIn(MAUTIC_API_URL, call_url)
        self.assertIn("users", call_url)

    @patch("requests.get")
    def test_verify_mautic_connectivity_failure(self, mock_get):
        """Mautic connectivity check returns False when service responds non-2xx."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = self.manager.verify_mautic_connectivity(
            MAUTIC_API_URL, MAUTIC_USERNAME, MAUTIC_PASSWORD
        )

        self.assertFalse(result)

    @patch("requests.get")
    def test_verify_mautic_uses_basic_auth(self, mock_get):
        """Mautic connectivity check uses HTTP Basic Auth with username/password."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1}
        mock_get.return_value = mock_response

        self.manager.verify_mautic_connectivity(
            MAUTIC_API_URL, MAUTIC_USERNAME, MAUTIC_PASSWORD
        )

        # Basic auth should be passed as 'auth' kwarg or in headers
        call_kwargs = mock_get.call_args[1]
        has_auth = (
            "auth" in call_kwargs
            or "Authorization" in str(call_kwargs.get("headers", {}))
        )
        self.assertTrue(has_auth, "Expected Basic Auth to be configured for Mautic request")


# ---------------------------------------------------------------------------
# AC 5 — All credential connections verified working
# ---------------------------------------------------------------------------
class TestVerifyAllCredentials(unittest.TestCase):
    """Tests for verifying all four service credentials together."""

    def setUp(self):
        self.manager = N8NCredentialManager(api_url=N8N_API_URL, api_key=N8N_API_KEY)
        self.credential_map = {
            "apollo": {"api_key": APOLLO_API_KEY},
            "ipinfo": {"token": IPINFO_TOKEN},
            "apify": {"api_token": APIFY_API_TOKEN},
            "mautic": {
                "api_url": MAUTIC_API_URL,
                "username": MAUTIC_USERNAME,
                "password": MAUTIC_PASSWORD,
            },
        }

    def test_verify_all_credentials_returns_complete_dict(self):
        """verify_all_credentials returns a dict with keys for all four services."""
        with patch.object(self.manager, "verify_apollo_connectivity", return_value=True), \
             patch.object(self.manager, "verify_ipinfo_connectivity", return_value=True), \
             patch.object(self.manager, "verify_apify_connectivity", return_value=True), \
             patch.object(self.manager, "verify_mautic_connectivity", return_value=True):

            results = self.manager.verify_all_credentials(self.credential_map)

        self.assertIsInstance(results, dict)
        self.assertIn("apollo", results)
        self.assertIn("ipinfo", results)
        self.assertIn("apify", results)
        self.assertIn("mautic", results)

    def test_verify_all_credentials_all_pass(self):
        """verify_all_credentials returns True for all services when connectivity succeeds."""
        with patch.object(self.manager, "verify_apollo_connectivity", return_value=True), \
             patch.object(self.manager, "verify_ipinfo_connectivity", return_value=True), \
             patch.object(self.manager, "verify_apify_connectivity", return_value=True), \
             patch.object(self.manager, "verify_mautic_connectivity", return_value=True):

            results = self.manager.verify_all_credentials(self.credential_map)

        self.assertTrue(results["apollo"])
        self.assertTrue(results["ipinfo"])
        self.assertTrue(results["apify"])
        self.assertTrue(results["mautic"])

    def test_verify_all_credentials_partial_failure(self):
        """verify_all_credentials correctly reports False for failing services."""
        with patch.object(self.manager, "verify_apollo_connectivity", return_value=False), \
             patch.object(self.manager, "verify_ipinfo_connectivity", return_value=True), \
             patch.object(self.manager, "verify_apify_connectivity", return_value=True), \
             patch.object(self.manager, "verify_mautic_connectivity", return_value=True):

            results = self.manager.verify_all_credentials(self.credential_map)

        self.assertFalse(results["apollo"])
        self.assertTrue(results["ipinfo"])

    def test_verify_all_credentials_delegates_to_service_methods(self):
        """verify_all_credentials calls each individual verify method."""
        with patch.object(self.manager, "verify_apollo_connectivity", return_value=True) as mock_apollo, \
             patch.object(self.manager, "verify_ipinfo_connectivity", return_value=True) as mock_ipinfo, \
             patch.object(self.manager, "verify_apify_connectivity", return_value=True) as mock_apify, \
             patch.object(self.manager, "verify_mautic_connectivity", return_value=True) as mock_mautic:

            self.manager.verify_all_credentials(self.credential_map)

        mock_apollo.assert_called_once_with(APOLLO_API_KEY)
        mock_ipinfo.assert_called_once_with(IPINFO_TOKEN)
        mock_apify.assert_called_once_with(APIFY_API_TOKEN)
        mock_mautic.assert_called_once_with(MAUTIC_API_URL, MAUTIC_USERNAME, MAUTIC_PASSWORD)


# ---------------------------------------------------------------------------
# AC 6 — Credential placeholders replaced with actual configured values
# ---------------------------------------------------------------------------
class TestReplaceWorkflowPlaceholders(unittest.TestCase):
    """Tests for replacing placeholder credentials in N8N workflows."""

    def setUp(self):
        self.manager = N8NCredentialManager(api_url=N8N_API_URL, api_key=N8N_API_KEY)
        self.workflow_id = "wf-lead-scoring-001"
        self.credential_map = {
            "apollo": "cred-apollo-001",
            "ipinfo": "cred-ipinfo-001",
            "apify": "cred-apify-001",
            "mautic": "cred-mautic-001",
        }

    @patch("requests.patch")
    @patch("requests.get")
    def test_replace_workflow_placeholders_calls_patch(self, mock_get, mock_patch):
        """replace_workflow_placeholders fetches workflow and patches it via N8N API."""
        # Mock GET /workflows/{id}
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "id": self.workflow_id,
            "nodes": [
                {
                    "type": "n8n-nodes-base.httpRequest",
                    "credentials": {"apolloApi": {"id": "PLACEHOLDER_APOLLO"}},
                }
            ],
        }
        mock_get.return_value = mock_get_response

        # Mock PATCH /workflows/{id}
        mock_patch_response = MagicMock()
        mock_patch_response.status_code = 200
        mock_patch_response.json.return_value = {"id": self.workflow_id, "active": True}
        mock_patch.return_value = mock_patch_response

        result = self.manager.replace_workflow_placeholders(self.workflow_id, self.credential_map)

        self.assertTrue(result)
        mock_get.assert_called_once()
        mock_patch.assert_called_once()
        patch_url = mock_patch.call_args[0][0]
        self.assertIn(self.workflow_id, patch_url)

    @patch("requests.get")
    def test_replace_workflow_placeholders_raises_on_unknown_workflow(self, mock_get):
        """replace_workflow_placeholders raises N8NCredentialError when workflow not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response

        with self.assertRaises(N8NCredentialError):
            self.manager.replace_workflow_placeholders("nonexistent-wf", self.credential_map)


# ---------------------------------------------------------------------------
# Edge Cases — create_credential generic method + error handling
# ---------------------------------------------------------------------------
class TestEdgeCases(unittest.TestCase):
    """Edge case and error handling tests."""

    def setUp(self):
        self.manager = N8NCredentialManager(api_url=N8N_API_URL, api_key=N8N_API_KEY)

    def test_empty_api_key_returns_false_for_apollo(self):
        """verify_apollo_connectivity returns False immediately for empty api_key."""
        result = self.manager.verify_apollo_connectivity("")
        self.assertFalse(result)

    def test_empty_token_returns_false_for_ipinfo(self):
        """verify_ipinfo_connectivity returns False immediately for empty token."""
        result = self.manager.verify_ipinfo_connectivity("")
        self.assertFalse(result)

    def test_empty_api_token_returns_false_for_apify(self):
        """verify_apify_connectivity returns False immediately for empty api_token."""
        result = self.manager.verify_apify_connectivity("")
        self.assertFalse(result)

    @patch("requests.get")
    def test_network_error_returns_false_not_exception(self, mock_get):
        """Network errors during connectivity check return False, not raise exception."""
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.ConnectionError("Connection refused")

        result = self.manager.verify_apollo_connectivity(APOLLO_API_KEY)
        self.assertFalse(result)

    @patch("requests.get")
    def test_timeout_returns_false_not_exception(self, mock_get):
        """Timeout during connectivity check returns False, not raise exception."""
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout("Request timed out")

        result = self.manager.verify_ipinfo_connectivity(IPINFO_TOKEN)
        self.assertFalse(result)

    @patch("requests.post")
    def test_n8n_401_raises_credential_error_on_create(self, mock_post):
        """N8N 401 response during credential creation raises N8NCredentialError."""
        import requests as req_lib
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = req_lib.exceptions.HTTPError("401 Unauthorized")
        mock_post.return_value = mock_response

        with self.assertRaises(N8NCredentialError):
            self.manager.create_apollo_credential(APOLLO_API_KEY)

    @patch("requests.post")
    def test_create_credential_generic_method(self, mock_post):
        """create_credential posts to N8N /credentials with provided name, type, and data."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "cred-generic-001", "name": "My Cred"}
        mock_post.return_value = mock_response

        credential_id = self.manager.create_credential(
            name="My Cred",
            credential_type="httpBasicAuth",
            data={"user": "admin", "password": "secret"},
        )

        self.assertEqual(credential_id, "cred-generic-001")
        mock_post.assert_called_once()
        posted_json = mock_post.call_args[1].get("json", {})
        self.assertEqual(posted_json.get("name"), "My Cred")
        self.assertEqual(posted_json.get("type"), "httpBasicAuth")

    def test_manager_sets_correct_auth_header(self):
        """N8NCredentialManager sets X-N8N-API-KEY header from constructor."""
        self.assertEqual(self.manager.headers.get("X-N8N-API-KEY"), N8N_API_KEY)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (
        TestApolloCredential,
        TestIPinfoCredential,
        TestApifyCredential,
        TestMauticCredential,
        TestVerifyAllCredentials,
        TestReplaceWorkflowPlaceholders,
        TestEdgeCases,
    ):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
