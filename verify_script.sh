#!/usr/bin/env bash
# US-014 Verification Script: Final integration testing and completion
# Verifies all prior story acceptance criteria + US-014 integration tests.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Activate venv if present
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

FAIL=0
PASS_COUNT=0
FAIL_COUNT=0

report() {
    local status="$1"
    local label="$2"
    if [ "$status" -eq 0 ]; then
        echo "PASS: $label"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "FAIL: $label"
        FAIL=1
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "=== US-014 Final Integration Verification ==="
echo ""

# --- AC: src/n8n/credential_manager.py implemented ---
echo "--- Checking credential_manager.py exists ---"
if [ -f "$PROJECT_ROOT/src/n8n/credential_manager.py" ]; then
    report 0 "src/n8n/credential_manager.py exists"
else
    report 1 "src/n8n/credential_manager.py missing"
fi

# --- Prior story: US-009 N8N Email Validation Workflow ---
echo ""
echo "--- Running US-009 tests (N8N Email Validation Workflow) ---"
set +e
US009_OUT=$(python3 tests/US-009_n8n_email_validation_workflow.test.py 2>&1)
US009_EXIT=$?
set -e
report $US009_EXIT "US-009: N8N Email Validation Workflow tests pass"
if [ $US009_EXIT -ne 0 ]; then
    echo "$US009_OUT" | tail -10
fi

# --- Prior story: US-011 N8N Credential Connectivity ---
echo ""
echo "--- Running US-011 tests (N8N Credential Connectivity) ---"
set +e
US011_OUT=$(python3 tests/US-011_n8n_credential_connectivity.test.py 2>&1)
US011_EXIT=$?
set -e
report $US011_EXIT "US-011: N8N Credential Connectivity tests pass"
if [ $US011_EXIT -ne 0 ]; then
    echo "$US011_OUT" | tail -15
fi

# --- Prior story: US-012 Documentation ---
echo ""
echo "--- Running US-012 tests (Documentation) ---"
set +e
US012_OUT=$(python3 tests/US-012_documentation.test.py 2>&1)
US012_EXIT=$?
set -e
report $US012_EXIT "US-012: Documentation tests pass"
if [ $US012_EXIT -ne 0 ]; then
    echo "$US012_OUT" | grep -E "FAIL:|Error" | head -10
fi

# --- Prior story: US-013 Email Warmup Plan ---
echo ""
echo "--- Running US-013 tests (Email Warmup Plan) ---"
set +e
US013_OUT=$(python3 tests/US-013_email_warmup_plan.test.py 2>&1)
US013_EXIT=$?
set -e
report $US013_EXIT "US-013: Email Warmup Plan tests pass"
if [ $US013_EXIT -ne 0 ]; then
    echo "$US013_OUT" | grep -E "FAIL:|Error" | head -10
fi

# --- US-014 Integration Tests ---
echo ""
echo "--- Running US-014 integration tests ---"
if [ -f "$PROJECT_ROOT/tests/US-014_integration_testing.test.py" ]; then
    set +e
    US014_OUT=$(python3 tests/US-014_integration_testing.test.py 2>&1)
    US014_EXIT=$?
    set -e
    report $US014_EXIT "US-014: Integration tests pass"
    if [ $US014_EXIT -ne 0 ]; then
        echo "$US014_OUT" | tail -20
    fi
else
    report 1 "US-014: tests/US-014_integration_testing.test.py missing"
fi

# --- AC 1: Skip logic module importable ---
echo ""
echo "--- Verifying AC: Skip logic (enrichment status) ---"
set +e
python3 -c "
from src.n8n.credential_manager import N8NCredentialManager, N8NCredentialError
m = N8NCredentialManager('http://localhost:8090/api/v1', 'key')
# verify empty key returns False (skip logic guard)
assert m.verify_apollo_connectivity('') == False
assert m.verify_ipinfo_connectivity('') == False
assert m.verify_apify_connectivity('') == False
print('Skip logic guard: empty credentials return False')
" 2>&1
SKIP_EXIT=$?
set -e
report $SKIP_EXIT "AC 1: Skip logic / empty credential guard works"

# --- AC 7: enrichment_status determination ---
echo ""
echo "--- Verifying AC: verify_all_credentials returns status dict ---"
set +e
python3 -c "
from unittest.mock import patch, MagicMock
from src.n8n.credential_manager import N8NCredentialManager
m = N8NCredentialManager('http://localhost:8090/api/v1', 'key')
cmap = {
    'apollo': {'api_key': 'k1'},
    'ipinfo': {'token': 't1'},
    'apify': {'api_token': 'a1'},
    'mautic': {'api_url': 'http://m.local', 'username': 'u', 'password': 'p'},
}
with patch.object(m, 'verify_apollo_connectivity', return_value=True), \
     patch.object(m, 'verify_ipinfo_connectivity', return_value=True), \
     patch.object(m, 'verify_apify_connectivity', return_value=True), \
     patch.object(m, 'verify_mautic_connectivity', return_value=True):
    result = m.verify_all_credentials(cmap)
assert isinstance(result, dict), 'verify_all_credentials must return dict'
assert set(result.keys()) >= {'apollo','ipinfo','apify','mautic'}
assert all(result.values()), 'All services should be True'
" 2>&1
AC7_EXIT=$?
set -e
report $AC7_EXIT "AC 7: enrichment_status determination (verify_all_credentials) works"

# --- AC 8: Error handling / N8NCredentialError raised on N8N auth failure ---
echo ""
echo "--- Verifying AC: Error handling and circuit breaker ---"
set +e
python3 -c "
from unittest.mock import patch, MagicMock
import requests as req
from src.n8n.credential_manager import N8NCredentialManager, N8NCredentialError
m = N8NCredentialManager('http://localhost:8090/api/v1', 'key')
mock_resp = MagicMock()
mock_resp.status_code = 401
mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError('401')
with patch('requests.post', return_value=mock_resp):
    try:
        m.create_apollo_credential('testkey')
        raise AssertionError('Expected N8NCredentialError')
    except N8NCredentialError:
        pass
" 2>&1
AC8_EXIT=$?
set -e
report $AC8_EXIT "AC 8: Error handling raises N8NCredentialError on auth failure"

# --- AC 9: Batch processing rate limits (RateLimitHandler importable) ---
echo ""
echo "--- Verifying AC: Batch processing and rate limits ---"
set +e
python3 -c "
from src.execution.rate_limit_handler import RateLimitHandler
print('RateLimitHandler imported successfully')
" 2>&1
AC9_EXIT=$?
set -e
report $AC9_EXIT "AC 9: Batch/rate limit handler importable"

# --- Documentation checks (US-012, US-013) ---
ENRICHMENT_DOC="$HOME/projects/marketing-automation/docs/n8n-enrichment-pipeline.md"
WARMUP_DOC="$HOME/projects/marketing-automation/docs/email-warmup-plan.md"
echo ""
echo "--- Verifying documentation files ---"
[ -f "$ENRICHMENT_DOC" ] && report 0 "n8n-enrichment-pipeline.md exists" || report 1 "n8n-enrichment-pipeline.md missing"
[ -f "$WARMUP_DOC" ] && report 0 "email-warmup-plan.md exists" || report 1 "email-warmup-plan.md missing"

echo ""
echo "======================================="
echo "Results: $FAIL_COUNT failure(s), $PASS_COUNT pass(es)"
echo "======================================="

if [ "$FAIL" -eq 0 ]; then
    echo "All US-014 verification checks passed."
    exit 0
else
    echo "One or more verification checks failed."
    exit 1
fi
