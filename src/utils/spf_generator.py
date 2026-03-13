"""
SPF Record Generator for Amazon SES integration.

This module provides functions to generate, merge, and document SPF records
for domains using Amazon SES.
"""


def generate_spf_record(domain: str, includes: list[str]) -> str:
    """
    Constructs a base SPF record string.

    Args:
        domain: Domain name
        includes: List of include statements to add to the record

    Returns:
        SPF record string in the format: "v=spf1 <includes> ~all"
    """
    includes_str = " ".join(includes)
    return f"v=spf1 {includes_str} ~all"


def merge_spf_records(existing_record: str, new_include: str) -> str:
    """
    Merges a new 'include' mechanism into an existing SPF record.

    Args:
        existing_record: The current SPF record string
        new_include: The include statement to add (e.g., "include:amazonses.com")

    Returns:
        Updated SPF record with the new include, without duplicates
    """
    # Parse the existing record
    parts = existing_record.split()

    # Separate v=spf1, includes, mechanisms, and all_mechanism
    includes = []
    mechanisms = []
    all_mechanism = None

    for part in parts:
        if part == "v=spf1":
            pass
        elif part.endswith("all"):
            all_mechanism = part
        elif part.startswith("include:"):
            includes.append(part)
        else:
            mechanisms.append(part)

    # Check if new_include is already present
    has_new_include = new_include in includes

    # Add the new include if not already present (insert after existing includes)
    if not has_new_include:
        includes.append(new_include)

    # Build the new record
    new_parts = ["v=spf1"] + includes + mechanisms

    # Add the all mechanism if not present
    if not all_mechanism:
        new_parts.append("~all")
    else:
        new_parts.append(all_mechanism)

    return " ".join(new_parts)


def document_spf_guidance(domain: str, new_include: str, existing_record: str | None) -> str:
    """
    Generates a comprehensive documentation string including the record type,
    host, full SPF value, and detailed guidance on merging with an existing record.

    Args:
        domain: Domain name
        new_include: The include statement to add (e.g., "include:amazonses.com")
        existing_record: Optional existing SPF record string

    Returns:
        Comprehensive SPF record documentation

    Raises:
        ValueError: If domain is empty
    """
    # Validate domain
    if not domain or not domain.strip():
        raise ValueError("Domain cannot be empty")

    # Generate the final SPF record
    if existing_record:
        final_spf = merge_spf_records(existing_record, new_include)
        guidance = f"""Existing SPF record detected for {domain}.
To correctly merge your Amazon SES SPF record, follow these steps:

1. Find your existing SPF TXT record for {domain} (or `@`)
2. The DNS record must contain ONLY ONE SPF record
3. Your updated SPF record should include the following structure:
   Record Type: TXT
   Host: {domain}
   Full Value: {final_spf}

4. The SPF record can have only one 'v=spf1' identifier and only one mechanism ending in 'all' (such as ~all, -all, or ?all).
5. To add the Amazon SES include to your existing record, simply add `include:amazonses.com` to your existing SPF record.
6. If your existing record doesn't have an 'all' mechanism, add `~all` to the end.
7. If your existing record already includes `include:amazonses.com`, you don't need to add it again.
8. The updated SPF record will allow email from Amazon SES and your existing mail sources.
9. IMPORTANT: You can have only one SPF record per domain - do not create multiple SPF records.

The merged SPF record is:
{final_spf}"""
    else:
        final_spf = generate_spf_record(domain, [new_include])
        guidance = f"""SPF record generated for {domain}:

Record Type: TXT
Host: {domain}
Full Value: {final_spf}

No existing SPF record found. To use this SPF record:
1. Create a TXT record with the name `{domain}` (or `@`)
2. Set the record value to: "{final_spf}"
3. The record should automatically be active within a few minutes to an hour.

Note: The ~all mechanism in the SPF record means "soft fail" - mail will be accepted but marked as potentially suspicious.
"""

    return guidance
