"""Tests for dry-run verification with retry feedback."""

from src.execution.dry_run import DryRunVerifier
from src.execution.verification_sdk import VerifyResult

# ---------------------------------------------------------------------------
# Helpers — simple callables that return VerifyResult
# ---------------------------------------------------------------------------


def _pass_check(target: str = "test-target") -> VerifyResult:
    return VerifyResult(passed=True, checker="test", target=target, message="ok")


def _fail_check(target: str = "test-target") -> VerifyResult:
    return VerifyResult(passed=False, checker="test", target=target, message="not ok")


def _raise_check() -> VerifyResult:
    raise RuntimeError("boom")


def _file_exists_pass(path: str) -> VerifyResult:
    return VerifyResult(passed=True, checker="file", target=path, message="file exists")


def _file_exists_fail(path: str) -> VerifyResult:
    return VerifyResult(passed=False, checker="file", target=path, message="path does not exist")


def _port_check_pass(host: str, port: int) -> VerifyResult:
    return VerifyResult(
        passed=True,
        checker="port",
        target=f"{host}:{port}",
        message="port is listening",
    )


def _port_check_fail(host: str, port: int) -> VerifyResult:
    return VerifyResult(
        passed=False,
        checker="port",
        target=f"{host}:{port}",
        message="connection refused",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDryRunVerifier:
    """Core verifier behaviour."""

    def test_dry_run_passes_then_full_run_executes(self):
        """When dry-run passes, the full checks should execute."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_pass_check,)],
            full_checks=[(_pass_check,)],
        )
        assert result.dry_run_passed is True
        assert result.full_run_passed is True
        assert len(result.dry_run_results) == 1
        assert len(result.full_run_results) == 1

    def test_dry_run_fails_skips_full_run(self):
        """When dry-run fails, full checks must not execute."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_fail_check,)],
            full_checks=[(_pass_check,)],
        )
        assert result.dry_run_passed is False
        assert result.full_run_passed is None
        assert len(result.full_run_results) == 0

    def test_dry_run_fails_provides_feedback(self):
        """Feedback string should be populated when dry-run fails."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_fail_check,)],
            full_checks=[],
        )
        assert result.feedback != ""
        assert "1 check(s) failed" in result.feedback

    def test_all_checks_pass(self):
        """Both dry-run and full run pass — result reflects success."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[
                (_pass_check, "a"),
                (_pass_check, "b"),
            ],
            full_checks=[
                (_pass_check, "c"),
            ],
        )
        assert result.dry_run_passed is True
        assert result.full_run_passed is True
        assert result.feedback == ""

    def test_full_run_fails_after_dry_run_passes(self):
        """Dry-run passes but full run fails — both statuses correct."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_pass_check,)],
            full_checks=[(_fail_check,)],
        )
        assert result.dry_run_passed is True
        assert result.full_run_passed is False
        assert "1 check(s) failed" in result.feedback

    def test_empty_dry_run_checks(self):
        """Empty dry-run list is treated as passed (vacuous truth)."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[],
            full_checks=[(_pass_check,)],
        )
        assert result.dry_run_passed is True
        assert result.full_run_passed is True

    def test_empty_full_checks(self):
        """Empty full-checks list is treated as passed (vacuous truth)."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_pass_check,)],
            full_checks=[],
        )
        assert result.dry_run_passed is True
        assert result.full_run_passed is True

    def test_both_check_lists_empty(self):
        """Both lists empty — everything passes."""
        v = DryRunVerifier()
        result = v.run(dry_run_checks=[], full_checks=[])
        assert result.dry_run_passed is True
        assert result.full_run_passed is True
        assert result.feedback == ""

    def test_exception_in_dry_run_check(self):
        """Exception in a check callable is caught and reported as failure."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_raise_check,)],
            full_checks=[(_pass_check,)],
        )
        assert result.dry_run_passed is False
        assert result.full_run_passed is None
        assert "exception" in result.dry_run_results[0].message.lower()

    def test_exception_in_full_run_check(self):
        """Exception during full run is caught; full run marked failed."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_pass_check,)],
            full_checks=[(_raise_check,)],
        )
        assert result.dry_run_passed is True
        assert result.full_run_passed is False
        assert "exception" in result.full_run_results[0].message.lower()

    def test_mixed_pass_fail_in_dry_run(self):
        """One pass and one fail in dry-run — overall dry-run fails."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[
                (_pass_check, "good"),
                (_fail_check, "bad"),
            ],
            full_checks=[(_pass_check,)],
        )
        assert result.dry_run_passed is False
        assert result.full_run_passed is None
        assert len(result.dry_run_results) == 2

    def test_mixed_pass_fail_in_full_run(self):
        """Mixed results in full run — overall full run fails."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_pass_check,)],
            full_checks=[
                (_pass_check, "good"),
                (_fail_check, "bad"),
            ],
        )
        assert result.dry_run_passed is True
        assert result.full_run_passed is False
        assert "1 check(s) failed" in result.feedback

    def test_feedback_includes_checker_and_target(self):
        """Feedback format must include checker name and target."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[
                (_file_exists_fail, "/tmp/missing.txt"),
            ],
            full_checks=[],
        )
        assert "[file]" in result.feedback
        assert "/tmp/missing.txt" in result.feedback
        assert "path does not exist" in result.feedback

    def test_feedback_multiple_failures(self):
        """Feedback lists all failures, numbered."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[
                (_file_exists_fail, "/a"),
                (_file_exists_fail, "/b"),
                (_pass_check,),
            ],
            full_checks=[],
        )
        assert "2 check(s) failed" in result.feedback
        assert "1." in result.feedback
        assert "2." in result.feedback
        assert "/a" in result.feedback
        assert "/b" in result.feedback

    def test_check_with_multiple_args(self):
        """Checks receiving multiple arguments are unpacked correctly."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[
                (_port_check_pass, "localhost", 8080),
            ],
            full_checks=[
                (_port_check_fail, "localhost", 9999),
            ],
        )
        assert result.dry_run_passed is True
        assert result.full_run_passed is False
        assert "localhost:9999" in result.feedback

    def test_retry_count_is_zero(self):
        """DryRunVerifier is stateless; retry_count always 0."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_pass_check,)],
            full_checks=[(_pass_check,)],
        )
        assert result.retry_count == 0

    def test_max_retries_stored(self):
        """max_retries attribute is stored on the verifier."""
        v = DryRunVerifier(max_retries=5)
        assert v.max_retries == 5

    def test_all_dry_run_fail(self):
        """All dry-run checks fail — feedback covers every failure."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[
                (_fail_check, "x"),
                (_fail_check, "y"),
                (_fail_check, "z"),
            ],
            full_checks=[],
        )
        assert result.dry_run_passed is False
        assert "3 check(s) failed" in result.feedback

    def test_feedback_all_pass_returns_all_passed_message(self):
        """_build_feedback with no failures returns 'All checks passed.'"""
        v = DryRunVerifier()
        feedback = v._build_feedback(
            [
                VerifyResult(passed=True, checker="t", target="t", message="ok"),
            ]
        )
        assert feedback == "All checks passed."

    def test_exception_check_target_in_results(self):
        """When a check raises, the resulting VerifyResult has useful details."""
        v = DryRunVerifier()
        result = v.run(
            dry_run_checks=[(_raise_check,)],
            full_checks=[],
        )
        r = result.dry_run_results[0]
        assert r.passed is False
        assert r.checker == "unknown"
        assert "boom" in r.message
        assert "boom" in r.details.get("error", "")
