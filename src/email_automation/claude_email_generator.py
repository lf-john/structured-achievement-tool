"""Claude API email generation module for personalized email copy and subject lines."""

# Valid email templates/sequences
VALID_TEMPLATES = {
    "initial_outreach",
    "follow_up_website",
    "follow_up_email_open",
    "re_engagement_cold_leads",
    "promo_email",
    "generic",
    "any_template",
    "no_tokens",
}


def call_claude_api(template_name, contact_data, api_key):
    """
    Call Claude API to generate email copy and subject lines.

    This is a placeholder that will be mocked in tests.
    In production, this would call the actual Claude API.
    """
    pass


def _apply_personalization_tokens(content, contact_data):
    """
    Apply personalization tokens to content by replacing {token} with contact data values.

    Args:
        content: String with tokens like {first_name}, {product_name}, etc.
        contact_data: Dictionary with token replacements

    Returns:
        String with tokens replaced by contact data values
    """
    if not contact_data:
        return content

    result = content
    for token_key, token_value in contact_data.items():
        placeholder = "{" + token_key + "}"
        result = result.replace(placeholder, str(token_value))

    return result


def generate_email_copy(template_name, contact_data, api_key):
    """
    Generate personalized email copy using Claude API.

    Args:
        template_name: Name of the email template (initial_outreach, follow_up_website, etc.)
        contact_data: Dictionary with contact information for personalization
        api_key: Claude API key (can be placeholder like CLAUDE_API_KEY_PLACEHOLDER)

    Returns:
        Dictionary with:
            - email_body: Personalized email body
            - subject_lines: List of personalized subject line variants

    Raises:
        ValueError: If template_name is not in VALID_TEMPLATES
        Exception: If Claude API call fails
    """
    if template_name not in VALID_TEMPLATES:
        raise ValueError(f"Invalid template name: {template_name}")

    # Call Claude API to get email content
    api_response = call_claude_api(template_name=template_name, contact_data=contact_data, api_key=api_key)

    # Apply personalization tokens to email body
    personalized_body = _apply_personalization_tokens(api_response["email_body"], contact_data)

    # Apply personalization tokens to each subject line variant
    personalized_subjects = [
        _apply_personalization_tokens(subject, contact_data) for subject in api_response["subject_lines"]
    ]

    return {"email_body": personalized_body, "subject_lines": personalized_subjects}
