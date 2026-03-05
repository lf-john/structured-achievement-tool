"""
IMPLEMENTATION PLAN for US-002:
Create SAT-compatible Seven Sweeps JSON scoring template

Components:
  - seven-sweeps-sat.md: Markdown template at
    ~/projects/marketing-automation/templates/quality-gate/seven-sweeps-sat.md
    Contains all 7 sweeps with scoring rubrics, JSON output schema, examples,
    and SAT integration instructions.
  - src/evaluation/seven_sweeps_gate.py: Python module implementing check_quality_gate()
    Validates LLM JSON output against the schema, returns (passed: bool, result: dict).

Data Flow:
  1. SAT story calls LLM with template + copy → LLM returns JSON string
  2. check_quality_gate(llm_response) parses and validates JSON
  3. Returns (overall_pass, result) for gate logic

Integration Points:
  - Template read by SAT story executor as prompt template
  - check_quality_gate() imported by SAT story executor gate verification step
  - src/evaluation/ already exists (geval_scorer.py present)

Edge Cases:
  - overall_score exactly 70 (boundary: should pass if all sweeps >= 3)
  - One sweep at exactly 3 (boundary pass)
  - One sweep at 2 (fails sweep, overall_pass must be false even if score >= 70)
  - All sweeps at 5 → overall_score = 100
  - All sweeps at 3 → overall_score = round(21/35 * 100) = 60 → overall_pass = false
  - Invalid JSON input
  - Missing required sweep keys
  - overall_pass inconsistency (true when sweeps fail)

Test Cases:
  1. AC: File exists at correct path -> test_template_file_exists
  2. AC: All 7 sweeps documented with 1-5 scoring -> test_all_seven_sweeps_present
  3. AC: JSON output schema documented with all required fields ->
         test_json_schema_documented
  4. AC: Thresholds documented (>= 3 per sweep, >= 70 overall) ->
         test_scoring_thresholds_documented
  5. AC: Pass/fail logic included -> test_pass_fail_logic_documented
  6. AC: Example with overall_pass true -> test_passing_example_present
  7. AC: Example with overall_pass false -> test_failing_example_present
  8. AC: JSON examples are valid parseable JSON -> test_examples_are_valid_json
  9. AC: check_quality_gate accepts valid passing JSON -> test_gate_accepts_passing_json
  10. AC: check_quality_gate accepts valid failing JSON -> test_gate_accepts_failing_json
  11. AC: check_quality_gate raises on invalid JSON -> test_gate_rejects_invalid_json
  12. AC: check_quality_gate raises on missing sweep -> test_gate_rejects_missing_sweep
  13. AC: Scoring formula consistent (round(sum/35*100)) ->
          test_overall_score_formula_consistent
  14. Edge: overall_pass false when one sweep < 3 even if score >= 70 ->
            test_overall_pass_false_when_any_sweep_fails
  15. Edge: overall_pass false when overall_score < 70 even if all sweeps >= 3 ->
            test_overall_pass_false_when_score_below_70
"""

import json
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module under test — will fail with ImportError until implemented (TDD-RED)
# ---------------------------------------------------------------------------
from src.evaluation.seven_sweeps_gate import check_quality_gate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TEMPLATE_PATH = Path.home() / "projects/marketing-automation/templates/quality-gate/seven-sweeps-sat.md"

EXPECTED_SWEEPS = [
    "clarity",
    "observation_hook",
    "problem_resonance",
    "proof_strength",
    "cta_precision",
    "brand_voice",
    "personalization_depth",
]

# Canonical JSON result shape for a fully-passing evaluation
_PASSING_RESULT = {
    "overall_pass": True,
    "overall_score": 91,
    "sweeps": {s: {"score": 5, "pass": True, "issues": []} for s in EXPECTED_SWEEPS},
    "revised_copy": "Hi {contactfield=firstname}, test copy.",
}
# Override a couple of sweeps to match template example values
_PASSING_RESULT["sweeps"]["problem_resonance"] = {
    "score": 4,
    "pass": True,
    "issues": ["Minor issue with problem anchor."],
}
_PASSING_RESULT["sweeps"]["brand_voice"] = {
    "score": 4,
    "pass": True,
    "issues": ["Slightly informal phrase."],
}
_PASSING_RESULT["sweeps"]["personalization_depth"] = {
    "score": 4,
    "pass": True,
    "issues": ["L3 token opportunity missed."],
}

_FAILING_RESULT = {
    "overall_pass": False,
    "overall_score": 46,
    "sweeps": {
        "clarity": {"score": 3, "pass": True, "issues": ["Generic proof claim."]},
        "observation_hook": {"score": 2, "pass": False, "issues": ["Generic opener."]},
        "problem_resonance": {"score": 2, "pass": False, "issues": ["Too abstract."]},
        "proof_strength": {"score": 1, "pass": False, "issues": ["No quantification."]},
        "cta_precision": {"score": 2, "pass": False, "issues": ["Vague CTA."]},
        "brand_voice": {"score": 2, "pass": False, "issues": ["Superlative present."]},
        "personalization_depth": {"score": 1, "pass": False, "issues": ["No tokens."]},
    },
    "revised_copy": "Hi {contactfield=firstname}, revised copy here.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _extract_json_blocks(text: str) -> list:
    """Return all ```json ... ``` code blocks from markdown text."""
    return re.findall(r"```json\s*(.*?)```", text, re.DOTALL)


# ===========================================================================
# Template File Structure Tests
# ===========================================================================


class TestTemplateFileStructure:
    def test_template_file_exists(self):
        """AC: File exists at the correct path."""
        assert TEMPLATE_PATH.exists(), f"Template file not found at {TEMPLATE_PATH}"

    def test_all_seven_sweeps_present(self):
        """AC: All 7 sweeps described with numeric scoring (1-5 scale)."""
        content = _load_template()
        for sweep in EXPECTED_SWEEPS:
            sweep_display = sweep.replace("_", " ").title()
            assert sweep_display.lower() in content.lower() or sweep in content.lower(), (
                f"Sweep '{sweep}' not found in template"
            )
        # Each sweep must have score rubric with 1-5
        for score in range(1, 6):
            assert f"**{score}**" in content or f"- **{score}**" in content, (
                f"Score rubric value {score} not found in template"
            )

    def test_json_schema_documented(self):
        """AC: Complete JSON output schema documented with all required fields."""
        content = _load_template()
        required_fields = [
            "overall_pass",
            "overall_score",
            "sweeps",
            "revised_copy",
            "issues",
            "score",
            "pass",
        ]
        for field in required_fields:
            assert f'"{field}"' in content or f"'{field}'" in content or field in content, (
                f"Field '{field}' not found in JSON schema documentation"
            )
        for sweep in EXPECTED_SWEEPS:
            assert sweep in content, f"Sweep key '{sweep}' not in schema"

    def test_scoring_thresholds_documented(self):
        """AC: Thresholds documented — each sweep >= 3/5, overall >= 70/100."""
        content = _load_template()
        assert ">= 3" in content or "≥ 3" in content or ">= 3" in content, (
            "Per-sweep pass threshold (>= 3) not documented"
        )
        assert "70" in content, "Overall score threshold (70) not documented"
        assert "100" in content, "Overall score scale (100) not documented"

    def test_pass_fail_logic_documented(self):
        """AC: Pass/fail logic included and transparent."""
        content = _load_template()
        assert "overall_pass" in content, "'overall_pass' logic not present"
        assert "overall_score" in content, "'overall_score' logic not present"
        # Logic must mention both conditions together
        assert "AND" in content or "and" in content, "Combined pass condition (AND) not documented"

    def test_passing_example_present(self):
        """AC: Example JSON output demonstrates passing case (overall_pass: true)."""
        content = _load_template()
        assert '"overall_pass": true' in content or "'overall_pass': true" in content, (
            "Passing example with overall_pass: true not found"
        )

    def test_failing_example_present(self):
        """AC: Example JSON output demonstrates failing case (overall_pass: false)."""
        content = _load_template()
        assert '"overall_pass": false' in content or "'overall_pass': false" in content, (
            "Failing example with overall_pass: false not found"
        )

    def test_examples_are_valid_json(self):
        """AC: JSON examples in the template are parseable."""
        content = _load_template()
        blocks = _extract_json_blocks(content)
        # Filter to blocks that look like quality gate output (have overall_pass)
        gate_blocks = [b for b in blocks if "overall_pass" in b]
        assert len(gate_blocks) >= 2, f"Expected at least 2 JSON example blocks, found {len(gate_blocks)}"
        for block in gate_blocks:
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError as e:
                pytest.fail(f"JSON example block is not valid JSON: {e}\n{block[:200]}")
            assert "overall_pass" in parsed
            assert "overall_score" in parsed
            assert "sweeps" in parsed
            assert "revised_copy" in parsed

    def test_sat_integration_section_present(self):
        """AC: Template is complete and immediately usable for SAT integration."""
        content = _load_template()
        assert "SAT" in content, "No SAT integration section found"
        assert "check_quality_gate" in content, "Gate verification function not documented in template"
        assert "{{COPY_TO_REVIEW}}" in content, (
            "Template placeholder {{COPY_TO_REVIEW}} not found — SAT cannot inject copy"
        )

    def test_logical_front_proof_points_present(self):
        """AC: Uses Logical Front proof points and brand voice in examples."""
        content = _load_template()
        assert "Logical Front" in content, "Logical Front brand not mentioned"
        assert "1,000,000" in content or "1M+" in content, "1M+ desktops proof point missing"
        assert "321" in content, "321 customers proof point missing"
        assert "30" in content and "45%" in content, "30-45% cost reduction proof missing"


# ===========================================================================
# check_quality_gate Function Tests
# ===========================================================================


class TestCheckQualityGate:
    def test_gate_accepts_passing_json(self):
        """AC: check_quality_gate returns (True, dict) for valid passing JSON."""
        payload = json.dumps(_PASSING_RESULT)
        passed, result = check_quality_gate(payload)
        assert passed is True
        assert result["overall_pass"] is True
        assert 0 <= result["overall_score"] <= 100

    def test_gate_accepts_failing_json(self):
        """AC: check_quality_gate returns (False, dict) for failing JSON."""
        payload = json.dumps(_FAILING_RESULT)
        passed, result = check_quality_gate(payload)
        assert passed is False
        assert result["overall_pass"] is False

    def test_gate_returns_all_sweep_keys(self):
        """AC: Result contains all 7 sweep names."""
        payload = json.dumps(_PASSING_RESULT)
        _, result = check_quality_gate(payload)
        for sweep in EXPECTED_SWEEPS:
            assert sweep in result["sweeps"], f"Sweep '{sweep}' missing from result"

    def test_gate_validates_sweep_score_range(self):
        """AC: Each sweep score is integer 1-5."""
        payload = json.dumps(_PASSING_RESULT)
        _, result = check_quality_gate(payload)
        for sweep in EXPECTED_SWEEPS:
            score = result["sweeps"][sweep]["score"]
            assert isinstance(score, int), f"Score for {sweep} is not int"
            assert 1 <= score <= 5, f"Score {score} for {sweep} out of range 1-5"

    def test_gate_validates_overall_score_range(self):
        """AC: overall_score is integer 0-100."""
        payload = json.dumps(_PASSING_RESULT)
        _, result = check_quality_gate(payload)
        assert isinstance(result["overall_score"], int)
        assert 0 <= result["overall_score"] <= 100

    def test_gate_validates_revised_copy_is_string(self):
        """AC: revised_copy is a string."""
        payload = json.dumps(_PASSING_RESULT)
        _, result = check_quality_gate(payload)
        assert isinstance(result["revised_copy"], str)

    def test_gate_validates_issues_are_lists(self):
        """AC: Each sweep issues field is a list."""
        payload = json.dumps(_PASSING_RESULT)
        _, result = check_quality_gate(payload)
        for sweep in EXPECTED_SWEEPS:
            assert isinstance(result["sweeps"][sweep]["issues"], list), f"issues for {sweep} is not a list"

    def test_gate_rejects_invalid_json(self):
        """AC: check_quality_gate raises ValueError on unparseable input."""
        with pytest.raises((ValueError, json.JSONDecodeError)):
            check_quality_gate("this is not json")

    def test_gate_rejects_missing_sweep(self):
        """AC: check_quality_gate raises on missing required sweep."""
        bad = dict(_PASSING_RESULT)
        bad["sweeps"] = {k: v for k, v in _PASSING_RESULT["sweeps"].items() if k != "clarity"}
        with pytest.raises((AssertionError, KeyError, ValueError)):
            check_quality_gate(json.dumps(bad))

    def test_gate_rejects_missing_overall_pass(self):
        """AC: check_quality_gate raises when overall_pass missing."""
        bad = {k: v for k, v in _PASSING_RESULT.items() if k != "overall_pass"}
        with pytest.raises((AssertionError, KeyError, ValueError)):
            check_quality_gate(json.dumps(bad))

    def test_overall_pass_false_when_any_sweep_fails(self):
        """Edge: overall_pass must be False when any sweep score < 3."""
        # Build result where all but one sweep score 5, but one scores 2
        tricky = json.loads(json.dumps(_PASSING_RESULT))
        tricky["sweeps"]["clarity"]["score"] = 2
        tricky["sweeps"]["clarity"]["pass"] = False
        tricky["overall_pass"] = True  # Lie about overall_pass
        tricky["overall_score"] = 97  # High score, but one sweep fails
        # Gate should detect the inconsistency and return passed=False
        passed, _ = check_quality_gate(json.dumps(tricky))
        assert passed is False, "overall_pass should be False when any sweep score < 3"

    def test_overall_pass_false_when_score_below_70(self):
        """Edge: overall_pass must be False when overall_score < 70."""
        low_score = json.loads(json.dumps(_PASSING_RESULT))
        low_score["overall_score"] = 60
        low_score["overall_pass"] = True  # Lie about it
        passed, _ = check_quality_gate(json.dumps(low_score))
        assert passed is False, "overall_pass should be False when overall_score < 70"

    def test_gate_derives_correct_overall_score(self):
        """AC: overall_score is round(sum_of_scores / 35 * 100)."""
        # All sweeps at 5 → sum=35 → score=100
        perfect = json.loads(json.dumps(_PASSING_RESULT))
        for s in EXPECTED_SWEEPS:
            perfect["sweeps"][s] = {"score": 5, "pass": True, "issues": []}
        perfect["overall_score"] = 100
        perfect["overall_pass"] = True
        passed, result = check_quality_gate(json.dumps(perfect))
        assert passed is True
        assert result["overall_score"] == 100

    def test_gate_boundary_all_sweeps_at_3(self):
        """Edge: All sweeps at exactly 3 → score=60 → overall_pass=False."""
        boundary = {
            "overall_pass": False,
            "overall_score": 60,  # round(21/35 * 100) = 60
            "sweeps": {s: {"score": 3, "pass": True, "issues": []} for s in EXPECTED_SWEEPS},
            "revised_copy": "Boundary test copy.",
        }
        passed, _result = check_quality_gate(json.dumps(boundary))
        assert passed is False, "All sweeps at 3 gives overall_score=60 which is < 70, so overall_pass must be False"

    def test_gate_boundary_sweep_score_exactly_3(self):
        """Edge: A sweep with score exactly 3 should have pass=True."""
        result_3 = json.loads(json.dumps(_PASSING_RESULT))
        result_3["sweeps"]["clarity"]["score"] = 3
        result_3["sweeps"]["clarity"]["pass"] = True
        _, result = check_quality_gate(json.dumps(result_3))
        assert result["sweeps"]["clarity"]["pass"] is True, "Score 3 should be a passing score (threshold is >= 3)"


# ===========================================================================
# Entry point — ensure exit code 1 on any failure
# ===========================================================================

if __name__ == "__main__":
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v"],
        capture_output=False,
    )
    sys.exit(result.returncode)
