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

After creating segments, it\'s crucial to verify their membership counts to ensure they are correctly capturing contacts.

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

### Programmatic Segment Creation:

For automated segment creation, refer to the `create_mautic_segments.py` script. This script outlines how to programmatically define and potentially create these segments using a Mautic API client.

## Configuring Mautic Lead Scoring Rules

This section describes how to set up lead scoring rules in Mautic to assign points based on demographic and behavioral criteria.

### Steps to Create a Point Trigger or Action:

1.  **Log in** to your Mautic instance.
2.  Navigate to **Points** (usually found in the left-hand navigation menu).
3.  Choose either **Triggers** or **Actions** depending on the type of rule you are creating.
4.  Click the **+ New** button.
5.  Enter a **Name** and **Description** for the rule.
6.  Configure the **Events** and **Actions** based on the specific demographic or behavioral criteria outlined below.
7.  Once configured, click **Save & Close**.

### Demographic Scoring Rules (Points > Triggers):

Create triggers to assign points based on contact demographic data.

*   **Rule:** Title criteria
    *   **Criteria:** `Contact Field` | `Title` | `contains` | `[Specific Job Titles, e.g., 'CEO', 'Director']`
    *   **Points:** +20
*   **Rule:** Industry criteria
    *   **Criteria:** `Contact Field` | `Industry` | `contains` | `[Target Industries, e.g., 'Healthcare', 'Technology']`
    *   **Points:** +15
*   **Rule:** Company size criteria
    *   **Criteria:** `Contact Field` | `Company Size` | `greater than or equal` | `[Specific Size, e.g., '50']`
    *   **Points:** +10
*   **Rule:** Phone number presence
    *   **Criteria:** `Contact Field` | `Phone` | `is not empty`
    *   **Points:** +5
*   **Rule:** LinkedIn URL presence
    *   **Criteria:** `Contact Field` | `LinkedIn URL` | `is not empty`
    *   **Points:** +5

### Behavioral Scoring Rules (Points > Triggers):

Create triggers to assign points based on contact engagement and behavior.

*   **Rule:** Email opened
    *   **Criteria:** `Email opened` | `[Select Specific Email or All Emails]`
    *   **Points:** +5
*   **Rule:** Email link clicked
    *   **Criteria:** `Clicks email link` | `[Select Specific Email or All Emails]` | `[Select Specific Link or Any Link]`
    *   **Points:** +10
*   **Rule:** Website page visited
    *   **Criteria:** `Visits a page` | `[Select Specific Page or All Pages]`
    *   **Points:** +3
*   **Rule:** Form submitted
    *   **Criteria:** `Submits a form` | `[Select Specific Form or Any Form]`
    *   **Points:** +25