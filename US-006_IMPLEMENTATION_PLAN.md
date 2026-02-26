# US-006: N8N Claude Email Generation Workflow Implementation Plan

This document provides the steps to import, configure, and activate the new email generation workflow in your N8N instance.

## Prerequisites

1.  An active N8N instance.
2.  Admin access to the N8N instance.
3.  Mautic credentials configured in N8N.
4.  A Claude API key from Anthropic.

## Implementation Steps

### 1. Import the Workflow

1.  Open your N8N dashboard.
2.  Navigate to the **Workflows** section.
3.  Click on the **"New"** button to create a new workflow.
4.  In the new workflow canvas, click on the options menu (three dots) in the top right and select **"Import from file"**.
5.  Select the `n8n_claude_email_workflow.json` file from this project.
6.  The "Claude Email Generation" workflow will be loaded onto the canvas.

### 2. Configure Credentials

The workflow requires a Claude API key to function.

1.  In the N8N sidebar, go to **Credentials**.
2.  Click **"Add credential"**.
3.  Search for **"Header Auth"** and select it.
4.  Fill in the credential details:
    *   **Credential Name:** `Claude API Key`
    *   **Name:** `x-api-key`
    *   **Value:** Paste your Claude API key here.
5.  Click **"Save"**.
6.  Go back to the imported workflow. Double-click the **"Call Claude API"** node.
7.  In the **"Authentication"** dropdown, ensure **"Header Auth"** is selected.
8.  For the **"Credentials"** field, select the `Claude API Key` credential you just created. The value should be `{{$credentials.Claude API Key.apiKey}}`.

### 3. Configure Mautic Node

1.  Double-click the **"Save to Mautic as Draft"** node.
2.  Ensure the correct Mautic API credentials are selected in the **"Credentials"** section.
3.  Review the parameters and adjust if necessary for your Mautic instance.

### 4. Activate the Workflow

1.  Once all nodes are configured correctly and show no errors, save the workflow.
2.  Toggle the **"Active"** switch in the top left of the workflow editor to activate it.

## 5. Using the Workflow

The workflow is triggered by a POST request to its webhook URL.

1.  Find the webhook URL by clicking on the **"Webhook Trigger"** node and navigating to the **"Webhook URLs"** tab.
2.  Send a POST request to this URL with a JSON body containing the contact information.

**Example `curl` command:**

```bash
curl -X POST 
-H "Content-Type: application/json" 
-d '{
  "tag": "initial_outreach",
  "firstName": "John",
  "company": "ACME Corp",
  "topic": "your recent inquiry about our products",
  "context": "John visited our pricing page twice this week."
}' 
YOUR_N8N_WEBHOOK_URL
```

This will trigger the workflow, generate an email using the Claude API, and save it as a draft in your Mautic instance.
