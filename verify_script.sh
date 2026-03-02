#!/bin/bash
# verify_script.sh — US-009: Test workflow in N8N environment
# Verifies: workflow imported, Mautic credentials configured, test batch processed,
#           validation-log.csv created, data_quality values correctly assigned.

N8N_URL="http://localhost:8090"
MAUTIC_URL="http://localhost:8080"
WORKFLOW_NAME="Email Validation Pipeline"
VALIDATION_LOG="${HOME}/projects/marketing-automation/data/validation-log.csv"
PASS=0
FAIL=0

# Read N8N API key from environment or well-known path
N8N_API_KEY="${N8N_API_KEY:-}"
if [ -z "$N8N_API_KEY" ] && [ -f "${HOME}/projects/marketing-automation/.n8n_api_key" ]; then
    N8N_API_KEY=$(cat "${HOME}/projects/marketing-automation/.n8n_api_key")
fi

check() {
    local desc="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo "PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "FAIL: $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== US-009 Verification: N8N Email Validation Workflow ==="
echo ""

# AC: N8N is reachable
http_code=$(curl -s -o /dev/null -w "%{http_code}" "${N8N_URL}" 2>/dev/null || echo "000")
check "N8N accessible at ${N8N_URL}" "$([ "$http_code" != "000" ] && echo 0 || echo 1)"

# AC: Workflow successfully imported (requires N8N API key)
if [ -n "$N8N_API_KEY" ]; then
    workflow_response=$(curl -s -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        "${N8N_URL}/api/v1/workflows" 2>/dev/null)
    workflow_exists=$(echo "$workflow_response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    workflows = data.get('data', [])
    found = any('Email Validation Pipeline' in w.get('name','') for w in workflows)
    print('0' if found else '1')
except:
    print('1')
" 2>/dev/null || echo "1")
    check "Workflow 'Email Validation Pipeline' imported into N8N" "$workflow_exists"

    # AC: Mautic credentials configured in N8N
    cred_response=$(curl -s -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        "${N8N_URL}/api/v1/credentials" 2>/dev/null)
    cred_exists=$(echo "$cred_response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    creds = data.get('data', [])
    found = any('mautic' in c.get('name','').lower() for c in creds)
    print('0' if found else '1')
except:
    print('1')
" 2>/dev/null || echo "1")
    check "Mautic API credentials configured in N8N" "$cred_exists"

    # AC: All 8 nodes present in workflow
    node_count=$(echo "$workflow_response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for w in data.get('data', []):
        if 'Email Validation Pipeline' in w.get('name',''):
            print(len(w.get('nodes', [])))
            sys.exit(0)
    print(0)
except:
    print(0)
" 2>/dev/null || echo "0")
    check "Workflow has 8 nodes (found: ${node_count})" "$([ "${node_count:-0}" -ge 8 ] && echo 0 || echo 1)"
else
    echo "WARN: N8N_API_KEY not set — skipping N8N API workflow/credential checks"
    echo "      Set via: export N8N_API_KEY=<key>  or  echo <key> > ~/projects/marketing-automation/.n8n_api_key"
fi

# AC: validation-log.csv created with test results
check "validation-log.csv exists at expected path" "$([ -f "${VALIDATION_LOG}" ] && echo 0 || echo 1)"

if [ -f "${VALIDATION_LOG}" ]; then
    # AC: Test batch processed (at least 10 rows)
    row_count=$(tail -n +2 "${VALIDATION_LOG}" | grep -c '.' 2>/dev/null || echo "0")
    check "validation-log.csv has 10+ email records (found: ${row_count})" \
        "$([ "${row_count:-0}" -ge 10 ] && echo 0 || echo 1)"

    # AC: CSV has required columns
    header=$(head -1 "${VALIDATION_LOG}")
    check "CSV has 'email' column" "$(echo "$header" | grep -q 'email' && echo 0 || echo 1)"
    check "CSV has 'data_quality' column" "$(echo "$header" | grep -q 'data_quality' && echo 0 || echo 1)"
    check "CSV has 'syntax_valid' column" "$(echo "$header" | grep -q 'syntax_valid' && echo 0 || echo 1)"

    # AC: Sample emails scored correctly — all three quality categories present
    content=$(cat "${VALIDATION_LOG}")
    verified_count=$(echo "$content" | grep -c 'verified' 2>/dev/null || echo "0")
    invalid_count=$(echo "$content" | grep -c 'invalid' 2>/dev/null || echo "0")
    needs_review_count=$(echo "$content" | grep -c 'needs_review' 2>/dev/null || echo "0")

    check "Log contains 'verified' entries (valid business email scored correctly)" \
        "$([ "${verified_count:-0}" -ge 1 ] && echo 0 || echo 1)"
    check "Log contains 'invalid' entries (bad syntax/disposable domain scored correctly)" \
        "$([ "${invalid_count:-0}" -ge 1 ] && echo 0 || echo 1)"
    check "Log contains 'needs_review' entries (role/free email scored correctly)" \
        "$([ "${needs_review_count:-0}" -ge 1 ] && echo 0 || echo 1)"
fi

# AC: Mautic API is reachable (401 = auth required = up; 200 = open)
mautic_code=$(curl -s -o /dev/null -w "%{http_code}" "${MAUTIC_URL}/api/" 2>/dev/null || echo "000")
check "Mautic API reachable at ${MAUTIC_URL}/api/" \
    "$([ "$mautic_code" = "401" ] || [ "$mautic_code" = "200" ] && echo 0 || echo 1)"

# AC: No DNS/API timeout errors blocking the workflow
if [ -f "${VALIDATION_LOG}" ]; then
    # Timeout errors would cause entire rows to be skipped; check for error markers
    error_count=$(grep -ci "dns_error\|connection_timeout\|CRITICAL_ERROR" "${VALIDATION_LOG}" 2>/dev/null || echo "0")
    check "No blocking DNS/API timeout errors in validation log" \
        "$([ "${error_count:-0}" -eq 0 ] && echo 0 || echo 1)"
fi

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
else
    exit 0
fi
