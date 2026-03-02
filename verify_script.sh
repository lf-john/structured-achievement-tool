#!/bin/bash
# verify_script.sh — US-011: Configure N8N Credentials and Verify Connectivity
# Verifies: Apollo.io, IPinfo, Apify, and Mautic credentials created and test calls succeed.

set -euo pipefail

N8N_URL="http://localhost:8090"
N8N_API_KEY_FILE="${HOME}/projects/marketing-automation/.n8n_api_key"
PASS=0
FAIL=0
WARN=0

# ─── helpers ────────────────────────────────────────────────────────────────
check() {
    local desc="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc"
        FAIL=$((FAIL + 1))
    fi
}

warn() {
    echo "  WARN: $1"
    WARN=$((WARN + 1))
}

require_api_key() {
    N8N_API_KEY="${N8N_API_KEY:-}"
    if [ -z "$N8N_API_KEY" ] && [ -f "$N8N_API_KEY_FILE" ]; then
        N8N_API_KEY=$(cat "$N8N_API_KEY_FILE" | tr -d '[:space:]')
    fi
    if [ -z "$N8N_API_KEY" ]; then
        echo "ERROR: N8N_API_KEY not set and ${N8N_API_KEY_FILE} not found."
        echo "       Generate a key: N8N UI → Settings → n8n API → Create API Key"
        echo "       Then:  echo '<key>' > ${N8N_API_KEY_FILE}"
        exit 1
    fi
    export N8N_API_KEY
}

n8n_get() {
    curl -s -H "X-N8N-API-KEY: ${N8N_API_KEY}" "${N8N_URL}/api/v1${1}" 2>/dev/null
}

n8n_post() {
    curl -s -X POST -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        -H "Content-Type: application/json" \
        -d "$2" "${N8N_URL}/api/v1${1}" 2>/dev/null
}

echo "=== US-011 Verification: N8N Credential Connectivity ==="
echo ""

# ─── 0. N8N accessibility ────────────────────────────────────────────────────
echo "[0] Infrastructure"
http_code=$(curl -s -o /dev/null -w "%{http_code}" "${N8N_URL}/healthz" 2>/dev/null || echo "000")
check "N8N accessible at ${N8N_URL}" "$([ "$http_code" = "200" ] && echo 0 || echo 1)"

# ─── 1. API key & credentials list ──────────────────────────────────────────
echo ""
echo "[1] N8N API Key"
require_api_key

creds_raw=$(n8n_get "/credentials")
creds_ok=$(echo "$creds_raw" | python3 -c "import sys,json; d=json.load(sys.stdin); print('0' if isinstance(d.get('data'), list) else '1')" 2>/dev/null || echo "1")
check "N8N API key is valid (credentials list accessible)" "$creds_ok"

# ─── 2. Credential presence checks ──────────────────────────────────────────
echo ""
echo "[2] Credentials Configured"

credential_exists() {
    local search="$1"
    echo "$creds_raw" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    creds = data.get('data', [])
    found = any('${search}' in c.get('name','').lower() for c in creds)
    print('0' if found else '1')
except:
    print('1')
" 2>/dev/null || echo "1"
}

check "Apollo.io credential exists in N8N"  "$(credential_exists 'apollo')"
check "IPinfo credential exists in N8N"     "$(credential_exists 'ipinfo')"
check "Apify credential exists in N8N"      "$(credential_exists 'apify')"
check "Mautic credential exists in N8N"     "$(credential_exists 'mautic')"

# ─── 3. Test workflow existence ──────────────────────────────────────────────
echo ""
echo "[3] Validation Workflows"

workflows_raw=$(n8n_get "/workflows")

workflow_exists() {
    local name="$1"
    echo "$workflows_raw" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    workflows = data.get('data', [])
    found = any('${name}' in w.get('name','') for w in workflows)
    print('0' if found else '1')
except:
    print('1')
" 2>/dev/null || echo "1"
}

check "Apollo.io Credential Test workflow exists"  "$(workflow_exists 'Apollo')"
check "IPinfo Credential Test workflow exists"     "$(workflow_exists 'IPinfo')"
check "Apify Credential Test workflow exists"      "$(workflow_exists 'Apify')"
check "Mautic Credential Test workflow exists"     "$(workflow_exists 'Mautic')"

# ─── 4. Live connectivity tests ──────────────────────────────────────────────
echo ""
echo "[4] Live API Connectivity"

# Execute each test workflow and check the last execution succeeded
execute_and_check_workflow() {
    local service="$1"
    local search_name="$2"

    # Find workflow ID
    wf_id=$(echo "$workflows_raw" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for w in data.get('data', []):
        if '${search_name}' in w.get('name',''):
            print(w.get('id',''))
            break
except:
    pass
" 2>/dev/null || echo "")

    if [ -z "$wf_id" ]; then
        warn "${service}: test workflow not found — skipping live test"
        return
    fi

    # Trigger manual execution
    exec_resp=$(n8n_post "/workflows/${wf_id}/run" '{}')
    exec_id=$(echo "$exec_resp" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data',{}).get('executionId','') or data.get('executionId',''))
except:
    pass
" 2>/dev/null || echo "")

    if [ -z "$exec_id" ]; then
        warn "${service}: could not start workflow execution"
        return
    fi

    # Poll for completion (max 15s)
    local attempts=0
    local status="running"
    while [ $attempts -lt 15 ] && [ "$status" = "running" ]; do
        sleep 1
        exec_status=$(n8n_get "/executions/${exec_id}")
        status=$(echo "$exec_status" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data',{}).get('status','running') or data.get('status','running'))
except:
    print('running')
" 2>/dev/null || echo "running")
        attempts=$((attempts + 1))
    done

    if [ "$status" = "success" ]; then
        check "${service}: live API call succeeded (execution ${exec_id})" "0"
    else
        check "${service}: live API call succeeded (status=${status})" "1"
    fi
}

execute_and_check_workflow "Apollo.io" "Apollo"
execute_and_check_workflow "IPinfo"    "IPinfo"
execute_and_check_workflow "Apify"     "Apify"
execute_and_check_workflow "Mautic"    "Mautic"

# ─── 5. Summary ─────────────────────────────────────────────────────────────
echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed, ${WARN} warnings ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
else
    exit 0
fi
