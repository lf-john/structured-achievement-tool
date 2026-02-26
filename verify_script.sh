#!/bin/bash

# verify_script.sh

set -e

FILE="n8n_claude_email_workflow.json"

if [ ! -f "$FILE" ]; then
    echo "Error: $FILE not found."
    exit 1
fi

# Check for valid JSON
if ! jq -e . "$FILE" > /dev/null; then
    echo "Error: $FILE is not valid JSON."
    exit 1
fi

# Check for key components
WEBHOOK_NODE=$(jq '.nodes[] | select(.type == "n8n-nodes-base.webhook")' "$FILE")
CLAUDE_NODE=$(jq '.nodes[] | select(.name == "Call Claude API")' "$FILE")
MAUTIC_NODE=$(jq '.nodes[] | select(.type == "n8n-nodes-base.mautic")' "$FILE")

if [ -z "$WEBHOOK_NODE" ]; then
    echo "Error: Webhook trigger node not found."
    exit 1
fi

if [ -z "$CLAUDE_NODE" ]; then
    echo "Error: 'Call Claude API' node not found."
    exit 1
fi

# Check for placeholder for Claude API key
CLAUDE_CREDENTIALS=$(echo "$CLAUDE_NODE" | jq -r '.parameters.authentication' )
if [[ "$CLAUDE_CREDENTIALS" != "headerAuth" ]]; then
    echo "Error: Claude API node is not using header authentication for the API key."
    exit 1
fi

API_KEY_VALUE=$(echo "$CLAUDE_NODE" | jq -r '.parameters.headerParameters.parameters[] | select(.name == "x-api-key") | .value')
if [[ "$API_KEY_VALUE" != "{{$credentials.claudeApiKey.apiKey}}" ]]; then
    echo "Error: Claude API key placeholder '{{$credentials.claudeApiKey.apiKey}}' not found."
    exit 1
fi


if [ -z "$MAUTIC_NODE" ]; then
    echo "Error: Mautic node not found."
    exit 1
fi

echo "Verification successful: $FILE is a valid N8N workflow with all required components."
exit 0
