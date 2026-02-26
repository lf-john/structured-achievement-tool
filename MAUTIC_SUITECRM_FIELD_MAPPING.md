# Mautic-SuiteCRM Field Mapping and Synchronization Strategy

## Overview
This document outlines the configuration for synchronizing contact data between Mautic and SuiteCRM, focusing on optimizing performance for approximately 30,000 contacts. It includes details on sync frequency, batch sizing, initial full sync procedures, and deduplication strategies.

## Synchronization Settings

### Sync Frequency
- **Recommended Frequency:** Every 15 minutes for bulk updates.
- **Real-time Updates:** Utilize webhooks for immediate synchronization of individual contact changes (e.g., form submissions in Mautic). This ensures data consistency for ongoing interactions.

### Batch Size
For 30,000 contacts, an optimal batch size is crucial to balance performance and server load.
- **Recommended Batch Size:** 500 records per sync operation. This value can be adjusted based on server performance monitoring during initial syncs.
- **Configuration:** This setting is typically managed within the Mautic SuiteCRM plugin configuration or via environment variables for the Mautic console commands.

## Initial Full Synchronization Process
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

## Deduplication Strategy

### Mautic Side Deduplication
- **Unique Identifiers:** Mautic primarily uses email address as a unique identifier for contacts. Ensure all contacts have a valid and unique email address.
- **Merge/Delete:** Regularly review Mautic's duplicate contacts report and use the merge functionality to consolidate records.

### SuiteCRM Side Deduplication
- **Duplicate Detection Rules:** Configure SuiteCRM's duplicate detection rules based on email, name, or other relevant fields.
- **Manual Review/Merge:** Empower sales or marketing teams to manually review and merge duplicate records within SuiteCRM.

### Synchronization Conflict Resolution
- **Last Modified Wins:** By default, Mautic's SuiteCRM plugin often uses a "last modified wins" approach. The record most recently updated in either system will overwrite older data during sync.
- **Custom Logic (Advanced):** For more complex scenarios, consider custom Mautic plugins or SuiteCRM logic hooks to implement specific conflict resolution rules (e.g., always prefer data from SuiteCRM for certain fields).

## Field Mappings

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

## Custom Fields

If custom fields are used in either Mautic or SuiteCRM, they must be explicitly mapped in the Mautic SuiteCRM plugin settings.

1.  **Create Custom Fields:** Ensure the custom fields exist in both Mautic and SuiteCRM with compatible data types.
2.  **Map in Mautic:**
    *   Go to Mautic UI: `Settings` > `Plugins` > `SuiteCRM`.
    *   Navigate to the `Field Mapping` tab.
    *   Add new mappings for your custom fields, linking the Mautic custom field to the corresponding SuiteCRM custom field.

## Step-by-Step Configuration Guide (Mautic UI)

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