# Lead Import Guide

## Creating Mautic Contact Segments Manually

This guide outlines the steps to manually create the required contact segments in Mautic based on various criteria.

### Steps to Create a Segment:

1.  **Log in** to your Mautic instance.
2.  Navigate to the **Segments** section (usually found in the left-hand navigation menu).
3.  Click the **+ New** button to create a new segment.
4.  Enter the **Name** and a **Description** for the segment.
5.  In the **Filters** section, use the **Segment Builder** to add conditions based on the criteria below.
6.  Once all filters are added, click **Save & Close**.

### Segment Definitions and Criteria:

Use the following definitions to create your segments:

#### Industry Segments:

*   **Name:** `industry-healthcare`
    *   **Filter:** `Industry` | `equals` | `Healthcare`
*   **Name:** `industry-higher-ed`
    *   **Filter:** `Industry` | `equals` | `Higher Education`
*   **Name:** `industry-manufacturing`
    *   **Filter:** `Industry` | `equals` | `Manufacturing`

#### Geography Segments:

*   **Name:** `geo-california`
    *   **Filter:** `State` | `equals` | `CA`
*   **Name:** `geo-texas`
    *   **Filter:** `State` | `equals` | `TX`
*   **Name:** `geo-new-york`
    *   **Filter:** `State` | `equals` | `NY`

#### Company Size Segments:

*   **Name:** `size-smb`
    *   **Filter:** `CompanySize` | `less than or equal` | `50`
*   **Name:** `size-mid-market`
    *   **Filter 1:** `CompanySize` | `greater than` | `50`
    *   **Filter 2 (AND):** `CompanySize` | `less than or equal` | `500`
*   **Name:** `size-enterprise`
    *   **Filter:** `CompanySize` | `greater than` | `500`

#### Engagement Segments:

*   **Name:** `engaged-openers`
    *   **Filter:** `EmailOpens` | `greater than` | `0`
*   **Name:** `engaged-clickers`
    *   **Filter:** `EmailClicks` | `greater than` | `0`
*   **Name:** `cold-no-engagement`
    *   **Filter 1:** `EmailOpens` | `equals` | `0`
    *   **Filter 2 (AND):** `EmailClicks` | `equals` | `0`

#### Lead Quality Segments:

*   **Name:** `icp-strong-fit`
    *   **Filter:** `ICPScore` | `greater than or equal` | `80`
*   **Name:** `icp-moderate-fit`
    *   **Filter 1:** `ICPScore` | `greater than or equal` | `50`
    *   **Filter 2 (AND):** `ICPScore` | `less than` | `80`
*   **Name:** `warmup-safe`
    *   **Filter:** `EmailBounceRate` | `less than` | `0.05`

## Verifying Segment Membership Counts

After creating segments, it's crucial to verify their membership counts to ensure they are correctly capturing contacts.

### Methods for Verification:

1.  **Mautic UI Inspection:**
    *   Navigate to the **Segments** section in Mautic.
    *   Locate the segment you wish to verify.
    *   The segment list will typically show the number of contacts in each segment. Click on the segment name to view the contacts.
    *   Manually inspect a few contacts within the segment to confirm they meet the defined filter criteria.

2.  **Programmatic Verification (via Mautic API):**
    *   Utilize the Mautic API to fetch segment membership counts. The `MauticApiClient` in `src/mautic/mautic_api_client.py` contains a placeholder method `get_segment_membership_count(segment_id: int)` which, if fully implemented, would allow programmatic retrieval of these counts.
    *   This method would typically make a GET request to an endpoint like `/api/segments/{segment_id}/contacts/count` (Mautic API endpoints may vary, consult Mautic API documentation for exact paths).
    *   Compare the retrieved counts with expected numbers based on your contact data.
