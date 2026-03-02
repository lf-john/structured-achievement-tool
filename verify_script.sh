#!/bin/bash
# Verification script for US-007: LinkedIn Calendar Template assembled
set -e

TARGET="$HOME/projects/marketing-automation/templates/linkedin-calendar-template.md"

# 1. File must exist
if [ ! -f "$TARGET" ]; then
    echo "FAIL: File not found: $TARGET"
    exit 1
fi

# 2. File must be non-empty (at least 5000 chars for a comprehensive template)
SIZE=$(wc -c < "$TARGET")
if [ "$SIZE" -lt 5000 ]; then
    echo "FAIL: File too small ($SIZE bytes), expected comprehensive template"
    exit 1
fi

# 3. Check for all required sections
REQUIRED_SECTIONS=(
    "Pillar"
    "Template"
    "Calendar"
    "Engagement"
    "KPI"
    "Sample Month"
)

for section in "${REQUIRED_SECTIONS[@]}"; do
    if ! grep -qi "$section" "$TARGET"; then
        echo "FAIL: Missing required section containing: $section"
        exit 1
    fi
done

# 4. Must have at least 16 templates referenced
TEMPLATE_COUNT=$(grep -ci "^### Template\|^## Template" "$TARGET" || true)
if [ "$TEMPLATE_COUNT" -lt 16 ]; then
    echo "FAIL: Expected at least 16 templates, found $TEMPLATE_COUNT"
    exit 1
fi

# 5. Must be valid markdown with proper heading structure
HEADING_COUNT=$(grep -c "^#" "$TARGET" || true)
if [ "$HEADING_COUNT" -lt 5 ]; then
    echo "FAIL: File has too few headings ($HEADING_COUNT), not properly structured markdown"
    exit 1
fi

echo "PASS: $TARGET exists with all required sections ($SIZE bytes, $HEADING_COUNT headings, $TEMPLATE_COUNT templates)"
exit 0
