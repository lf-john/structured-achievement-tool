"""
IMPLEMENTATION PLAN for US-002:

Components:
  - aws_ses_dkim_documenter.py: A new module to document the DKIM setup process.
  - generate_dkim_setup_documentation(domain: str, region: str) -> str: Main function to generate the documentation.
  - _execute_aws_cli_command(domain: str, region: str) -> str: (Mocked in tests) Simulates AWS CLI command execution.
  - _parse_dkim_cname_records(cli_output: str) -> list[dict]: Parses CLI output for CNAME records.
  - _format_documentation(cli_output: str, parsed_records: list[dict]) -> str: Formats output into a human-readable document.

Test Cases:
  1. [AC 1] -> Verify generated documentation includes the AWS CLI command and setup process.
  2. [AC 2] -> Verify documentation describes the expected AWS CLI output format.
  3. [AC 3] -> Verify documentation provides CNAME extraction instructions and that parsing is correct.

Edge Cases:
  - Malformed AWS CLI output.
  - Empty or missing DKIM tokens in CLI output.
  - Error during AWS CLI command execution.
"""
import pytest
import sys
from unittest.mock import patch

# Importing the module that doesn't exist yet, to ensure tests fail
from src.utils.aws_ses_dkim_documenter import generate_dkim_setup_documentation, _parse_dkim_cname_records

class TestDkimDocumentation:

    MOCK_CLI_OUTPUT_SUCCESS = """
    {
        "DkimTokens": [
            "EXAMPLE1",
            "EXAMPLE2",
            "EXAMPLE3"
        ],
        "ResponseMetadata": {
            "RequestId": "some-request-id",
            "HTTPStatusCode": 200,
            "HTTPHeaders": {
                "x-amzn-requestid": "some-request-id",
                "content-type": "text/xml",
                "content-length": "472",
                "date": "Wed, 25 Feb 2026 12:00:00 GMT"
            },
            "RetryAttempts": 0
        }
    }
    """

    MOCK_CLI_OUTPUT_EMPTY_TOKENS = """
    {
        "DkimTokens": [],
        "ResponseMetadata": {
            "RequestId": "some-request-id",
            "HTTPStatusCode": 200,
            "HTTPHeaders": {
                "x-amzn-requestid": "some-request-id",
                "content-type": "text/xml",
                "content-length": "472",
                "date": "Wed, 25 Feb 2026 12:00:00 GMT"
            },
            "RetryAttempts": 0
        }
    }
    """

    MOCK_CLI_OUTPUT_MALFORMED_JSON = """
    {
        "DkimTokens": [
            "EXAMPLE1",
            "EXAMPLE2",
            "EXAMPLE3"
        ,
    """

    @patch('src.utils.aws_ses_dkim_documenter._execute_aws_cli_command', return_value=MOCK_CLI_OUTPUT_SUCCESS)
    def test_should_document_dkim_setup_process_and_cli_command_when_valid_input(self, mock_execute_command):
        """
        [AC 1] Verify generated documentation includes the AWS CLI command and setup process.
        """
        domain = "logicalfront.net"
        region = "us-east-1"
        documentation = generate_dkim_setup_documentation(domain, region)

        assert f"aws ses verify-domain-dkim --domain {domain} --region {region}" in documentation
        assert "Step-by-step DKIM setup process" in documentation
        assert "CNAME" in documentation # Check for mention of CNAME records

    @patch('src.utils.aws_ses_dkim_documenter._execute_aws_cli_command', return_value=MOCK_CLI_OUTPUT_SUCCESS)
    def test_should_describe_aws_cli_output_format_in_documentation(self, mock_execute_command):
        """
        [AC 2] Verify documentation describes the expected AWS CLI output format.
        """
        domain = "logicalfront.net"
        region = "us-east-1"
        documentation = generate_dkim_setup_documentation(domain, region)

        assert "Expected AWS CLI Output Format (JSON)" in documentation
        assert '"DkimTokens":' in documentation
        assert "List of strings representing DKIM tokens" in documentation

    @patch('src.utils.aws_ses_dkim_documenter._execute_aws_cli_command', return_value=MOCK_CLI_OUTPUT_SUCCESS)
    def test_should_provide_cname_extraction_instructions_and_parse_records_correctly(self, mock_execute_command):
        """
        [AC 3] Verify documentation provides CNAME extraction instructions and that parsing is correct.
        """
        domain = "logicalfront.net"
        region = "us-east-1"
        documentation = generate_dkim_setup_documentation(domain, region)

        assert "To extract the CNAME records" in documentation
        assert "Record Type: CNAME" in documentation
        assert "Host: EXAMPLE1._domainkey.logicalfront.net" in documentation
        assert "Value: EXAMPLE1.dkim.awsapps.com" in documentation

        # Test the parsing function directly (should be internal but accessible for testing)
        parsed_records = _parse_dkim_cname_records(self.MOCK_CLI_OUTPUT_SUCCESS, domain)
        assert len(parsed_records) == 3
        assert {"Host": "EXAMPLE1._domainkey.logicalfront.net", "Value": "EXAMPLE1.dkim.awsapps.com"} in parsed_records
        assert {"Host": "EXAMPLE2._domainkey.logicalfront.net", "Value": "EXAMPLE2.dkim.awsapps.com"} in parsed_records
        assert {"Host": "EXAMPLE3._domainkey.logicalfront.net", "Value": "EXAMPLE3.dkim.awsapps.com"} in parsed_records

    @patch('src.utils.aws_ses_dkim_documenter._execute_aws_cli_command', return_value=MOCK_CLI_OUTPUT_MALFORMED_JSON)
    def test_should_handle_malformed_cli_output_gracefully(self, mock_execute_command):
        """
        Edge Case: Malformed AWS CLI output.
        """
        domain = "logicalfront.net"
        region = "us-east-1"
        with pytest.raises(ValueError, match="Failed to parse AWS CLI output"):
            generate_dkim_setup_documentation(domain, region)

    @patch('src.utils.aws_ses_dkim_documenter._execute_aws_cli_command', return_value=MOCK_CLI_OUTPUT_EMPTY_TOKENS)
    def test_should_handle_empty_dkim_tokens_in_cli_output(self, mock_execute_command):
        """
        Edge Case: Empty or missing DKIM tokens in CLI output.
        """
        domain = "logicalfront.net"
        region = "us-east-1"
        documentation = generate_dkim_setup_documentation(domain, region)
        assert "No DKIM tokens found" in documentation
        assert "Host: EXAMPLE._domainkey.logicalfront.net" not in documentation

    @patch('src.utils.aws_ses_dkim_documenter._execute_aws_cli_command', side_effect=Exception("CLI Error"))
    def test_should_raise_error_on_cli_command_failure(self, mock_execute_command):
        """
        Edge Case: Error during AWS CLI command execution.
        """
        domain = "logicalfront.net"
        region = "us-east-1"
        with pytest.raises(Exception, match="CLI Error"):
            generate_dkim_setup_documentation(domain, region)

# Exit with a non-zero code if any test fails

