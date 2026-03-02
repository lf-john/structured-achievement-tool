#!/usr/bin/env bash
# US-013 Verification Script: Email Warmup Plan document for logicalfront.net

set -euo pipefail

DOC_PATH="$HOME/projects/marketing-automation/docs/email-warmup-plan.md"
SCRIPT_PATH="$HOME/projects/marketing-automation/scripts/warmup_daily_check.sh"
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

# Document exists
check "Documentation file created at correct path" "[ -f '$DOC_PATH' ]"

if [ ! -f "$DOC_PATH" ]; then
    echo "Cannot proceed with content checks — file missing"
    exit 1
fi

# Week-by-Week Schedule: all 28 days present
ALL_DAYS=1
for day in $(seq 1 28); do
    if ! grep -q "Day $day" "$DOC_PATH"; then
        echo "FAIL: Missing Day $day in schedule"
        ALL_DAYS=0
        FAIL=1
    fi
done
[ "$ALL_DAYS" -eq 1 ] && echo "PASS: All 28 days present in Week-by-Week Schedule"

# Volume targets
check "Volume target 50/day present" "grep -q '50' '$DOC_PATH'"
check "Volume target 2500/day present" "grep -qE '2,500|2500' '$DOC_PATH'"

# Mautic cron --limit values
check "Mautic cron --limit values present" "grep -q '\-\-limit' '$DOC_PATH'"

# AWS SES CLI commands
check "get-send-statistics CLI command present" "grep -q 'get-send-statistics' '$DOC_PATH'"
check "get-account CLI command present" "grep -q 'get-account' '$DOC_PATH'"
check "Mautic queue check in monitoring checklist" "grep -qi 'mautic.*queue\|queue.*mautic' '$DOC_PATH'"

# Abort criteria thresholds
check "Bounce rate threshold 5% in abort criteria" "grep -q '5%' '$DOC_PATH'"
check "Complaint rate threshold 0.1% in abort criteria" "grep -q '0.1%' '$DOC_PATH'"
check "SES suspension abort trigger present" "grep -qi 'suspension\|suspend' '$DOC_PATH'"
check "Spam folder delivery abort criterion present" "grep -qi 'spam folder' '$DOC_PATH'"

# Recovery Steps section
check "Recovery Steps section present" "grep -qi 'recovery\|recover' '$DOC_PATH'"
check "Pause procedure in recovery steps" "grep -qi 'pause' '$DOC_PATH'"
check "Contact remediation in recovery steps" "grep -qi 'remediat' '$DOC_PATH'"
check "Resume at 50% volume in recovery steps" "grep -q '50%' '$DOC_PATH'"

# Campaign Activation Schedule
check "Campaign Activation Schedule section present" "grep -qi 'campaign activation\|activation schedule' '$DOC_PATH'"
check "Week 1 welcome campaign mentioned" "grep -qi 'week 1.*welcome\|welcome.*week 1' '$DOC_PATH'"
check "Week 2 healthcare nurture mentioned" "grep -qi 'healthcare\|nurture' '$DOC_PATH'"
check "Cold outreach mentioned" "grep -qi 'cold outreach\|cold' '$DOC_PATH'"

# Monitoring script content in document
check "warmup_daily_check.sh referenced in document" "grep -q 'warmup_daily_check.sh' '$DOC_PATH'"
check "ntfy.sh notifications in monitoring script" "grep -q 'ntfy' '$DOC_PATH'"
check "Test email sat.system23@gmail.com present" "grep -q 'sat.system23@gmail.com' '$DOC_PATH'"

# Markdown table formatting
check "Markdown pipe-delimited tables present" "grep -q '^|' '$DOC_PATH'"

# Section hierarchy (H1/H2/H3)
check "H2 sections present" "grep -q '^## ' '$DOC_PATH'"
check "H3 sections present" "grep -q '^### ' '$DOC_PATH'"

# Standalone warmup_daily_check.sh script file
check "warmup_daily_check.sh exists as standalone file" "[ -f '$SCRIPT_PATH' ]"
check "warmup_daily_check.sh is executable" "[ -x '$SCRIPT_PATH' ]"

# Document must be substantial (at least 200 lines)
LINE_COUNT=$(wc -l < "$DOC_PATH")
if [ "$LINE_COUNT" -ge 200 ]; then
    echo "PASS: Documentation is substantial ($LINE_COUNT lines)"
else
    echo "FAIL: Documentation too short ($LINE_COUNT lines, expected >= 200)"
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
