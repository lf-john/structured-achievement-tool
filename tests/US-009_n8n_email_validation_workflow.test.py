"""
IMPLEMENTATION PLAN for US-009:
Test workflow in N8N environment

Components:
  - email-validation-pipeline.json: N8N workflow export file with 8 nodes
    (Webhook/Manual Trigger, Fetch Contacts, Email Validator, Disposable Check,
    Role Account Check, Free Email Check, Update Mautic data_quality, Log Writer)
  - src/n8n/workflow_importer.py: N8NWorkflowImporter - imports workflow JSON to N8N API,
    verifies node count, and checks credential configuration
  - src/email_automation/email_validator.py: EmailValidator - classifies emails as
    valid_business, invalid_syntax, disposable_domain, role_account, free_email
  - src/email_automation/validation_logger.py: ValidationLogger - appends results to
    validation-log.csv with email, classification, score, timestamp columns

Data Flow:
  1. N8N imports email-validation-pipeline.json via API POST /api/v1/workflows
  2. Workflow fetches contacts from Mautic, runs EmailValidator per contact
  3. Result written to Mautic contact field data_quality (High/Medium/Low/Unverified)
  4. Each classification appended to validation-log.csv

Integration Points:
  - N8N REST API at http://localhost:8090/api/v1/
  - Mautic API via MauticApiClient (update_contact with data_quality payload)
  - validation-log.csv in project root or configurable output path

Edge Cases:
  - Email with valid syntax but disposable domain → data_quality=Low
  - Role account (info@, admin@, noreply@) → data_quality=Low
  - Free email (gmail, yahoo, hotmail) → data_quality=Medium
  - Completely invalid syntax → data_quality=Unverified
  - Valid business email → data_quality=High
  - DNS timeout during MX record lookup → graceful fallback, no crash
  - N8N API unavailable → ImportError raised with clear message
  - CSV already exists → rows appended, not overwritten

Test Cases:
  1. [AC 1] Workflow JSON file exists at expected path → test_workflow_json_file_exists
  2. [AC 1] Workflow imported into N8N without errors → test_import_workflow_succeeds
  3. [AC 2] Mautic API credentials retrievable from N8N → test_mautic_credentials_configured
  4. [AC 3] Test batch of 10-20 emails processed without crash → test_batch_processed_without_crash
  5. [AC 4] Workflow has exactly 8 nodes → test_workflow_has_eight_nodes
  6. [AC 5] Valid business email → data_quality=High update sent to Mautic → test_valid_email_updates_data_quality_high
  7. [AC 5] Disposable domain → data_quality=Low update sent to Mautic → test_disposable_updates_data_quality_low
  8. [AC 6] validation-log.csv created after batch run → test_validation_log_csv_created
  9. [AC 6] CSV contains expected columns → test_validation_log_has_expected_columns
  10. [AC 7] Invalid syntax email scored as Unverified → test_invalid_syntax_classified_unverified
  11. [AC 7] Role account scored as Low → test_role_account_classified_low
  12. [AC 7] Free email scored as Medium → test_free_email_classified_medium
  13. [AC 8] DNS timeout does not raise exception → test_dns_timeout_handled_gracefully
  14. Edge: Empty email string → classified as invalid_syntax → test_empty_email_classified_invalid
  15. Edge: CSV appends rows on second run → test_csv_appends_not_overwrites
"""

import csv
import json
import os
import sys
import tempfile
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
from src.email_automation.email_validator import EmailValidator
from src.email_automation.validation_logger import ValidationLogger
from src.n8n.workflow_importer import N8NWorkflowImporter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKFLOW_JSON_PATH = PROJECT_ROOT / "email-validation-pipeline.json"
N8N_BASE_URL = "http://localhost:8090"
N8N_API_URL = f"{N8N_BASE_URL}/api/v1"

SAMPLE_EMAILS = [
    "john.doe@company.com",          # valid business
    "not-an-email",                  # invalid syntax
    "user@mailinator.com",           # disposable domain
    "user@guerrillamail.com",        # disposable domain
    "info@business.com",             # role account
    "admin@example.com",             # role account
    "noreply@service.com",           # role account
    "user@gmail.com",                # free email
    "test@yahoo.com",                # free email
    "contact@hotmail.com",           # free email
    "jane.smith@enterprise.org",     # valid business
    "support@validcorp.net",         # role account (support)
    "sales@acme.io",                 # valid business (sales is borderline but not pure role)
    "user@10minutemail.com",         # disposable
    "",                              # empty / invalid
]


class TestWorkflowJsonFile(unittest.TestCase):
    """AC 1 — Workflow JSON file exists and is valid."""

    def test_workflow_json_file_exists(self):
        """email-validation-pipeline.json must exist in project root."""
        self.assertTrue(
            WORKFLOW_JSON_PATH.exists(),
            f"Workflow file not found at {WORKFLOW_JSON_PATH}"
        )

    def test_workflow_json_is_valid_json(self):
        """email-validation-pipeline.json must be parseable JSON."""
        with open(WORKFLOW_JSON_PATH) as fh:
            data = json.load(fh)
        self.assertIsInstance(data, dict)

    def test_workflow_has_eight_nodes(self):
        """AC 4 — Workflow must contain exactly 8 nodes."""
        with open(WORKFLOW_JSON_PATH) as fh:
            data = json.load(fh)
        nodes = data.get("nodes", [])
        self.assertEqual(
            len(nodes),
            8,
            f"Expected 8 nodes, got {len(nodes)}: {[n.get('name') for n in nodes]}"
        )

    def test_workflow_has_name_field(self):
        """Workflow JSON must have a name field (required by N8N import)."""
        with open(WORKFLOW_JSON_PATH) as fh:
            data = json.load(fh)
        self.assertIn("name", data)
        self.assertIsInstance(data["name"], str)
        self.assertGreater(len(data["name"]), 0)


class TestN8NWorkflowImporter(unittest.TestCase):
    """AC 1 & 2 — Import workflow into N8N and configure credentials."""

    def setUp(self):
        self.importer = N8NWorkflowImporter(
            api_url=N8N_API_URL,
            api_key="test-n8n-api-key"
        )

    @patch("requests.post")
    def test_import_workflow_succeeds(self, mock_post):
        """AC 1 — import_workflow returns workflow ID on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "wf-123", "name": "email-validation-pipeline"}
        mock_post.return_value = mock_response

        workflow_id = self.importer.import_workflow(str(WORKFLOW_JSON_PATH))

        self.assertEqual(workflow_id, "wf-123")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("/workflows", call_args[0][0])

    @patch("requests.post")
    def test_import_workflow_raises_on_api_error(self, mock_post):
        """AC 1 — import_workflow raises N8NImportError when API returns 4xx/5xx."""
        import requests
        mock_post.side_effect = requests.RequestException("Connection refused")

        with self.assertRaises(Exception):
            self.importer.import_workflow(str(WORKFLOW_JSON_PATH))

    @patch("requests.get")
    def test_mautic_credentials_configured(self, mock_get):
        """AC 2 — get_credentials returns Mautic credential entry when configured."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "cred-1", "name": "Mautic API", "type": "mauticApi"}
            ]
        }
        mock_get.return_value = mock_response

        creds = self.importer.get_credentials()

        mautic_creds = [c for c in creds if "mautic" in c.get("type", "").lower()]
        self.assertGreater(
            len(mautic_creds), 0,
            "No Mautic credentials found in N8N"
        )

    @patch("requests.get")
    def test_get_credentials_returns_list(self, mock_get):
        """get_credentials always returns a list (never None)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        result = self.importer.get_credentials()
        self.assertIsInstance(result, list)


class TestEmailValidator(unittest.TestCase):
    """AC 3, 7 — Email classification logic."""

    def setUp(self):
        self.validator = EmailValidator()

    def test_valid_business_email_classified_high(self):
        """AC 7 — Valid business email returns classification=valid_business, quality=High."""
        result = self.validator.validate("john.doe@company.com")
        self.assertEqual(result["classification"], "valid_business")
        self.assertEqual(result["data_quality"], "High")

    def test_invalid_syntax_classified_unverified(self):
        """AC 7 — Malformed email returns classification=invalid_syntax, quality=Unverified."""
        result = self.validator.validate("not-an-email")
        self.assertEqual(result["classification"], "invalid_syntax")
        self.assertEqual(result["data_quality"], "Unverified")

    def test_disposable_domain_classified_low(self):
        """AC 7 — Disposable domain returns classification=disposable_domain, quality=Low."""
        result = self.validator.validate("user@mailinator.com")
        self.assertEqual(result["classification"], "disposable_domain")
        self.assertEqual(result["data_quality"], "Low")

    def test_guerrillamail_classified_disposable(self):
        """AC 7 — guerrillamail.com is a known disposable domain."""
        result = self.validator.validate("user@guerrillamail.com")
        self.assertEqual(result["classification"], "disposable_domain")
        self.assertEqual(result["data_quality"], "Low")

    def test_role_account_info_classified_low(self):
        """AC 7 — info@ prefix is a role account, quality=Low."""
        result = self.validator.validate("info@business.com")
        self.assertEqual(result["classification"], "role_account")
        self.assertEqual(result["data_quality"], "Low")

    def test_role_account_admin_classified_low(self):
        """AC 7 — admin@ prefix is a role account, quality=Low."""
        result = self.validator.validate("admin@example.com")
        self.assertEqual(result["classification"], "role_account")
        self.assertEqual(result["data_quality"], "Low")

    def test_role_account_noreply_classified_low(self):
        """AC 7 — noreply@ prefix is a role account, quality=Low."""
        result = self.validator.validate("noreply@service.com")
        self.assertEqual(result["classification"], "role_account")
        self.assertEqual(result["data_quality"], "Low")

    def test_free_email_gmail_classified_medium(self):
        """AC 7 — Gmail is a free email provider, quality=Medium."""
        result = self.validator.validate("user@gmail.com")
        self.assertEqual(result["classification"], "free_email")
        self.assertEqual(result["data_quality"], "Medium")

    def test_free_email_yahoo_classified_medium(self):
        """AC 7 — Yahoo is a free email provider, quality=Medium."""
        result = self.validator.validate("test@yahoo.com")
        self.assertEqual(result["classification"], "free_email")
        self.assertEqual(result["data_quality"], "Medium")

    def test_free_email_hotmail_classified_medium(self):
        """AC 7 — Hotmail is a free email provider, quality=Medium."""
        result = self.validator.validate("contact@hotmail.com")
        self.assertEqual(result["classification"], "free_email")
        self.assertEqual(result["data_quality"], "Medium")

    def test_empty_email_classified_invalid(self):
        """Edge — Empty string classified as invalid_syntax."""
        result = self.validator.validate("")
        self.assertEqual(result["classification"], "invalid_syntax")
        self.assertEqual(result["data_quality"], "Unverified")

    def test_validate_returns_required_fields(self):
        """validate() result must contain email, classification, data_quality, score keys."""
        result = self.validator.validate("john.doe@company.com")
        for field in ("email", "classification", "data_quality", "score"):
            self.assertIn(field, result, f"Missing field: {field}")

    def test_score_is_numeric(self):
        """validate() result score must be a number between 0 and 100."""
        result = self.validator.validate("john.doe@company.com")
        self.assertIsInstance(result["score"], (int, float))
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    def test_dns_timeout_handled_gracefully(self):
        """AC 8 — DNS timeout during MX lookup must not raise an exception."""
        with patch.object(self.validator, "_lookup_mx", side_effect=TimeoutError("DNS timeout")):
            try:
                result = self.validator.validate("user@unknown-domain-xyz.com")
                # Should not raise; result should be a dict
                self.assertIsInstance(result, dict)
            except TimeoutError:
                self.fail("EmailValidator raised TimeoutError on DNS timeout")

    def test_batch_processed_without_crash(self):
        """AC 3 — Processing 10-20 sample emails returns a result for each."""
        results = [self.validator.validate(email) for email in SAMPLE_EMAILS]
        self.assertEqual(len(results), len(SAMPLE_EMAILS))
        for r in results:
            self.assertIsInstance(r, dict)
            self.assertIn("data_quality", r)


class TestMauticDataQualityUpdate(unittest.TestCase):
    """AC 5 — data_quality field updated in Mautic after validation."""

    def setUp(self):
        self.validator = EmailValidator()

    @patch("src.email_automation.email_validator.MauticApiClient")
    def test_valid_email_updates_data_quality_high(self, mock_client_cls):
        """AC 5 — Valid business email triggers Mautic update with data_quality=High."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.update_contact.return_value = {"contact": {"id": 1}, "status": "success"}

        self.validator.validate_and_update(
            email="john.doe@company.com",
            contact_id=1,
            mautic_url="http://localhost",
            mautic_token="tok"
        )

        mock_client.update_contact.assert_called_once()
        call_kwargs = mock_client.update_contact.call_args
        payload = call_kwargs[0][1] if call_kwargs[0] else call_kwargs[1].get("payload", {})
        self.assertEqual(payload.get("data_quality"), "High")

    @patch("src.email_automation.email_validator.MauticApiClient")
    def test_disposable_updates_data_quality_low(self, mock_client_cls):
        """AC 5 — Disposable email triggers Mautic update with data_quality=Low."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.update_contact.return_value = {"contact": {"id": 2}, "status": "success"}

        self.validator.validate_and_update(
            email="user@mailinator.com",
            contact_id=2,
            mautic_url="http://localhost",
            mautic_token="tok"
        )

        mock_client.update_contact.assert_called_once()
        call_kwargs = mock_client.update_contact.call_args
        payload = call_kwargs[0][1] if call_kwargs[0] else call_kwargs[1].get("payload", {})
        self.assertEqual(payload.get("data_quality"), "Low")


class TestValidationLogger(unittest.TestCase):
    """AC 6 — validation-log.csv created and populated correctly."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.tmp_dir, "validation-log.csv")
        self.logger = ValidationLogger(output_path=self.csv_path)

    def tearDown(self):
        if os.path.exists(self.csv_path):
            os.remove(self.csv_path)
        os.rmdir(self.tmp_dir)

    def test_validation_log_csv_created(self):
        """AC 6 — log_result() creates validation-log.csv if it doesn't exist."""
        self.logger.log_result(
            email="john.doe@company.com",
            classification="valid_business",
            data_quality="High",
            score=90
        )
        self.assertTrue(os.path.exists(self.csv_path))

    def test_validation_log_has_expected_columns(self):
        """AC 6 — CSV contains email, classification, data_quality, score, timestamp columns."""
        self.logger.log_result(
            email="test@example.com",
            classification="valid_business",
            data_quality="High",
            score=85
        )
        with open(self.csv_path, newline="") as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames
        for col in ("email", "classification", "data_quality", "score", "timestamp"):
            self.assertIn(col, headers, f"Missing column: {col}")

    def test_csv_appends_not_overwrites(self):
        """Edge — Second call to log_result appends a row, not overwrites."""
        self.logger.log_result("a@company.com", "valid_business", "High", 90)
        self.logger.log_result("b@mailinator.com", "disposable_domain", "Low", 20)

        with open(self.csv_path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2)

    def test_log_result_records_correct_email(self):
        """Logged row contains the correct email address."""
        self.logger.log_result("user@gmail.com", "free_email", "Medium", 55)
        with open(self.csv_path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[0]["email"], "user@gmail.com")

    def test_log_result_records_correct_data_quality(self):
        """Logged row contains the correct data_quality value."""
        self.logger.log_result("info@corp.com", "role_account", "Low", 30)
        with open(self.csv_path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[0]["data_quality"], "Low")


# ---------------------------------------------------------------------------
# Exit with non-zero code when any tests fail (required by TDD-RED-CHECK)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (
        TestWorkflowJsonFile,
        TestN8NWorkflowImporter,
        TestEmailValidator,
        TestMauticDataQualityUpdate,
        TestValidationLogger,
    ):
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
