#!/usr/bin/env bash
# US-012 Verification Script: n8n-enrichment-pipeline.md documentation

set -euo pipefail

DOC_PATH="$HOME/projects/marketing-automation/docs/n8n-enrichment-pipeline.md"
FAIL=0

check() {
    local label="$1"
    local condition="$2"
    if eval "$condition"; then
        echo "PASS: $label"
    else
        echo "FAIL: $label"
        FAIL=1
    fi
}

# AC-9: File exists at correct path
check "Documentation file created at correct path" "[ -f '$DOC_PATH' ]"

if [ ! -f "$DOC_PATH" ]; then
    echo "Cannot proceed with content checks — file missing"
    exit 1
fi

# AC-1: Workflow overview section mentions Lead Coordinator integration
check "Workflow overview section present" "grep -qi 'overview' '$DOC_PATH'"
check "Lead Coordinator integration mentioned" "grep -qi 'lead coordinator' '$DOC_PATH'"

# AC-2: Architecture diagram or data flow diagram
check "Architecture or data flow diagram section present" "grep -qi 'architecture\|diagram\|data flow' '$DOC_PATH'"

# AC-3: API credential sections for all four services
check "Apollo.io credentials section present" "grep -qi 'apollo' '$DOC_PATH'"
check "IPinfo credentials section present" "grep -qi 'ipinfo' '$DOC_PATH'"
check "Apify credentials section present" "grep -qi 'apify' '$DOC_PATH'"
check "Mautic credentials section present" "grep -qi 'mautic' '$DOC_PATH'"

# AC-4: N8N credential configuration step-by-step instructions
check "N8N credential configuration instructions present" "grep -qi 'n8n' '$DOC_PATH'"
check "Step-by-step configuration instructions present" "grep -qi 'step\|configure\|setup' '$DOC_PATH'"

# AC-5: Import and testing procedures with example test contact data
check "Import procedure documented" "grep -qi 'import' '$DOC_PATH'"
check "Testing procedure documented" "grep -qi 'test' '$DOC_PATH'"
check "Example test contact data present" "grep -qi 'example\|sample\|test contact\|test data' '$DOC_PATH'"

# AC-6: Rate limits documented
check "Apollo rate limit (100 req/min) documented" "grep -qi '100.*req\|100.*min\|req.*min.*100\|apollo.*rate\|rate.*apollo' '$DOC_PATH'"
check "IPinfo free tier (50K/month) documented" "grep -qi '50,000\|50000\|50k\|50 k' '$DOC_PATH'"
check "Apify async limits documented" "grep -qi 'async\|apify.*limit\|limit.*apify' '$DOC_PATH'"

# AC-7: Enrichment field mapping table
check "Field mapping table present" "grep -qi 'field mapping\|input.*output\|mapping table' '$DOC_PATH'"

# AC-8: Cost estimation
check "Cost estimation section present" "grep -qi 'cost\|pricing' '$DOC_PATH'"
check "Per-contact cost mentioned" "grep -qi 'per.contact\|per contact\|contact cost' '$DOC_PATH'"
check "Monthly volume calculations present" "grep -qi 'monthly\|per month\|month' '$DOC_PATH'"

# AC-10: Troubleshooting section
check "Troubleshooting section present" "grep -qi 'troubleshoot\|trouble' '$DOC_PATH'"
check "Common issues/errors documented" "grep -qi 'common issue\|error scenario\|error.*scenario\|401\|403\|timeout\|rate limit error' '$DOC_PATH'"

# Document must be substantial (at least 150 lines)
LINE_COUNT=$(wc -l < "$DOC_PATH")
if [ "$LINE_COUNT" -ge 150 ]; then
    echo "PASS: Documentation is substantial ($LINE_COUNT lines)"
else
    echo "FAIL: Documentation too short ($LINE_COUNT lines, expected >= 150)"
    FAIL=1
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "All verification checks passed."
    exit 0
else
    echo "One or more verification checks failed."
    exit 1
fi
