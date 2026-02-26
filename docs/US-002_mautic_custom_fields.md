# Mautic Custom Field Configuration (US-002)

This document outlines the configuration for custom contact fields created in Mautic as part of user story US-002.

## Method

The fields were created programmatically using the Mautic API. The script `scripts/mautic/create_fields.py` was used to ensure a repeatable and documented process. This method is preferred over manual UI configuration for consistency across environments.

## Field Configurations

The following fields were created for the `contact` object:

| Label | Alias (API Name) | Type | Properties |
|---|---|---|---|
| Industry | `industry` | `select` | Technology, Healthcare, Finance, Manufacturing, Education, Other |
| Company Size | `company_size` | `select` | 1-10, 11-50, 51-200, 201-500, 501-1000, 1001+ |
| Lead Source | `lead_source` | `select` | Website, Referral, Paid Ads, Social Media, Cold Outreach |
| ICP Fit | `icp_fit` | `select` | High, Medium, Low |
| Import Batch | `import_batch` | `text` | N/A |
| Data Quality | `data_quality` | `select` | High, Medium, Low, Unverified |

---
*This document is auto-generated/updated as part of the execution plan.*
