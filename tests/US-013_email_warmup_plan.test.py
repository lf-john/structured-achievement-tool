"""
IMPLEMENTATION PLAN for US-013:

Components:
  - Documentation file: ~/projects/marketing-automation/docs/email-warmup-plan.md
    Created as a markdown document with all required sections for a 4-week
    email warmup plan for logicalfront.net via Amazon SES

Test Cases:
  1. [AC 1] File exists at ~/projects/marketing-automation/docs/email-warmup-plan.md
  2. [AC 2] Week-by-Week Schedule section with 28-day breakdown, volumes (50→2500/day), segments
  3. [AC 3] Mautic Cron Configuration section with --limit values for each of 4 phases
  4. [AC 4] Daily Monitoring Checklist with AWS CLI commands: get-send-statistics, get-account, queue checks
  5. [AC 5] Abort Criteria table: bounce >5%, complaint >0.1%, SES suspension, spam folder
  6. [AC 6] Recovery Steps: pause, contact remediation, validation re-run, wait period, resume at 50%
  7. [AC 7] Campaign Activation Schedule: Week 1 welcome, Week 2 healthcare nurture, Week 3 education, Week 4 all
  8. [AC 8] Monitoring script warmup_daily_check.sh with SES stats, queue, ntfy.sh, test email logic
  9. [AC 9] Markdown tables with pipe delimiters and alignment rows
  10. [AC 10] Well-structured document with clear section hierarchy

Edge Cases:
  - File is not empty (has substantive content, not a stub)
  - Volume progression from 50 to 2500 is documented
  - Test email address sat.system23@gmail.com referenced for daily test validation
  - Script includes ntfy.sh notification integration
"""

import os
import re
import sys

DOC_PATH = os.path.expanduser(
    "~/projects/marketing-automation/docs/email-warmup-plan.md"
)

fail_count = 0


def assert_true(condition, message):
    global fail_count
    if not condition:
        print(f"  FAIL: {message}")
        fail_count += 1
    else:
        print(f"  PASS: {message}")


def load_doc():
    if not os.path.exists(DOC_PATH):
        return None
    with open(DOC_PATH, "r") as f:
        return f.read()


print("\n=== US-013 Email Warmup Plan Tests ===\n")

# --- AC 1: File exists at correct path ---
print("Test: File exists at expected path")
assert_true(os.path.exists(DOC_PATH), f"Documentation file exists at {DOC_PATH}")

content = load_doc()
if content is None:
    print("  FAIL: Documentation file is readable")
    print("  FAIL: Documentation file has substantive content (>1000 chars)")
    print("\nCannot continue — file does not exist or is unreadable")
    sys.exit(1)

assert_true(content is not None, "Documentation file is readable")
assert_true(len(content) > 1000, "Documentation file has substantive content (>1000 chars)")

content_lower = content.lower()

# --- AC 2: Week-by-Week Schedule with 28-day breakdown ---
print("\nTest: Week-by-Week Schedule section with 28-day breakdown")
assert_true(
    re.search(r"#+ .*week.*schedule|#+ .*schedule|#+ .*warmup.*schedule|#+ .*day.*by.*day", content, re.IGNORECASE) is not None,
    "Has a schedule or week-by-week section heading",
)
# 28 days must be accounted for — look for Day 1 through Day 28 references
day_matches = re.findall(r"\bday\s+\d+\b", content, re.IGNORECASE)
assert_true(
    len(day_matches) >= 10,
    f"Schedule references multiple days (found {len(day_matches)} day references; expect >=10)",
)
# Volume ramp: 50/day at start
assert_true(
    "50" in content,
    "Schedule includes 50/day volume (start of warmup)",
)
# Volume ramp: 2500/day at peak
assert_true(
    "2500" in content or "2,500" in content,
    "Schedule includes 2,500/day volume (end of warmup)",
)
# Segment assignments
assert_true(
    any(word in content_lower for word in ["segment", "icp", "healthcare", "education", "list"]),
    "Schedule references segment targeting",
)

# --- AC 3: Mautic Cron Configuration section ---
print("\nTest: Mautic Cron Configuration section")
assert_true(
    re.search(r"#+ .*cron|#+ .*mautic.*config|#+ .*config.*mautic", content, re.IGNORECASE) is not None,
    "Has Mautic cron configuration section heading",
)
# Must include --limit flag values
assert_true(
    "--limit" in content,
    "Cron configuration includes --limit parameter",
)
# Should mention mautic:emails:send or similar mautic CLI commands
assert_true(
    re.search(r"mautic:\w+|\bmautic\b.*send|php.*console.*mautic", content, re.IGNORECASE) is not None,
    "Cron section includes Mautic CLI/console commands",
)
# Should cover multiple phases/weeks
week_refs = re.findall(r"\bweek\s+[1-4]\b", content, re.IGNORECASE)
assert_true(
    len(set(w.lower() for w in week_refs)) >= 4,
    f"Cron config covers all 4 weeks (found references: {set(w.lower() for w in week_refs)})",
)

# --- AC 4: Daily Monitoring Checklist with AWS CLI commands ---
print("\nTest: Daily Monitoring Checklist section with AWS CLI commands")
assert_true(
    re.search(r"#+ .*monitor.*checklist|#+ .*daily.*check|#+ .*checklist", content, re.IGNORECASE) is not None,
    "Has monitoring checklist section heading",
)
assert_true(
    "get-send-statistics" in content,
    "Checklist includes 'get-send-statistics' AWS CLI command",
)
assert_true(
    "get-account" in content,
    "Checklist includes 'get-account' AWS CLI command",
)
assert_true(
    any(phrase in content_lower for phrase in ["queue", "mautic queue", "email queue"]),
    "Checklist includes Mautic queue check",
)
assert_true(
    "aws ses" in content_lower or "aws" in content_lower,
    "Checklist references AWS CLI commands",
)

# --- AC 5: Abort Criteria table with thresholds ---
print("\nTest: Abort Criteria table")
assert_true(
    re.search(r"#+ .*abort|#+ .*abort.*criteria|#+ .*stop.*criteria", content, re.IGNORECASE) is not None,
    "Has abort criteria section heading",
)
# Bounce rate threshold >5%
assert_true(
    re.search(r"bounce.*5%|5%.*bounce|bounce.*>\s*5", content, re.IGNORECASE) is not None,
    "Abort criteria specifies bounce rate threshold >5%",
)
# Complaint rate threshold >0.1%
assert_true(
    re.search(r"complaint.*0\.1%|0\.1%.*complaint|complaint.*>\s*0\.1", content, re.IGNORECASE) is not None,
    "Abort criteria specifies complaint rate threshold >0.1%",
)
# SES suspension
assert_true(
    re.search(r"ses.*suspend|suspend.*ses|ses.*pause|account.*suspend", content, re.IGNORECASE) is not None,
    "Abort criteria includes SES suspension trigger",
)
# Spam folder delivery
assert_true(
    any(phrase in content_lower for phrase in ["spam folder", "spam rate", "inbox placement", "spam delivery"]),
    "Abort criteria includes spam folder delivery condition",
)

# --- AC 6: Recovery Steps section ---
print("\nTest: Recovery Steps section")
assert_true(
    re.search(r"#+ .*recover|#+ .*recovery.*step|#+ .*remediat", content, re.IGNORECASE) is not None,
    "Has recovery/remediation steps section heading",
)
# Pause procedure
assert_true(
    any(phrase in content_lower for phrase in ["pause", "halt", "stop sending"]),
    "Recovery steps include pause/halt procedure",
)
# Contact remediation
assert_true(
    any(phrase in content_lower for phrase in ["contact remediation", "list clean", "remove invalid", "clean list", "hygiene"]),
    "Recovery steps include contact remediation",
)
# Validation re-run
assert_true(
    any(phrase in content_lower for phrase in ["re-run", "rerun", "re-validate", "revalidate", "validation"]),
    "Recovery steps include validation re-run",
)
# Wait period
assert_true(
    any(phrase in content_lower for phrase in ["wait", "waiting period", "pause period", "days before"]),
    "Recovery steps include a wait period",
)
# Resume at 50% volume
assert_true(
    re.search(r"resume.*50%|50%.*resume|restart.*50%|50%.*restart", content, re.IGNORECASE) is not None,
    "Recovery steps specify resuming at 50% volume",
)

# --- AC 7: Campaign Activation Schedule ---
print("\nTest: Campaign Activation Schedule")
assert_true(
    re.search(r"#+ .*campaign.*activation|#+ .*activation.*schedule|#+ .*campaign.*schedule|#+ .*rollout", content, re.IGNORECASE) is not None,
    "Has campaign activation schedule section heading",
)
# Week 1: welcome only
assert_true(
    re.search(r"week\s*1.*welcome|welcome.*week\s*1", content, re.IGNORECASE) is not None,
    "Campaign schedule: Week 1 is welcome campaign only",
)
# Week 2: healthcare nurture
assert_true(
    re.search(r"week\s*2.*healthcare|healthcare.*week\s*2|week\s*2.*nurture", content, re.IGNORECASE) is not None,
    "Campaign schedule: Week 2 adds healthcare nurture",
)
# Week 3: education
assert_true(
    re.search(r"week\s*3.*education|education.*week\s*3", content, re.IGNORECASE) is not None,
    "Campaign schedule: Week 3 adds education",
)
# Week 4: all campaigns
assert_true(
    re.search(r"week\s*4.*all|all.*campaign.*week\s*4|week\s*4.*cold|cold.*outreach.*week\s*4", content, re.IGNORECASE) is not None,
    "Campaign schedule: Week 4 activates all campaigns",
)

# --- AC 8: Monitoring Script content ---
print("\nTest: Monitoring Script (warmup_daily_check.sh) included")
assert_true(
    "warmup_daily_check.sh" in content,
    "Document references warmup_daily_check.sh script",
)
# Script should contain SES stats checks
assert_true(
    "get-send-statistics" in content or "ses" in content_lower,
    "Monitoring script performs SES stats checks",
)
# ntfy.sh notifications
assert_true(
    "ntfy" in content_lower or "ntfy.sh" in content_lower,
    "Monitoring script includes ntfy.sh notifications",
)
# Daily test email logic
assert_true(
    "sat.system23@gmail.com" in content,
    "Monitoring script includes daily test email to sat.system23@gmail.com",
)

# --- AC 9: Markdown tables with pipe delimiters ---
print("\nTest: Markdown tables properly formatted")
table_lines = [l for l in content.split("\n") if l.strip().startswith("|")]
assert_true(
    len(table_lines) >= 6,
    f"Has markdown tables with pipe delimiters (found {len(table_lines)} table lines; expect >=6)",
)
# Separator rows (e.g. |---|---|) indicate proper table formatting
separator_lines = [l for l in table_lines if re.match(r"\s*\|[\s\-:]+\|", l)]
assert_true(
    len(separator_lines) >= 1,
    "Markdown tables have alignment/separator rows",
)

# --- AC 10: Well-structured document with section hierarchy ---
print("\nTest: Document structure and section hierarchy")
# Should have multiple heading levels
h1_count = len(re.findall(r"^# ", content, re.MULTILINE))
h2_count = len(re.findall(r"^## ", content, re.MULTILINE))
h3_count = len(re.findall(r"^### ", content, re.MULTILINE))
assert_true(
    h2_count >= 5,
    f"Document has at least 5 H2 sections (found {h2_count})",
)
assert_true(
    h3_count >= 3,
    f"Document has at least 3 H3 subsections (found {h3_count})",
)
# Domain name should be in document
assert_true(
    "logicalfront.net" in content_lower,
    "Document references domain logicalfront.net",
)
# Amazon SES referenced
assert_true(
    "amazon ses" in content_lower or "ses" in content_lower,
    "Document references Amazon SES",
)

# --- Summary ---
print(f"\n{'='*40}")
print(f"Results: {fail_count} failure(s)")
print(f"{'='*40}\n")

sys.exit(1 if fail_count > 0 else 0)
