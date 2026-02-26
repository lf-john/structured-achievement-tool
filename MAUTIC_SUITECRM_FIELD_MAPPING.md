# Mautic to SuiteCRM Field Mapping and Synchronization Strategy

## Overview
This document outlines the configuration for synchronizing contacts between Mautic and SuiteCRM, focusing on field mappings, handling of custom fields, and strategies for conflict resolution. The primary goal is to ensure data consistency and efficient lead management across both platforms for a dataset of approximately 30,000 contacts.

## Synchronization Schedule and Performance
- **Sync Frequency:** Every 15 minutes for bulk updates.
- **Real-time Updates:** Utilize webhooks for immediate synchronization of new contacts or significant contact updates from Mautic to SuiteCRM to ensure ongoing data freshness.
- **Batch Size:** Configured to handle 30,000 contacts efficiently. Initial full sync will process contacts in batches of 500-1000 to manage server load.
- **Initial Full Sync Process:**
    1.  **Backup:** Ensure a full backup of both Mautic and SuiteCRM databases before initiating the sync.
    2.  **Configuration:** Apply all field mappings and sync settings as detailed in this document within the Mautic SuiteCRM plugin.
    3.  **Disable Webhooks (Temporarily):** For the initial full sync, temporarily disable any real-time webhooks to prevent duplicate processing or race conditions.
    4.  **Execute Command:** Run the manual synchronization command from the Mautic CLI:
        `php /var/www/mautic/bin/console mautic:integration:synccontacts --integration=SuiteCRM`
    5.  **Monitor:** Closely monitor server resource usage (CPU, RAM, database I/O) on both Mautic and SuiteCRM instances during the sync.
    6.  **Verify:** After completion, spot-check a sample of contacts in both systems to ensure accurate data transfer.
    7.  **Re-enable Webhooks:** Once the initial sync is complete and verified, re-enable real-time webhooks.

## Field Mapping (Mautic to SuiteCRM)

| Mautic Field (Source) | SuiteCRM Field (Target) | Notes |
|-----------------------|-------------------------|-------|
| First Name            | first_name              |       |
| Last Name             | last_name               |       |
| Email                 | email1                  | Primary email |
| Mobile                | phone_mobile            |       |
| Phone                 | phone_work              |       |
| Company               | account_name            | Linked to Account module in SuiteCRM |
| Website               | website                 |       |
| Address Line 1        | primary_address_street  |       |
| City                  | primary_address_city    |       |
| State                 | primary_address_state   |       |
| Zip Code              | primary_address_postalcode |       |
| Country               | primary_address_country |       |
| Lead Source           | lead_source             | Mapped from Mautic segments or form submissions |
| Do Not Contact        | do_not_call             | Sync based on Mautic's "Do Not Contact" status |
| Unsubscribed          | email_opt_out           | Sync based on Mautic's email unsubscribe status |
| Last Activity Date    | date_modified           | Updates on Mautic contact activity |

## Custom Fields
For any custom fields created in Mautic that need to be synced to SuiteCRM:
1.  **Create in SuiteCRM:** Ensure a corresponding custom field with the same data type exists in SuiteCRM (e.g., using Studio).
2.  **Map in Mautic Plugin:** Add these custom fields to the field mapping section within the Mautic SuiteCRM integration settings.
3.  **Naming Convention:** Maintain consistent naming conventions where possible (e.g., `mautic_custom_field_name` in SuiteCRM).

## Deduplication Strategy
A robust deduplication strategy is critical to maintain data integrity.
-   **Primary Identifier:** Email address will serve as the primary unique identifier for contacts across both systems.
-   **Mautic Deduplication:** Mautic's built-in deduplication (based on email) will be relied upon for inbound contacts.
-   **SuiteCRM Deduplication:**
    -   **On Sync:** When a contact is pushed from Mautic to SuiteCRM, the integration should first attempt to find an existing contact in SuiteCRM by email address.
    -   **Update vs. Create:** If a match is found, the existing SuiteCRM contact should be updated with Mautic's data. If no match, a new contact should be created.
    -   **Manual Review:** Implement a process for manual review of potential duplicates identified by SuiteCRM's internal duplicate detection (if enabled) that are not caught by the email-based primary identifier.
-   **Conflict Resolution:**
    -   **Last Update Wins:** In cases where a field is modified in both Mautic and SuiteCRM between sync cycles, the value from the system that had the most recent update will prevail.
    -   **Mautic as Master (for certain fields):** For marketing-specific fields (e.g., Lead Score, Segment Membership), Mautic will be considered the master. Changes in Mautic for these fields will always overwrite SuiteCRM.
    -   **SuiteCRM as Master (for certain fields):** For sales-specific fields (e.g., Sales Stage, Owner), SuiteCRM will be considered the master.
    -   **Logging:** Ensure that the integration logs all conflict resolutions for auditing and troubleshooting purposes.
