"""Dry-run verification with retry feedback.

Runs verification checks in a non-destructive mode first. If the dry-run
fails, provides feedback to the LLM for correction before the real run.
"""

import logging
from dataclasses import dataclass, field

from src.execution.verification_sdk import VerifyResult

logger = logging.getLogger(__name__)


@dataclass
class DryRunResult:
    """Result of a dry-run verification cycle."""
    dry_run_passed: bool
    full_run_passed: bool | None  # None if dry-run failed and no full run happened
    dry_run_results: list[VerifyResult] = field(default_factory=list)
    full_run_results: list[VerifyResult] = field(default_factory=list)
    retry_count: int = 0
    feedback: str = ""  # Summary of what failed (for LLM consumption)


class DryRunVerifier:
    """Executes verification checks with a dry-run/smoke-test first.

    Flow:
    1. Run all checks in dry-run mode (lightweight, non-destructive subset)
    2. If dry-run passes, run full verification
    3. If dry-run fails, return failure feedback without running full verification
    4. Caller can retry with corrected code, up to max_retries
    """

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def run(
        self,
        dry_run_checks: list[tuple],  # [(checker_method, *args), ...]
        full_checks: list[tuple],     # [(checker_method, *args), ...]
    ) -> DryRunResult:
        """Execute dry-run then full verification.

        Args:
            dry_run_checks: Lightweight checks to run first (e.g., file exists,
                syntax valid)
            full_checks: Full verification checks (e.g., port listening, service
                healthy)

        Returns:
            DryRunResult with pass/fail status and feedback
        """
        dry_run_results = self._execute_checks(dry_run_checks)
        dry_run_passed = all(r.passed for r in dry_run_results)

        # When there are no dry-run checks, treat as passed (vacuous truth)
        if not dry_run_checks:
            dry_run_passed = True

        if not dry_run_passed:
            feedback = self._build_feedback(dry_run_results)
            logger.info(
                "Dry-run failed (%d/%d checks passed), skipping full run",
                sum(1 for r in dry_run_results if r.passed),
                len(dry_run_results),
            )
            return DryRunResult(
                dry_run_passed=False,
                full_run_passed=None,
                dry_run_results=dry_run_results,
                full_run_results=[],
                retry_count=0,
                feedback=feedback,
            )

        # Dry-run passed; proceed to full checks
        logger.info("Dry-run passed (%d checks), running full verification", len(dry_run_results))
        full_run_results = self._execute_checks(full_checks)
        full_run_passed = all(r.passed for r in full_run_results)

        # When there are no full checks, treat as passed (vacuous truth)
        if not full_checks:
            full_run_passed = True

        feedback = ""
        if not full_run_passed:
            feedback = self._build_feedback(full_run_results)
            logger.info(
                "Full verification failed (%d/%d checks passed)",
                sum(1 for r in full_run_results if r.passed),
                len(full_run_results),
            )

        return DryRunResult(
            dry_run_passed=True,
            full_run_passed=full_run_passed,
            dry_run_results=dry_run_results,
            full_run_results=full_run_results,
            retry_count=0,
            feedback=feedback,
        )

    def _execute_checks(self, checks: list[tuple]) -> list[VerifyResult]:
        """Run a list of checks, catching exceptions."""
        results: list[VerifyResult] = []
        for entry in checks:
            method = entry[0]
            args = entry[1:]
            try:
                result = method(*args)
                results.append(result)
            except Exception as e:
                method_name = getattr(method, "__name__", str(method))
                logger.error(
                    "Check %s raised exception: %s", method_name, e
                )
                results.append(VerifyResult(
                    passed=False,
                    checker="unknown",
                    target=str(args) if args else method_name,
                    message=f"check raised exception: {e}",
                    details={"error": str(e), "method": method_name},
                ))
        return results

    def _build_feedback(self, results: list[VerifyResult]) -> str:
        """Build human-readable feedback from failed checks.

        Produces a structured summary suitable for LLM consumption, listing
        each failed check with its checker type, target, and failure message.
        """
        failures = [r for r in results if not r.passed]
        if not failures:
            return "All checks passed."

        lines = [f"{len(failures)} check(s) failed:"]
        for i, f in enumerate(failures, 1):
            lines.append(f"  {i}. [{f.checker}] {f.target} -- {f.message}")

        return "\n".join(lines)
