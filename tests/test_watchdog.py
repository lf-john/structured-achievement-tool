"""
Tests for Watchdog — Monitor Watchdog (Phase 2 item 2.6).

Uses tmp_path and mock subprocess throughout.
"""

import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from src.execution.watchdog import Watchdog

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def watchdog(tmp_path):
    """Create a Watchdog with a temp audit directory."""
    audit_dir = str(tmp_path / "audits")
    os.makedirs(audit_dir, exist_ok=True)
    return Watchdog(
        monitor_service="sat-monitor.service",
        daemon_service="sat.service",
        audit_dir=audit_dir,
        audit_max_age=2700,
    )


@pytest.fixture
def fresh_audit_file(tmp_path):
    """Create a recent audit file."""
    audit_dir = tmp_path / "audits"
    audit_dir.mkdir(exist_ok=True)
    audit_file = audit_dir / "audit_20260226_100000.json"
    audit_file.write_text(json.dumps({"status": "ok"}))
    return str(audit_file)


@pytest.fixture
def stale_audit_file(tmp_path):
    """Create an old audit file (> 45 minutes ago)."""
    audit_dir = tmp_path / "audits"
    audit_dir.mkdir(exist_ok=True)
    audit_file = audit_dir / "audit_20260226_080000.json"
    audit_file.write_text(json.dumps({"status": "ok"}))
    # Set mtime to 1 hour ago
    old_time = time.time() - 3600
    os.utime(str(audit_file), (old_time, old_time))
    return str(audit_file)


# ---------------------------------------------------------------------------
# Service Check
# ---------------------------------------------------------------------------


class TestCheckService:
    def test_active_service(self, watchdog):
        """Returns True for active services."""
        mock_result = MagicMock(stdout="active\n")
        with patch("subprocess.run", return_value=mock_result):
            assert watchdog.check_service("sat.service") is True

    def test_inactive_service(self, watchdog):
        """Returns False for inactive services."""
        mock_result = MagicMock(stdout="inactive\n")
        with patch("subprocess.run", return_value=mock_result):
            assert watchdog.check_service("sat.service") is False

    def test_failed_service(self, watchdog):
        """Returns False for failed services."""
        mock_result = MagicMock(stdout="failed\n")
        with patch("subprocess.run", return_value=mock_result):
            assert watchdog.check_service("sat.service") is False

    def test_service_check_timeout(self, watchdog):
        """Returns False on subprocess timeout."""
        import subprocess as sp

        with patch("subprocess.run", side_effect=sp.TimeoutExpired("systemctl", 5)):
            assert watchdog.check_service("sat.service") is False

    def test_service_check_oserror(self, watchdog):
        """Returns False on OSError (e.g., systemctl not found)."""
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert watchdog.check_service("sat.service") is False


# ---------------------------------------------------------------------------
# Audit Freshness
# ---------------------------------------------------------------------------


class TestCheckAuditFreshness:
    def test_fresh_audit(self, watchdog, fresh_audit_file):
        """Returns (True, path) for a recent audit file."""
        is_fresh, path = watchdog.check_audit_freshness()
        assert is_fresh is True
        assert path == fresh_audit_file

    def test_stale_audit(self, watchdog, stale_audit_file):
        """Returns (False, path) for an old audit file."""
        is_fresh, path = watchdog.check_audit_freshness()
        assert is_fresh is False
        assert path == stale_audit_file

    def test_no_audit_dir(self, tmp_path):
        """Returns (False, None) when audit directory does not exist."""
        w = Watchdog(audit_dir=str(tmp_path / "nonexistent"))
        is_fresh, path = w.check_audit_freshness()
        assert is_fresh is False
        assert path is None

    def test_empty_audit_dir(self, watchdog):
        """Returns (False, None) when audit directory is empty."""
        is_fresh, path = watchdog.check_audit_freshness()
        assert is_fresh is False
        assert path is None

    def test_ignores_non_audit_files(self, tmp_path):
        """Skips files that do not match the audit_*.json pattern."""
        audit_dir = tmp_path / "audits"
        audit_dir.mkdir()
        (audit_dir / "random_file.txt").write_text("not an audit")
        (audit_dir / "notes.json").write_text("{}")

        w = Watchdog(audit_dir=str(audit_dir))
        is_fresh, path = w.check_audit_freshness()
        assert is_fresh is False
        assert path is None


# ---------------------------------------------------------------------------
# Alert Sending
# ---------------------------------------------------------------------------


class TestSendAlert:
    def test_sends_curl_command(self, watchdog):
        """send_alert invokes curl with correct args."""
        with patch("subprocess.run") as mock_run:
            watchdog.send_alert("Something broke")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "curl" in cmd
        assert any("SAT Watchdog Alert" in str(a) for a in cmd)
        assert any("Something broke" in str(a) for a in cmd)

    def test_alert_handles_timeout(self, watchdog):
        """send_alert does not raise on timeout."""
        import subprocess as sp

        with patch("subprocess.run", side_effect=sp.TimeoutExpired("curl", 10)):
            # Should not raise
            watchdog.send_alert("test alert")

    def test_alert_handles_oserror(self, watchdog):
        """send_alert does not raise on OSError."""
        with patch("subprocess.run", side_effect=OSError("curl not found")):
            # Should not raise
            watchdog.send_alert("test alert")


# ---------------------------------------------------------------------------
# Full Check Run
# ---------------------------------------------------------------------------


class TestRunChecks:
    def test_all_healthy(self, watchdog, fresh_audit_file):
        """No alerts when all services active and audit fresh."""
        mock_result = MagicMock(stdout="active\n")
        with patch("subprocess.run", return_value=mock_result):
            results = watchdog.run_checks()

        assert results["checks"]["daemon"] is True
        assert results["checks"]["monitor"] is True
        assert results["checks"]["audit_fresh"] is True
        assert len(results["alerts"]) == 0

    def test_daemon_down_restart_succeeds(self, watchdog, fresh_audit_file):
        """Detects down daemon, attempts restart, reports success."""
        call_count = {"n": 0}

        def mock_run(cmd, **kwargs):
            call_count["n"] += 1
            if "is-active" in cmd:
                svc = cmd[-1]
                if svc == "sat.service":
                    # First call: inactive, second call (after restart): active
                    if call_count["n"] <= 2:
                        return MagicMock(stdout="inactive\n")
                    return MagicMock(stdout="active\n")
                return MagicMock(stdout="active\n")
            if "restart" in cmd:
                return MagicMock(returncode=0)
            # curl for alert
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_run), patch("time.sleep"):
            results = watchdog.run_checks()

        assert "sat.service is not active" in results["alerts"]
        assert any("restarted successfully" in r for r in results["restarts"])

    def test_monitor_down_restart_fails(self, watchdog, fresh_audit_file):
        """Detects down monitor, restart fails, alert sent."""

        def mock_run(cmd, **kwargs):
            if "is-active" in cmd:
                svc = cmd[-1]
                if svc == "sat-monitor.service":
                    return MagicMock(stdout="inactive\n")
                return MagicMock(stdout="active\n")
            if "restart" in cmd:
                return MagicMock(returncode=0)
            # curl for alert
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_run), patch("time.sleep"):
            results = watchdog.run_checks()

        assert "sat-monitor.service is not active" in results["alerts"]
        assert any("FAILED" in r for r in results["restarts"])

    def test_stale_audit_alert(self, watchdog, stale_audit_file):
        """Alerts when audit results are stale."""
        mock_active = MagicMock(stdout="active\n")

        def mock_run(cmd, **kwargs):
            if "is-active" in cmd:
                return mock_active
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_run):
            results = watchdog.run_checks()

        assert results["checks"]["audit_fresh"] is False
        assert any("stale" in a for a in results["alerts"])

    def test_no_audit_files_alert(self, tmp_path):
        """Alerts when no audit files exist at all."""
        audit_dir = str(tmp_path / "empty_audits")
        os.makedirs(audit_dir)
        w = Watchdog(audit_dir=audit_dir)

        mock_active = MagicMock(stdout="active\n")

        def mock_run(cmd, **kwargs):
            if "is-active" in cmd:
                return mock_active
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_run):
            results = w.run_checks()

        assert any("No audit results found" in a for a in results["alerts"])


# ---------------------------------------------------------------------------
# Restart Attempt
# ---------------------------------------------------------------------------


class TestAttemptRestart:
    def test_restart_success(self, watchdog):
        """Returns True when service comes back active after restart."""
        call_count = {"n": 0}

        def mock_run(cmd, **kwargs):
            call_count["n"] += 1
            if "restart" in cmd:
                return MagicMock(returncode=0)
            if "is-active" in cmd:
                return MagicMock(stdout="active\n")
            return MagicMock()

        with patch("subprocess.run", side_effect=mock_run), patch("time.sleep"):
            assert watchdog.attempt_restart("sat.service") is True

    def test_restart_failure(self, watchdog):
        """Returns False when service stays inactive after restart."""

        def mock_run(cmd, **kwargs):
            if "restart" in cmd:
                return MagicMock(returncode=0)
            if "is-active" in cmd:
                return MagicMock(stdout="inactive\n")
            return MagicMock()

        with patch("subprocess.run", side_effect=mock_run), patch("time.sleep"):
            assert watchdog.attempt_restart("sat.service") is False

    def test_restart_timeout(self, watchdog):
        """Returns False when restart command times out."""
        import subprocess as sp

        with patch("subprocess.run", side_effect=sp.TimeoutExpired("systemctl", 15)):
            assert watchdog.attempt_restart("sat.service") is False

    def test_restart_oserror(self, watchdog):
        """Returns False when systemctl is not available."""
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert watchdog.attempt_restart("sat.service") is False
