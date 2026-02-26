# SuiteCRM-Mautic Sync Configuration Guide

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
-   **Last Modified Wins:** In cases where a field is updated in both systems simultaneously, the value from the system where the field was most recently modified will take precedence. The `last_modified_date` or `date_modified` timestamps of the respective records are compared to determine the winning value.
-   **System Preference for Key Fields:** For certain critical fields (e.g., `email1` or unique identifiers), SuiteCRM is designated as the master system. Changes to these fields in Mautic will not overwrite the SuiteCRM value if a conflict is detected, unless explicitly overridden by an administrator.
-   **Logging and Alerts:** All detected conflicts and their resolutions are logged in the integration's activity log. Critical conflicts that cannot be automatically resolved are flagged, and an alert is sent to the system administrator for manual review and intervention.

## Field Mappings

The following fields are configured for mapping:

| SuiteCRM Field (Contacts/Leads) | Mautic Field (Contacts) | Mapping Direction | Notes |
|---------------------------------|-------------------------|-------------------|-------|
| `first_name`                    | `firstname`             | Bidirectional     |       |
| `last_name`                     | `lastname`              | Bidirectional     |       |
| `email1`                        | `email`                 | Bidirectional     |       |
| `phone_work`                    | `phone`                 | Bidirectional     |       |
| `title`                         | `position`              | Bidirectional     |       |
| `account_name`                  | `company`               | Bidirectional     |       |
| `primary_address_street`        | `address1`              | Bidirectional     |       |
| `primary_address_city`          | `city`                  | Bidirectional     |       |
| `primary_address_state`         | `state`                 | Bidirectional     |       |
| `primary_address_postalcode`    | `zipcode`               | Bidirectional     |       |
| `primary_address_country`       | `country`               | Bidirectional     |       |
| `lead_source`                   | `lead_source`           | SuiteCRM -> Mautic| Unidirectional |
| `status`                        | `segment`               | Bidirectional     | Mautic equivalent for lead/contact status |
| `description`                   | `notes`                 | Bidirectional     | Mautic equivalent for general description/notes |

## Custom Fields

To add new custom fields to the bidirectional mapping, follow these steps:

1.  **Create Custom Field in SuiteCRM:**
    *   Navigate to `Admin > Studio`.
    *   Select the `Contacts` and/or `Leads` module.
    *   Add a new custom field with the desired name and type.
    *   Deploy the changes.

2.  **Create Custom Field in Mautic:**
    *   Navigate to `Settings > Custom Fields`.
    *   Create a new custom field with a matching name (or a logical equivalent) and type.
    *   Ensure the field is marked as "Publicly Updatable" if it's intended for form submissions or API updates.

3.  **Update Mapping Configuration:**
    *   Identify the integration point or configuration file responsible for SuiteCRM-Mautic synchronization. (e.g., a custom integration script or a plugin configuration).
    *   Add a new entry to the mapping table, specifying:
        *   SuiteCRM field name (e.g., `suitecrm_custom_field__c`)
        *   Mautic field name (e.g., `mautic_custom_field`)
        *   Desired mapping direction (Bidirectional, SuiteCRM -> Mautic, or Mautic -> SuiteCRM).
    *   Restart or refresh the integration service to apply the new mapping.

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