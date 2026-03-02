"""
IMPLEMENTATION PLAN for US-012:

Components:
  - Documentation file: ~/projects/marketing-automation/docs/n8n-enrichment-pipeline.md
    Created as a markdown document with all required sections

Test Cases:
  1. [AC 1] File exists and has workflow overview section mentioning Lead Coordinator
  2. [AC 2] Architecture diagram section present showing all workflow steps
  3. [AC 3] API credential section lists all services with retrieval instructions
  4. [AC 4] Step-by-step config instructions for Apollo.io, IPinfo, Apify, Mautic in N8N
  5. [AC 5] Import and testing procedures with example test contact data
  6. [AC 6] Rate limits: Apollo 100 req/min, IPinfo 50K/month, Apify async limits
  7. [AC 7] Enrichment field mapping table (input → source → output/transformations)
  8. [AC 8] Cost estimation per-contact and monthly volume calculations
  9. [AC 9] File created at correct path
  10. [AC 10] Troubleshooting section for common issues and errors

Edge Cases:
  - File is not empty (has substantive content, not a stub)
  - All required services mentioned by name in credential section
  - Field mapping table has proper columns
  - Rate limit numbers are accurate
"""

import os
import re
import sys

DOC_PATH = os.path.expanduser(
    "~/projects/marketing-automation/docs/n8n-enrichment-pipeline.md"
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


print("\n=== US-012 Documentation Tests ===\n")

# --- AC 9: File exists at correct path ---
print("Test: File exists at expected path")
assert_true(os.path.exists(DOC_PATH), f"Documentation file exists at {DOC_PATH}")

content = load_doc()
if content is None:
    print("  FAIL: Documentation file is readable")
    print("  FAIL: Documentation file has substantive content (>500 chars)")
    print("\nCannot continue — file does not exist or is unreadable")
    sys.exit(1)

assert_true(content is not None, "Documentation file is readable")
assert_true(len(content) > 500, "Documentation file has substantive content (>500 chars)")

content_lower = content.lower()

# --- AC 1: Workflow overview mentions Lead Coordinator ---
print("\nTest: Workflow overview section")
assert_true(
    re.search(r"#+ .*overview", content, re.IGNORECASE) is not None,
    "Has a 'Overview' section heading",
)
assert_true(
    "lead coordinator" in content_lower,
    "Workflow overview mentions 'Lead Coordinator'",
)

# --- AC 2: Architecture diagram section ---
print("\nTest: Architecture diagram")
assert_true(
    re.search(r"#+ .*architect", content, re.IGNORECASE) is not None
    or re.search(r"#+ .*diagram", content, re.IGNORECASE) is not None,
    "Has an architecture or diagram section heading",
)
# Should show all workflow steps (Apollo, IPinfo, Apify, Mautic at minimum)
assert_true("apollo" in content_lower, "Architecture references Apollo.io")
assert_true("ipinfo" in content_lower, "Architecture references IPinfo")
assert_true("apify" in content_lower, "Architecture references Apify")
assert_true("mautic" in content_lower, "Architecture references Mautic")

# --- AC 3: API credential section with retrieval instructions ---
print("\nTest: API credentials section")
assert_true(
    re.search(r"#+ .*credential", content, re.IGNORECASE) is not None
    or re.search(r"#+ .*api key", content, re.IGNORECASE) is not None,
    "Has an API credentials section heading",
)
for service in ["apollo", "ipinfo", "apify", "mautic"]:
    assert_true(
        service in content_lower,
        f"Credentials section references {service}",
    )
# Should explain where to obtain keys
assert_true(
    any(
        phrase in content_lower
        for phrase in ["obtain", "generate", "retrieve", "sign up", "signup", "create account"]
    ),
    "Credentials section explains how to obtain keys",
)

# --- AC 4: Step-by-step N8N configuration instructions ---
print("\nTest: Step-by-step N8N configuration instructions")
assert_true(
    re.search(r"#+ .*n8n.*config|#+ .*config.*n8n|#+ .*setup|#+ .*configure", content, re.IGNORECASE) is not None,
    "Has N8N configuration section heading",
)
# Must include numbered steps or ordered list for at least one service
assert_true(
    re.search(r"^\s*\d+\.", content, re.MULTILINE) is not None,
    "Has numbered step-by-step instructions",
)
for service in ["apollo", "ipinfo", "apify", "mautic"]:
    assert_true(
        service in content_lower,
        f"N8N config instructions reference {service}",
    )

# --- AC 5: Import and testing procedures with example test data ---
print("\nTest: Import and testing procedures")
assert_true(
    re.search(r"#+ .*import|#+ .*test.*procedure|#+ .*testing", content, re.IGNORECASE) is not None,
    "Has import or testing procedures section",
)
assert_true(
    any(
        phrase in content_lower
        for phrase in ["example", "test contact", "sample", "test data"]
    ),
    "Testing section includes example/test contact data",
)

# --- AC 6: Rate limits with specific values ---
print("\nTest: Rate limits documentation")
assert_true(
    re.search(r"#+ .*rate limit|#+ .*limits|#+ .*throttl", content, re.IGNORECASE) is not None,
    "Has rate limits section heading",
)
assert_true(
    "100" in content and "req" in content_lower,
    "Apollo rate limit (100 req/min) mentioned",
)
assert_true(
    "50" in content and "ipinfo" in content_lower,
    "IPinfo rate limit (50K/month) mentioned",
)
assert_true(
    "apify" in content_lower and any(
        phrase in content_lower for phrase in ["async", "concurrent", "limit"]
    ),
    "Apify async limits mentioned",
)

# --- AC 7: Enrichment field mapping table ---
print("\nTest: Enrichment field mapping table")
assert_true(
    re.search(r"#+ .*field.*map|#+ .*map.*field|#+ .*enrichment.*field", content, re.IGNORECASE) is not None,
    "Has field mapping section heading",
)
# Markdown table should have | separators
table_lines = [l for l in content.split("\n") if l.strip().startswith("|")]
assert_true(len(table_lines) >= 3, "Has markdown table with at least 3 rows (header, separator, data)")
# Table should reference input and output
assert_true(
    any("input" in l.lower() for l in table_lines),
    "Field mapping table has 'Input' column",
)
assert_true(
    any("output" in l.lower() for l in table_lines),
    "Field mapping table has 'Output' column",
)

# --- AC 8: Cost estimation ---
print("\nTest: Cost estimation section")
assert_true(
    re.search(r"#+ .*cost|#+ .*pricing|#+ .*estimation", content, re.IGNORECASE) is not None,
    "Has cost estimation section heading",
)
assert_true(
    any(phrase in content_lower for phrase in ["per contact", "per-contact", "per enrichment"]),
    "Cost section includes per-contact cost",
)
assert_true(
    any(phrase in content_lower for phrase in ["monthly", "per month"]),
    "Cost section includes monthly volume calculation",
)

# --- AC 10: Troubleshooting section ---
print("\nTest: Troubleshooting section")
assert_true(
    re.search(r"#+ .*troubleshoot|#+ .*common issue|#+ .*error", content, re.IGNORECASE) is not None,
    "Has troubleshooting section heading",
)
assert_true(
    any(
        phrase in content_lower
        for phrase in ["error", "issue", "problem", "fail", "debug"]
    ),
    "Troubleshooting section mentions errors or issues",
)

# --- Summary ---
print(f"\n{'='*40}")
print(f"Results: {fail_count} failure(s)")
print(f"{'='*40}\n")

sys.exit(1 if fail_count > 0 else 0)
