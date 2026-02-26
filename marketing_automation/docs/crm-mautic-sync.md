# SuiteCRM-Mautic Synchronization Configuration Guide

This comprehensive guide outlines the process for configuring and managing the synchronization of contact data between Mautic and SuiteCRM. It covers initial setup, ongoing synchronization settings, data deduplication, conflict resolution, and related Mautic configurations for segments and lead scoring.

## 1. Mautic-SuiteCRM Field Mapping and Synchronization Strategy

### Overview
This section details the configuration for synchronizing contact data between Mautic and SuiteCRM, focusing on optimizing performance for approximately 30,000 contacts. It includes specifics on sync frequency, batch sizing, initial full sync procedures, and deduplication strategies.

### Synchronization Settings

#### Sync Frequency
- **Recommended Frequency:** Every 15 minutes for bulk updates.
- **Real-time Updates:** Utilize webhooks for immediate synchronization of individual contact changes (e.g., form submissions in Mautic). This ensures data consistency for ongoing interactions.

#### Batch Size
For 30,000 contacts, an optimal batch size is crucial to balance performance and server load.
- **Recommended Batch Size:** 500 records per sync operation. This value can be adjusted based on server performance monitoring during initial syncs.
- **Configuration:** This setting is typically managed within the Mautic SuiteCRM plugin configuration or via environment variables for the Mautic console commands.

### Initial Full Synchronization Process
1.  **Backup:** Before initiating any large-scale sync, perform a full backup of both Mautic and SuiteCRM databases.
2.  **Plugin Activation & Configuration:**
    *   Navigate to Mautic UI: `Settings` > `Plugins` > `SuiteCRM`.
    *   Enable the plugin and configure API credentials.
    *   Go to the `Feature` tab and enable `Contact Sync`.
3.  **Field Mapping:** Configure the field mappings as detailed in the "Field Mappings" section below.
4.  **Initial Sync Execution:**
    *   Access the Mautic server via command line.
    *   Execute the command: `php /var/www/mautic/bin/console mautic:integration:synccontacts --integration=SuiteCRM --full` (Note: `--full` flag might vary or not exist depending on Mautic version; consult Mautic documentation for exact command for full initial sync).
    *   Monitor server resources (CPU, RAM, database activity) during the initial sync.
5.  **Verification:** After the sync completes, spot-check a sample of contacts in both systems to ensure data integrity.

### Deduplication Strategy

#### Mautic Side Deduplication
- **Unique Identifiers:** Mautic primarily uses email address as a unique identifier for contacts. Ensure all contacts have a valid and unique email address.
- **Merge/Delete:** Regularly review Mautic's duplicate contacts report and use the merge functionality to consolidate records.

#### SuiteCRM Side Deduplication
- **Duplicate Detection Rules:** Configure SuiteCRM's duplicate detection rules based on email, name, or other relevant fields.
- **Manual Review/Merge:** Empower sales or marketing teams to manually review and merge duplicate records within SuiteCRM.

#### Synchronization Conflict Resolution
- **Last Modified Wins:** By default, Mautic's SuiteCRM plugin often uses a "last modified wins" approach. The record most recently updated in either system will overwrite older data during sync.
- **Custom Logic (Advanced):** For more complex scenarios, consider custom Mautic plugins or SuiteCRM logic hooks to implement specific conflict resolution rules (e.g., always prefer data from SuiteCRM for certain fields).

### Field Mappings

| Mautic Field      | SuiteCRM Field    | Notes                                    |
|-------------------|-------------------|------------------------------------------|
| Email             | email1            | Primary identifier                       |
| First Name        | first_name        |                                          |
| Last Name         | last_name         |                                          |
| Company           | account_name      | Mapped to primary account in SuiteCRM    |
| Phone             | phone_work        |                                          |
| City              | primary_address_city |                                          |
| State             | primary_address_state |                                          |
| Zip Code          | primary_address_postalcode |                                   |
| Country           | primary_address_country |                                   |
| Lead Source       | lead_source       | Custom field mapping may be required     |
| Marketing Segment | description       | Mapped to a text area in SuiteCRM, or a custom field |

### Custom Fields

If custom fields are used in either Mautic or SuiteCRM, they must be explicitly mapped in the Mautic SuiteCRM plugin settings.

1.  **Create Custom Fields:** Ensure the custom fields exist in both Mautic and SuiteCRM with compatible data types.
2.  **Map in Mautic:**
    *   Go to Mautic UI: `Settings` > `Plugins` > `SuiteCRM`.
    *   Navigate to the `Field Mapping` tab.
    *   Add new mappings for your custom fields, linking the Mautic custom field to the corresponding SuiteCRM custom field.

### Step-by-Step Configuration Guide (Mautic UI)

1.  **Access Plugins:** In Mautic, navigate to the left sidebar, click on the gear icon (Settings), and then select `Plugins`.
2.  **Locate SuiteCRM Plugin:** Find the "SuiteCRM" plugin in the list and click on it.
3.  **Enable Integration:**
    *   On the `Authorization` tab, ensure your SuiteCRM URL, username, and password (or API keys) are correctly entered and authorized.
    *   On the `Feature` tab, check the box next to `Sync Contacts to/from SuiteCRM`.
4.  **Configure Field Mappings:**
    *   Switch to the `Field Mapping` tab.
    *   Review the default mappings and adjust them according to the "Field Mappings" table above.
    *   To add a new mapping, click `Add new`. Select the Mautic field from the dropdown on the left and the SuiteCRM field from the dropdown on the right.
    *   Pay special attention to custom fields; ensure they are correctly mapped.
5.  **Save Configuration:** Click the `Save & Close` button at the top right to apply all changes.

## 2. General Mautic UI Settings Navigation

This section provides general guidance on how to access and modify settings within the Mautic user interface, which may be useful for other configurations not directly related to SuiteCRM sync.

1.  Log in to your Mautic admin dashboard.
2.  Navigate to **Settings** (cog icon in the top right).
3.  Click on **Configuration**.
4.  From here, you can select various tabs (e.g., Email Settings, System Settings) to adjust different aspects of your Mautic instance.
5.  Always remember to save your configuration changes.

## 3. Creating Mautic Contact Segments Manually

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

### Verifying Segment Membership Counts

After creating segments, it's crucial to verify their membership counts to ensure they are correctly capturing contacts.

#### Methods for Verification:

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

## 4. Configuring Mautic Lead Scoring Rules

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
