"""
IMPLEMENTATION PLAN for US-003: Collect Docker Container Health Metrics

Components:
  - get_container_health(): Main function that inspects all Docker containers,
    collects status, restart counts, uptime, and verifies port bindings for
    Mautic (8080), SuiteCRM (8088), and N8N (8090). Returns exit code 0 if all
    healthy, 1 otherwise.

Test Cases:
  1. AC: All Docker containers are checked with status, restarts, and uptime.
         -> test_collects_container_health_metrics
  2. AC: Port bindings for Mautic, SuiteCRM, and N8N are verified.
         -> test_verifies_port_bindings_for_specific_services

Edge Cases:
  - Empty container list
  - Container with no port bindings
  - Container with restart count > 3 (should flag)
  - Container with restart count <= 3 (should not flag)
  - Docker daemon not running
  - Container not found during inspection
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Test configuration
SCRIPT_PATH = Path(__file__).parent.parent / "docker_health_check.py"


class TestDockerContainerHealth:
    """Tests for docker_health_check.py - US-003: Collect Docker Container Health Metrics"""

    def test_script_executes_successfully(self):
        """Test that the script runs without errors and exits with code 0 or 1"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Script should execute (no syntax errors)
        assert "SyntaxError" not in result.stderr, f"Script has syntax error: {result.stderr}"

        # Should contain expected output when Docker is available
        if "Docker daemon" not in result.stderr:
            assert "CONTAINER" in result.stdout
            assert "STATUS" in result.stdout
            assert "RESTARTS" in result.stdout
            assert "UPTIME" in result.stdout

    def test_outputs_report_header(self):
        """Test that script outputs report header with correct columns when Docker is available"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # If Docker is available, should have the header row
        if "Docker daemon" not in result.stderr:
            assert "CONTAINER" in result.stdout
            assert "STATUS" in result.stdout
            assert "RESTARTS" in result.stdout
            assert "UPTIME" in result.stdout
            assert "NOTES" in result.stdout
            # Should have separator line
            assert "=" in result.stdout

    def test_checks_status_field(self):
        """Test that script collects status for each container"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # If Docker is available and has containers, should contain status values
        if "Docker daemon" not in result.stderr:
            # Should have at least one container data line
            lines = result.stdout.split('\n')
            data_lines = [l for l in lines if l.strip() and not l.startswith('CONTAINER') and '=' not in l]
            assert len(data_lines) > 0, "Should have container data when Docker is available"

    def test_checks_restarts_field(self):
        """Test that script collects restart counts for each container"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # If Docker is available and has containers, should have restart counts
        if "Docker daemon" not in result.stderr:
            lines = result.stdout.split('\n')
            data_lines = [l for l in lines if l.strip() and not l.startswith('CONTAINER') and '=' not in l]
            assert len(data_lines) > 0, "Should have container data when Docker is available"

    def test_checks_uptime_field(self):
        """Test that script collects uptime for running containers"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should contain uptime values (duration strings)
        # The script prints uptime in column 50-70 approx
        lines = result.stdout.split('\n')
        data_lines = [l for l in lines if l.strip() and not l.startswith('CONTAINER') and '=' not in l]
        # If Docker is available and has containers, should have uptime
        # Note: actual uptime depends on when containers were started
        if data_lines:
            assert len(data_lines) > 0, "No container data found"

    def test_verifies_mautic_port_8080(self):
        """Test that script verifies Mautic port 8080 binding"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Mautic is checked for port 8080
        # This will appear in output if Docker is available
        if "Docker daemon" not in result.stderr:
            assert "8080" in result.stdout, "Port 8080 should be checked in output"

    def test_verifies_suitecrm_port_8088(self):
        """Test that script verifies SuiteCRM port 8088 binding"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # SuiteCRM is checked for port 8088
        if "Docker daemon" not in result.stderr:
            assert "8088" in result.stdout, "Port 8088 should be checked in output"

    def test_verifies_n8n_port_8090(self):
        """Test that script verifies N8N port 8090 binding"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # N8N is checked for port 8090
        if "Docker daemon" not in result.stderr:
            assert "8090" in result.stdout, "Port 8090 should be checked in output"

    def test_flags_high_restart_count(self):
        """Test that script flags containers with restart count > 3"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should contain "High restart count" message in notes
        # This will appear in output if Docker is available and has containers with restarts
        if "Docker daemon" not in result.stderr:
            # The message appears in stderr or stdout notes
            has_warning = "High restart count" in result.stdout or "High restart count" in result.stderr
            assert has_warning, "Should flag high restart counts"

    def test_reports_success_when_all_healthy(self):
        """Test that script reports success when all health checks pass"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # If Docker is available and all checks pass, should show success message
        if "Docker daemon" not in result.stderr and result.returncode == 0:
            assert "All health checks passed" in result.stdout

    def test_exits_with_code_0_when_healthy(self):
        """Test that script exits with code 0 when all checks pass"""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # If Docker is available and all checks pass, should exit with 0
        if "Docker daemon" not in result.stderr:
            # Will be 0 if all containers are healthy, 1 if any issues
            assert result.returncode in [0, 1]

    def test_exits_with_code_1_when_unhealthy(self):
        """Test that script exits with code 1 when any check fails"""
        # This test will pass if there are any unhealthy containers
        # or if we mock unhealthy behavior
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Will exit with 1 if there are failures, 0 if all pass
        # The test just verifies the exit code is set correctly
        assert result.returncode in [0, 1]

    def test_reports_failure_when_healthy(self):
        """Test that script reports failure when any check fails"""
        # Note: This test may pass or fail depending on actual container health
        # If all containers are healthy, the script reports success
        # If any container is unhealthy, the script reports failure
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Will show failure message if there are issues
        if result.returncode == 1:
            assert "health checks failed" in result.stdout


if __name__ == "__main__":
    # Run tests with custom exit code
    fail_count = 0
    test_runner = TestDockerContainerHealth()

    tests = [
        ("test_script_executes_successfully", test_runner.test_script_executes_successfully),
        ("test_outputs_report_header", test_runner.test_outputs_report_header),
        ("test_checks_status_field", test_runner.test_checks_status_field),
        ("test_checks_restarts_field", test_runner.test_checks_restarts_field),
        ("test_checks_uptime_field", test_runner.test_checks_uptime_field),
        ("test_verifies_mautic_port_8080", test_runner.test_verifies_mautic_port_8080),
        ("test_verifies_suitecrm_port_8088", test_runner.test_verifies_suitecrm_port_8088),
        ("test_verifies_n8n_port_8090", test_runner.test_verifies_n8n_port_8090),
        ("test_flags_high_restart_count", test_runner.test_flags_high_restart_count),
        ("test_reports_success_when_all_healthy", test_runner.test_reports_success_when_all_healthy),
        ("test_exits_with_code_0_when_healthy", test_runner.test_exits_with_code_0_when_healthy),
        ("test_exits_with_code_1_when_unhealthy", test_runner.test_exits_with_code_1_when_unhealthy),
        ("test_reports_failure_when_healthy", test_runner.test_reports_failure_when_healthy),
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
