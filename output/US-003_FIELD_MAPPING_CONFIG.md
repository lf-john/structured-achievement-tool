# US-003: Bidirectional Field Mapping Configuration

This document outlines the configuration for bidirectional field mapping between SuiteCRM Contacts/Leads and Mautic Contacts, including handling custom fields and conflict resolution strategies.

## 1. Configured Field Mappings

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

## 2. Custom Field Mapping Configuration

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

## 3. Conflict Resolution Strategy

Conflicts can occur when a record is updated in both SuiteCRM and Mautic independently before synchronization. The following strategy is implemented:

*   **Last Modified Wins:** In cases where a field is updated in both systems simultaneously, the value from the system where the field was most recently modified will take precedence. The `last_modified_date` or `date_modified` timestamps of the respective records are compared to determine the winning value.
*   **System Preference for Key Fields:** For certain critical fields (e.g., `email1` or unique identifiers), SuiteCRM is designated as the master system. Changes to these fields in Mautic will not overwrite the SuiteCRM value if a conflict is detected, unless explicitly overridden by an administrator.
*   **Logging and Alerts:** All detected conflicts and their resolutions are logged in the integration's activity log. Critical conflicts that cannot be automatically resolved are flagged, and an alert is sent to the system administrator for manual review and intervention.
