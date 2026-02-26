# scripts/mautic/field_definitions.py
# Defines the custom fields to be created in Mautic.
# This file is shared by creation, verification, and rollback scripts.

CUSTOM_FIELDS = {
    # alias: {definition}
    "industry": {
        "label": "Industry",
        "type": "select",
        "properties": {
            "list": [
                {"label": "Technology", "value": "technology"},
                {"label": "Healthcare", "value": "healthcare"},
                {"label": "Finance", "value": "finance"},
                {"label": "Manufacturing", "value": "manufacturing"},
                {"label": "Education", "value": "education"},
                {"label": "Other", "value": "other"},
            ]
        }
    },
    "company_size": {
        "label": "Company Size",
        "type": "select",
        "properties": {
            "list": [
                {"label": "1-10 employees", "value": "1-10"},
                {"label": "11-50 employees", "value": "11-50"},
                {"label": "51-200 employees", "value": "51-200"},
                {"label": "201-500 employees", "value": "201-500"},
                {"label": "501-1000 employees", "value": "501-1000"},
                {"label": "1001+ employees", "value": "1001+"},
            ]
        }
    },
    "lead_source": {
        "label": "Lead Source",
        "type": "select",
        "properties": {
            "list": [
                {"label": "Website", "value": "website"},
                {"label": "Referral", "value": "referral"},
                {"label": "Paid Ads", "value": "paid_ads"},
                {"label": "Social Media", "value": "social_media"},
                {"label": "Cold Outreach", "value": "cold_outreach"},
            ]
        }
    },
    "icp_fit": {
        "label": "ICP Fit",
        "type": "select",
        "properties": {
            "list": [
                {"label": "High", "value": "high"},
                {"label": "Medium", "value": "medium"},
                {"label": "Low", "value": "low"},
            ]
        }
    },
    "import_batch": {
        "label": "Import Batch",
        "type": "text",
    },
    "data_quality": {
        "label": "Data Quality",
        "type": "select",
        "properties": {
            "list": [
                {"label": "High", "value": "high"},
                {"label": "Medium", "value": "medium"},
                {"label": "Low", "value": "low"},
                {"label": "Unverified", "value": "unverified"},
            ]
        }
    }
}
