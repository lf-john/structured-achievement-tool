import json

CLI_OUTPUT_EXAMPLE_JSON = """
```json
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
```
"""


def _execute_aws_cli_command(domain: str, region: str) -> str:
    """
    Executes the AWS CLI command to verify a domain's DKIM settings.
    This function is intended to be mocked in tests.
    In a real scenario, it would use the run_shell_command tool.
    """
    # Placeholder for actual CLI execution. In a real scenario, this would use default_api.run_shell_command
    # For now, it will raise an error if not mocked, as per test expectation.
    raise NotImplementedError(
        "This function should be mocked for testing or use run_shell_command in a real execution."
    )


def _parse_dkim_cname_records(cli_output: str, domain: str) -> list[dict]:
    """
    Parses the AWS CLI output to extract DKIM CNAME records.
    """
    try:
        data = json.loads(cli_output)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse AWS CLI output: {e}")

    dkim_tokens = data.get("DkimTokens", [])
    if not dkim_tokens:
        return []

    cname_records = []
    for token in dkim_tokens:
        cname_records.append({"Host": f"{token}._domainkey.{domain}", "Value": f"{token}.dkim.awsapps.com"})
    return cname_records


def _format_documentation(cli_output: str, parsed_records: list[dict], domain: str, region: str) -> str:
    """
    Formats the DKIM setup process documentation.
    """
    documentation = f"""# Amazon SES DKIM Setup Process

## Step-by-step DKIM setup process for {domain} in {region}

This document outlines the process to set up DomainKeys Identified Mail (DKIM) for your domain using Amazon Simple Email Service (SES) via the AWS Command Line Interface (CLI).

### 1. Initiate Domain Verification and Retrieve CNAME Records

To begin, you will use the `aws ses verify-domain-dkim` command. This command will return a set of DKIM tokens that you will use to create CNAME records in your domain's DNS configuration.

**AWS CLI Command:**
```bash
aws ses verify-domain-dkim --domain {domain} --region {region}
```

### 2. Expected AWS CLI Output Format (JSON)

{CLI_OUTPUT_EXAMPLE_JSON.strip()}

*   **`DkimTokens`**: List of strings representing DKIM tokens. This is a critical list of strings representing the unique DKIM tokens for your domain. You will use these tokens to construct your CNAME records.
*   **`ResponseMetadata`**: Contains standard AWS response metadata, including the HTTP status code and request ID.

### 3. Extracting CNAME Records for DNS Configuration

To extract the CNAME records from the AWS CLI output, identify the `DkimTokens` array.
From the `DkimTokens` array in the AWS CLI output, you will derive three CNAME records. Each token corresponds to one CNAME record.

Here's how to construct each record:

Record Type: CNAME

{"_records_placeholder_"}

These records need to be added to your domain's DNS settings. It may take some time for the changes to propagate.

### Important Notes:
*   Ensure you replace `EXAMPLE` with the actual tokens provided in the AWS CLI output.
*   The `_domainkey` subdomain is standard for DKIM records.
*   The `dkim.awsapps.com` is a common endpoint for AWS SES DKIM validation.
"""

    if parsed_records:
        records_str = ""
        for i, record in enumerate(parsed_records):
            records_str += f"""
**Record {i + 1}:**
    Host: {record["Host"]}
    Value: {record["Value"]}
"""
        documentation = documentation.replace("_records_placeholder_", records_str)
    else:
        documentation = documentation.replace(
            "_records_placeholder_",
            "\n**No DKIM tokens found in the AWS CLI output. Please verify your domain and region, and ensure the `aws ses verify-domain-dkim` command returns valid tokens.**\n",
        )

    return documentation


def generate_dkim_setup_documentation(domain: str, region: str) -> str:
    """
    Generates the complete DKIM setup documentation for Amazon SES.
    """
    try:
        cli_output = _execute_aws_cli_command(domain, region)
        parsed_records = _parse_dkim_cname_records(cli_output, domain)
        documentation = _format_documentation(cli_output, parsed_records, domain, region)
        return documentation
    except ValueError as e:
        raise e
    except Exception as e:
        raise Exception(f"Error during AWS CLI command execution or documentation generation: {e}")
