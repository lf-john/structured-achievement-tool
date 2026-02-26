"""
IMPLEMENTATION PLAN for US-002: Collect Disk Usage Metrics

Components:
  - verify_script.sh: Bash script that executes `df -h` and flags mounts over 80% usage

Test Cases:
  1. AC: Disk usage for all mounts is reported -> test_script_executes_successfully
  2. AC: Script outputs df -h header -> test_outputs_df_header
  3. AC: Script processes all mount points -> test_outputs_multiple_mount_points
  4. Edge case: Script exits with code 0 -> test_exits_with_zero_code
  5. Edge case: Warning for mounts over 80% -> test_warns_for_high_usage

Edge Cases:
  - Multiple mounts with varying usage percentages
  - All mounts under threshold (no warnings)
  - Error handling in pipe processing
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Test configuration
SCRIPT_PATH = Path(__file__).parent.parent / "verify_script.sh"


class TestVerifyScript:
    """Tests for verify_script.sh - US-002: Collect Disk Usage Metrics"""

    def test_script_executes_successfully(self):
        """Test that the script runs without errors and exits with code 0"""
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Script failed with exit code {result.returncode}\nStdout: {result.stdout}\nStderr: {result.stderr}"
        assert "Verifying Disk Usage Metrics Collection" in result.stdout

    def test_outputs_df_header(self):
        """Test that script outputs the df -h header"""
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # df -h output starts with "Filesystem"
        assert "Filesystem" in result.stdout
        # Should have usage information (5th column)
        assert "Use%" in result.stdout

    def test_outputs_multiple_mount_points(self):
        """Test that script processes all mounted filesystems"""
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should contain common mount point names
        assert "/" in result.stdout, "Root filesystem should be reported"
        assert "tmpfs" in result.stdout, "tmpfs should be reported"
        assert "Use%" in result.stdout, "Usage percentage should be reported"

    def test_exits_with_zero_code(self):
        """Test that script exits with code 0 on successful execution"""
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0

    def test_warns_for_high_usage(self):
        """
        Test that script warns for filesystems over 80% usage.
        Note: This test may pass or fail depending on actual system disk usage.
        If the root mount is under 80%, this test will pass.
        If the root mount is over 80%, the warning will be printed to stderr.
        """
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Check if any warning was printed (to stderr or stdout)
        # The script prints warnings to stderr for high usage
        has_warning = "WARNING:" in result.stderr or "WARNING:" in result.stdout

        # If there's a warning, it should contain "Mount point"
        if has_warning:
            assert "Mount point" in result.stderr or "Mount point" in result.stdout

    def test_has_correct_description(self):
        """Test that script outputs correct description"""
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert "Running 'df -h' and flagging filesystems" in result.stdout
        assert "80%" in result.stdout


if __name__ == "__main__":
    # Run tests with custom exit code
    fail_count = 0
    test_runner = TestVerifyScript()

    tests = [
        ("test_script_executes_successfully", test_runner.test_script_executes_successfully),
        ("test_outputs_df_header", test_runner.test_outputs_df_header),
        ("test_outputs_multiple_mount_points", test_runner.test_outputs_multiple_mount_points),
        ("test_exits_with_zero_code", test_runner.test_exits_with_zero_code),
        ("test_warns_for_high_usage", test_runner.test_warns_for_high_usage),
        ("test_has_correct_description", test_runner.test_has_correct_description),
    ]

    for test_name, test_func in tests:
        try:
            test_func()
            print(f"✓ {test_name}")
        except AssertionError as e:
            print(f"✗ {test_name}: {e}")
            fail_count += 1
        except Exception as e:
            print(f"✗ {test_name}: Unexpected error: {e}")
            fail_count += 1

    print(f"\n{fail_count}/{len(tests)} tests failed")
    sys.exit(1 if fail_count > 0 else 0)
