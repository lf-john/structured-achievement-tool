"""Mautic API module for saving generated emails as drafts."""


def call_mautic_api_to_save_draft(email_data, mautic_api_config):
    """
    Call Mautic API to save an email as a draft.

    This is a placeholder that will be mocked in tests.
    In production, this would call the actual Mautic API.

    Args:
        email_data: Dictionary with email_body and subject_lines
        mautic_api_config: Dictionary with Mautic API configuration (base_url, api_key)

    Returns:
        Response from Mautic API
    """
    pass


def save_email_as_draft(email_data, mautic_api_config):
    """
    Save a generated email to Mautic as a draft for review.

    Args:
        email_data: Dictionary with:
            - email_body: Email content
            - subject_lines: List of subject line variants
        mautic_api_config: Dictionary with:
            - base_url: Mautic instance URL
            - api_key: Mautic API key

    Returns:
        Response from Mautic API indicating success and draft ID

    Raises:
        Exception: If Mautic API call fails
    """
    return call_mautic_api_to_save_draft(
        email_data=email_data,
        mautic_api_config=mautic_api_config
    )
