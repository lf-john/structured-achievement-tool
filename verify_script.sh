#!/bin/bash
# Verification script for US-002: Seven Sweeps SAT-compatible quality gate template
set -e

TARGET="$HOME/projects/marketing-automation/templates/quality-gate/seven-sweeps-sat.md"

# 1. File exists
if [ ! -f "$TARGET" ]; then
  echo "FAIL: Template file not found at $TARGET"
  exit 1
fi

# 2. All 7 sweeps present with numeric scoring
SWEEPS=("clarity" "observation_hook" "problem_resonance" "proof_strength" "cta_precision" "brand_voice" "personalization_depth")
for sweep in "${SWEEPS[@]}"; do
  if ! grep -qi "$sweep" "$TARGET"; then
    echo "FAIL: Sweep '$sweep' not found in template"
    exit 1
  fi
done

# 3. Scoring scale 1-5 documented
if ! grep -q "1-5\|1.5\|score.*[1-5]\|[1-5].*scale" "$TARGET"; then
  echo "FAIL: 1-5 scoring scale not documented"
  exit 1
fi

# 4. JSON schema present
if ! grep -q '"overall_pass"' "$TARGET"; then
  echo "FAIL: overall_pass field not in JSON schema"
  exit 1
fi
if ! grep -q '"overall_score"' "$TARGET"; then
  echo "FAIL: overall_score field not in JSON schema"
  exit 1
fi
if ! grep -q '"revised_copy"' "$TARGET"; then
  echo "FAIL: revised_copy field not in JSON schema"
  exit 1
fi
if ! grep -q '"issues"' "$TARGET"; then
  echo "FAIL: issues array not in JSON schema"
  exit 1
fi

# 5. Scoring thresholds documented
if ! grep -q ">= 3\|>= 70\|>=.*3\|>=.*70" "$TARGET"; then
  echo "FAIL: Scoring thresholds (>= 3 per sweep, >= 70 overall) not documented"
  exit 1
fi

# 6. Both passing and failing example JSON present
if ! grep -q '"overall_pass": true' "$TARGET"; then
  echo "FAIL: Passing example (overall_pass: true) not found"
  exit 1
fi
if ! grep -q '"overall_pass": false' "$TARGET"; then
  echo "FAIL: Failing example (overall_pass: false) not found"
  exit 1
fi

# 7. Logical Front proof points present
if ! grep -q "1,000,000\|1M+" "$TARGET"; then
  echo "FAIL: Logical Front 1M+ deployments proof point not present"
  exit 1
fi
if ! grep -q "321" "$TARGET"; then
  echo "FAIL: Logical Front 321 customers proof point not present"
  exit 1
fi

# 8. SAT integration instructions present
if ! grep -qi "SAT\|json.loads\|quality.gate\|check_quality_gate" "$TARGET"; then
  echo "FAIL: SAT workflow integration section not found"
  exit 1
fi

echo "PASS: All acceptance criteria verified for seven-sweeps-sat.md"
exit 0
