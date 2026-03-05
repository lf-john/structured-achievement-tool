"""
Seven Sweeps Quality Gate validator for SAT-compatible JSON scoring.
"""

import json

EXPECTED_SWEEPS = [
    "clarity",
    "observation_hook",
    "problem_resonance",
    "proof_strength",
    "cta_precision",
    "brand_voice",
    "personalization_depth",
]


def check_quality_gate(llm_response: str) -> tuple[bool, dict]:
    """
    Validate LLM JSON output against Seven Sweeps quality gate schema.

    Args:
        llm_response: JSON string from LLM containing quality gate evaluation.

    Returns:
        (overall_pass: bool, result: dict) where overall_pass is from result["overall_pass"]

    Raises:
        ValueError: If JSON is invalid or schema is incomplete.
        AssertionError: If validation rules are violated.
    """
    # Parse JSON
    try:
        result = json.loads(llm_response)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    # Validate overall structure
    if not isinstance(result, dict):
        raise ValueError("Response must be a JSON object")

    # Check required top-level fields
    required_top_level = ["overall_pass", "overall_score", "sweeps", "revised_copy"]
    for field in required_top_level:
        if field not in result:
            raise ValueError(f"Missing required field: {field}")

    # Validate overall_pass is boolean
    if not isinstance(result["overall_pass"], bool):
        raise ValueError("overall_pass must be a boolean")

    # Validate overall_score is integer in range
    if not isinstance(result["overall_score"], int):
        raise ValueError("overall_score must be an integer")
    if not (0 <= result["overall_score"] <= 100):
        raise ValueError("overall_score must be between 0 and 100")

    # Validate revised_copy is string
    if not isinstance(result["revised_copy"], str):
        raise ValueError("revised_copy must be a string")

    # Validate sweeps structure
    if not isinstance(result["sweeps"], dict):
        raise ValueError("sweeps must be an object")

    # Check all required sweeps are present
    for sweep in EXPECTED_SWEEPS:
        if sweep not in result["sweeps"]:
            raise ValueError(f"Missing required sweep: {sweep}")

    # Validate each sweep
    sweep_scores = []
    for sweep in EXPECTED_SWEEPS:
        sweep_data = result["sweeps"][sweep]

        if not isinstance(sweep_data, dict):
            raise ValueError(f"Sweep '{sweep}' must be an object")

        # Check required sweep fields
        required_sweep_fields = ["score", "pass", "issues"]
        for field in required_sweep_fields:
            if field not in sweep_data:
                raise ValueError(f"Sweep '{sweep}' missing required field: {field}")

        # Validate score
        score = sweep_data["score"]
        if not isinstance(score, int):
            raise ValueError(f"Sweep '{sweep}' score must be an integer")
        if not (1 <= score <= 5):
            raise ValueError(f"Sweep '{sweep}' score must be between 1 and 5")
        sweep_scores.append(score)

        # Validate pass boolean
        if not isinstance(sweep_data["pass"], bool):
            raise ValueError(f"Sweep '{sweep}' pass must be a boolean")

        # Validate issues is list
        if not isinstance(sweep_data["issues"], list):
            raise ValueError(f"Sweep '{sweep}' issues must be a list")

        # Validate issues are strings
        for issue in sweep_data["issues"]:
            if not isinstance(issue, str):
                raise ValueError(f"Sweep '{sweep}' issues must contain only strings")

    # Validate scoring logic
    # 1. Each sweep.pass must match score >= 3
    for sweep in EXPECTED_SWEEPS:
        score = result["sweeps"][sweep]["score"]
        pass_value = result["sweeps"][sweep]["pass"]
        expected_pass = score >= 3
        if pass_value != expected_pass:
            raise ValueError(
                f"Sweep '{sweep}' pass={pass_value} but score={score}. "
                f"pass must be {expected_pass}"
            )

    # 2. Calculate the logically correct overall_pass
    # overall_pass must be True only if ALL sweeps >= 3 AND overall_score >= 70
    all_sweeps_pass = all(result["sweeps"][s]["score"] >= 3 for s in EXPECTED_SWEEPS)
    score_passes = result["overall_score"] >= 70
    correct_overall_pass = all_sweeps_pass and score_passes

    # Return the correct overall_pass (not what the LLM claimed)
    return correct_overall_pass, result
