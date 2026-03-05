"""
Tests for SystemAuditor — Layer 2 LLM-powered audit (Phase 2 item 2.5).

Uses tmp_path and mock subprocess throughout.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.execution.audit_cronjob import MaintenanceAuditLog, SystemAuditor

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def maintenance_log(tmp_path):
    """Create a MaintenanceAuditLog writing to a temp directory."""
    log_path = str(tmp_path / "memory" / "maintenance_audit.jsonl")
    return MaintenanceAuditLog(path=log_path)


@pytest.fixture
def auditor(tmp_path, maintenance_log):
    """Create a SystemAuditor with a temp audit directory."""
    audit_dir = str(tmp_path / "audits")
    return SystemAuditor(audit_dir=audit_dir, maintenance_log=maintenance_log)


@pytest.fixture
def task_tree(tmp_path):
    """Create a mock task directory tree with sample task files."""
    task_root = tmp_path / "sat-tasks"
    sub = task_root / "test-project"
    sub.mkdir(parents=True)

    # Recent task (touch now)
    task1 = sub / "001_test.md"
    task1.write_text("<Working>\n# Task 1\nSome content")

    task2 = sub / "002_done.md"
    task2.write_text("<Finished>\n# Task 2\nDone")

    # Response file (should be skipped)
    resp = sub / "001_response.md"
    resp.write_text("<!-- CLAUDE-RESPONSE -->\nResponse content")

    return str(task_root)


# ---------------------------------------------------------------------------
# Input Collection
# ---------------------------------------------------------------------------

class TestCollectInputs:
    def test_collect_returns_all_keys(self, auditor):
        """collect_inputs returns dict with all expected sections."""
        with patch.object(auditor, "_get_recent_tasks", return_value=[]), \
             patch.object(auditor, "_get_system_health", return_value={}), \
             patch.object(auditor, "_get_debug_history", return_value=[]), \
             patch.object(auditor, "_get_service_status", return_value={}):
            inputs = auditor.collect_inputs()

        assert "recent_tasks" in inputs
        assert "system_health" in inputs
        assert "debug_history" in inputs
        assert "service_status" in inputs

    def test_get_system_health_success(self, auditor):
        """System health captures disk and memory output."""
        mock_df = MagicMock(returncode=0, stdout="Filesystem  Size  Used Avail Use%\n/dev/sda1   100G  50G  50G  50%")
        mock_free = MagicMock(returncode=0, stdout="              total   used   free\nMem:          16Gi   8Gi   8Gi")

        def run_side_effect(cmd, **kwargs):
            if "df" in cmd:
                return mock_df
            if "free" in cmd:
                return mock_free
            return MagicMock(returncode=1, stdout="")

        with patch("subprocess.run", side_effect=run_side_effect):
            health = auditor._get_system_health()

        assert "disk" in health
        assert "100G" in health["disk"]
        assert "memory" in health
        assert "16Gi" in health["memory"]

    def test_get_system_health_timeout(self, auditor):
        """System health returns 'unavailable' on timeout."""
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired("df", 5)):
            health = auditor._get_system_health()

        assert health.get("disk") == "unavailable"
        assert health.get("memory") == "unavailable"

    def test_get_service_status_mixed(self, auditor):
        """Service status returns True/False per service."""
        def run_side_effect(cmd, **kwargs):
            svc = cmd[-1]  # service name is last arg
            if svc == "sat.service":
                return MagicMock(stdout="active\n")
            return MagicMock(stdout="inactive\n")

        with patch("subprocess.run", side_effect=run_side_effect):
            status = auditor._get_service_status()

        assert status["sat.service"] is True
        assert status["sat-monitor.service"] is False
        assert status["ollama.service"] is False

    def test_get_recent_tasks(self, auditor, task_tree):
        """Recent tasks finds modified task files, skips response files."""
        with patch.object(
            type(auditor), "_get_recent_tasks",
            wraps=auditor._get_recent_tasks,
        ):
            # Temporarily override TASK_DIRS
            import src.execution.audit_cronjob as mod
            orig = mod.TASK_DIRS
            mod.TASK_DIRS = [task_tree]
            try:
                recent = auditor._get_recent_tasks(hours=1)
            finally:
                mod.TASK_DIRS = orig

        # Should find task files but not response files
        filenames = [t["file"] for t in recent]
        assert any("001_test.md" in f for f in filenames)
        assert any("002_done.md" in f for f in filenames)
        assert not any("response" in f for f in filenames)

    def test_get_debug_history_no_file(self, auditor):
        """Debug history returns empty list when no budget file exists."""
        with patch("os.path.exists", return_value=False):
            result = auditor._get_debug_history()
        assert result == []

    def test_get_debug_history_with_data(self, auditor, tmp_path):
        """Debug history parses budget manager JSON."""
        budget_file = tmp_path / "debug_budget.json"
        budget_file.write_text(json.dumps({
            "task_001": {"attempts": 3, "last_attempt": "2026-02-25T12:00:00"},
            "task_002": {"attempts": 1, "last_attempt": "2026-02-25T13:00:00"},
        }))

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=lambda *a, **kw: open(str(budget_file), *a[1:], **kw)):
            # Simpler approach: just test with a real file path
            pass

        # Direct test with patched file path
        auditor_mod = auditor
        import src.execution.audit_cronjob as mod
        with patch.object(mod.os.path, "exists", return_value=True), \
             patch("builtins.open", return_value=open(str(budget_file))):
            result = auditor_mod._get_debug_history()

        assert len(result) == 2
        assert "task_001" in result[0]
        assert "attempts=3" in result[0]


# ---------------------------------------------------------------------------
# Prompt Construction
# ---------------------------------------------------------------------------

class TestBuildAuditPrompt:
    def test_prompt_includes_service_status(self, auditor):
        """Prompt includes service status section."""
        inputs = {
            "service_status": {"sat.service": True, "ollama.service": False},
            "system_health": {"disk": "50% used", "memory": "8G free"},
            "recent_tasks": [],
            "debug_history": [],
        }
        prompt = auditor.build_audit_prompt(inputs)

        assert "Service Status" in prompt
        assert "sat.service" in prompt
        assert "active" in prompt
        assert "INACTIVE" in prompt

    def test_prompt_includes_system_health(self, auditor):
        """Prompt includes disk and memory info."""
        inputs = {
            "service_status": {},
            "system_health": {"disk": "50% used", "memory": "8G free"},
            "recent_tasks": [],
            "debug_history": [],
        }
        prompt = auditor.build_audit_prompt(inputs)

        assert "System Health" in prompt
        assert "50% used" in prompt
        assert "8G free" in prompt

    def test_prompt_includes_recent_tasks(self, auditor):
        """Prompt includes recent task entries."""
        inputs = {
            "service_status": {},
            "system_health": {},
            "recent_tasks": [
                {"file": "project/001.md", "status": "<Working>"},
            ],
            "debug_history": [],
        }
        prompt = auditor.build_audit_prompt(inputs)

        assert "Recent Tasks" in prompt
        assert "project/001.md" in prompt
        assert "<Working>" in prompt

    def test_prompt_includes_json_instructions(self, auditor):
        """Prompt asks LLM to respond with JSON containing status/issues/recommendations."""
        inputs = {
            "service_status": {},
            "system_health": {},
            "recent_tasks": [],
            "debug_history": [],
        }
        prompt = auditor.build_audit_prompt(inputs)

        assert '"status"' in prompt
        assert '"issues"' in prompt
        assert '"recommendations"' in prompt
        assert "JSON" in prompt

    def test_prompt_no_recent_activity(self, auditor):
        """Prompt handles empty recent tasks gracefully."""
        inputs = {
            "service_status": {},
            "system_health": {},
            "recent_tasks": [],
            "debug_history": [],
        }
        prompt = auditor.build_audit_prompt(inputs)
        assert "No recent task activity" in prompt


# ---------------------------------------------------------------------------
# Response Parsing
# ---------------------------------------------------------------------------

class TestParseAuditResponse:
    def test_parse_ok_response(self, auditor):
        """Parses a clean 'ok' JSON response."""
        response = json.dumps({
            "status": "ok",
            "issues": [],
            "recommendations": ["Keep monitoring"],
        })
        result = auditor.parse_audit_response(response)

        assert result["status"] == "ok"
        assert result["issues"] == []
        assert "Keep monitoring" in result["recommendations"]

    def test_parse_warning_response(self, auditor):
        """Parses a 'warning' response with issues."""
        response = json.dumps({
            "status": "warning",
            "issues": ["Disk usage at 85%"],
            "recommendations": ["Clean up logs"],
        })
        result = auditor.parse_audit_response(response)

        assert result["status"] == "warning"
        assert len(result["issues"]) == 1
        assert "Disk usage" in result["issues"][0]

    def test_parse_critical_response(self, auditor):
        """Parses a 'critical' response."""
        response = json.dumps({
            "status": "critical",
            "issues": ["SAT daemon down", "Ollama unresponsive"],
            "recommendations": ["Restart services immediately"],
        })
        result = auditor.parse_audit_response(response)

        assert result["status"] == "critical"
        assert len(result["issues"]) == 2

    def test_parse_markdown_wrapped_json(self, auditor):
        """Handles LLM responses wrapped in markdown code blocks."""
        response = '```json\n{"status": "ok", "issues": [], "recommendations": []}\n```'
        result = auditor.parse_audit_response(response)
        assert result["status"] == "ok"

    def test_parse_invalid_json(self, auditor):
        """Returns warning status for unparseable responses."""
        result = auditor.parse_audit_response("This is not JSON at all")
        assert result["status"] == "warning"
        assert len(result["issues"]) > 0

    def test_parse_empty_response(self, auditor):
        """Returns ok for empty/None responses."""
        assert auditor.parse_audit_response("")["status"] == "ok"
        assert auditor.parse_audit_response(None)["status"] == "ok"

    def test_parse_invalid_status_value(self, auditor):
        """Coerces unknown status values to 'warning'."""
        response = json.dumps({
            "status": "banana",
            "issues": ["something"],
            "recommendations": [],
        })
        result = auditor.parse_audit_response(response)
        assert result["status"] == "warning"


# ---------------------------------------------------------------------------
# Audit Result Saving
# ---------------------------------------------------------------------------

class TestSaveAuditResult:
    def test_save_creates_file(self, auditor, tmp_path):
        """save_audit_result creates a JSON file with correct content."""
        result = {
            "status": "ok",
            "issues": [],
            "recommendations": ["All good"],
            "timestamp": "2026-02-26T10:00:00",
        }
        filepath = auditor.save_audit_result(result)

        assert os.path.exists(filepath)
        assert filepath.endswith(".json")
        assert filepath.startswith(auditor.audit_dir)

        with open(filepath) as f:
            saved = json.load(f)
        assert saved["status"] == "ok"
        assert saved["timestamp"] == "2026-02-26T10:00:00"

    def test_save_creates_directory(self, tmp_path):
        """save_audit_result creates the audit directory if missing."""
        deep_dir = str(tmp_path / "deep" / "nested" / "audits")
        aud = SystemAuditor(audit_dir=deep_dir)
        result = {"status": "ok", "issues": [], "recommendations": []}
        filepath = aud.save_audit_result(result)
        assert os.path.exists(filepath)


# ---------------------------------------------------------------------------
# Notification Logic
# ---------------------------------------------------------------------------

class TestSendNotification:
    def test_no_notification_for_ok(self, auditor):
        """No notification sent when status is ok."""
        with patch("subprocess.run") as mock_run:
            auditor.send_notification({"status": "ok", "issues": [], "recommendations": []})
        mock_run.assert_not_called()

    def test_notification_for_warning(self, auditor):
        """Notification sent for warning status."""
        with patch("subprocess.run") as mock_run:
            auditor.send_notification({
                "status": "warning",
                "issues": ["Disk at 85%"],
                "recommendations": ["Clean logs"],
            })
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "curl" in cmd
        assert any("high" in str(a) for a in cmd)

    def test_notification_for_critical(self, auditor):
        """Critical uses urgent priority."""
        with patch("subprocess.run") as mock_run:
            auditor.send_notification({
                "status": "critical",
                "issues": ["Everything is on fire"],
                "recommendations": [],
            })
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert any("urgent" in str(a) for a in cmd)

    def test_notification_handles_timeout(self, auditor):
        """Notification does not raise on timeout."""
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired("curl", 10)):
            # Should not raise
            auditor.send_notification({
                "status": "warning",
                "issues": ["test"],
                "recommendations": [],
            })


# ---------------------------------------------------------------------------
# Full Audit Cycle
# ---------------------------------------------------------------------------

class TestRunAudit:
    def test_run_audit_returns_result(self, auditor):
        """run_audit returns a dict with status, issues, recommendations, and timestamp."""
        llm_response = json.dumps({
            "status": "ok",
            "issues": [],
            "recommendations": ["All systems nominal"],
        })
        with patch.object(auditor, "collect_inputs", return_value={
            "recent_tasks": [],
            "system_health": {},
            "debug_history": [],
            "service_status": {"sat.service": True},
        }), patch.object(auditor, "_invoke_llm", return_value=llm_response):
            result = auditor.run_audit()

        assert result["status"] == "ok"
        assert "timestamp" in result
        assert "inputs" in result
        assert result["llm_response_raw"] == llm_response

    def test_run_audit_handles_llm_failure(self, auditor):
        """run_audit handles empty LLM response gracefully."""
        with patch.object(auditor, "collect_inputs", return_value={
            "recent_tasks": [],
            "system_health": {},
            "debug_history": [],
            "service_status": {},
        }), patch.object(auditor, "_invoke_llm", return_value=""):
            result = auditor.run_audit()

        # Empty response parses as "ok" (default)
        assert result["status"] == "ok"

    def test_run_audit_writes_audit_log_entries(self, auditor, maintenance_log):
        """run_audit writes audit_started and llm_response_received entries."""
        llm_response = json.dumps({
            "status": "ok",
            "issues": [],
            "recommendations": [],
        })
        with patch.object(auditor, "collect_inputs", return_value={
            "recent_tasks": [],
            "system_health": {},
            "debug_history": [],
            "service_status": {},
        }), patch.object(auditor, "_invoke_llm", return_value=llm_response):
            auditor.run_audit()

        with open(maintenance_log.path) as f:
            entries = [json.loads(line) for line in f]

        actions = [e["action"] for e in entries]
        assert "audit_started" in actions
        assert "llm_response_received" in actions
        # No issues, so issues_detected should NOT be present
        assert "issues_detected" not in actions

        # Check the response hash is a valid SHA-256 hex string
        resp_entry = next(e for e in entries if e["action"] == "llm_response_received")
        assert len(resp_entry["llm_response_hash"]) == 64

    def test_run_audit_logs_issues_when_present(self, auditor, maintenance_log):
        """run_audit writes issues_detected entry when LLM reports issues."""
        llm_response = json.dumps({
            "status": "warning",
            "issues": ["Disk at 90%", "Ollama slow"],
            "recommendations": [],
        })
        with patch.object(auditor, "collect_inputs", return_value={
            "recent_tasks": [],
            "system_health": {},
            "debug_history": [],
            "service_status": {},
        }), patch.object(auditor, "_invoke_llm", return_value=llm_response):
            auditor.run_audit()

        with open(maintenance_log.path) as f:
            entries = [json.loads(line) for line in f]

        issues_entry = next(e for e in entries if e["action"] == "issues_detected")
        assert "Disk at 90%" in issues_entry["details"]["issues"]
        assert "Ollama slow" in issues_entry["details"]["issues"]

    def test_send_notification_writes_audit_log(self, auditor, maintenance_log):
        """send_notification writes notification_sent entry for non-ok status."""
        with patch("subprocess.run"):
            auditor.send_notification({
                "status": "warning",
                "issues": ["test issue"],
                "recommendations": [],
            })

        with open(maintenance_log.path) as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 1
        assert entries[0]["action"] == "notification_sent"
        assert entries[0]["details"]["status"] == "warning"
        assert entries[0]["details"]["issue_count"] == 1


# ---------------------------------------------------------------------------
# MaintenanceAuditLog
# ---------------------------------------------------------------------------

class TestMaintenanceAuditLog:
    def test_write_creates_jsonl_entry(self, maintenance_log):
        """write() appends a valid JSONL line."""
        maintenance_log.write("test_source", "test_action", {"key": "value"})

        with open(maintenance_log.path) as f:
            lines = f.readlines()

        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["source"] == "test_source"
        assert entry["action"] == "test_action"
        assert entry["details"]["key"] == "value"
        assert "timestamp" in entry

    def test_write_multiple_entries(self, maintenance_log):
        """Multiple writes append separate lines."""
        maintenance_log.write("s1", "a1")
        maintenance_log.write("s2", "a2")
        maintenance_log.write("s3", "a3")

        with open(maintenance_log.path) as f:
            lines = f.readlines()
        assert len(lines) == 3

    def test_write_with_response_hash(self, maintenance_log):
        """write() stores llm_response_hash when provided."""
        h = MaintenanceAuditLog.hash_response("hello world")
        maintenance_log.write("src", "act", llm_response_hash=h)

        with open(maintenance_log.path) as f:
            entry = json.loads(f.readline())
        assert entry["llm_response_hash"] == h
        assert len(h) == 64

    def test_hash_response_deterministic(self):
        """hash_response produces the same hash for the same input."""
        h1 = MaintenanceAuditLog.hash_response("test input")
        h2 = MaintenanceAuditLog.hash_response("test input")
        assert h1 == h2

    def test_hash_response_different_inputs(self):
        """hash_response produces different hashes for different inputs."""
        h1 = MaintenanceAuditLog.hash_response("input a")
        h2 = MaintenanceAuditLog.hash_response("input b")
        assert h1 != h2

    def test_rotation_when_exceeding_max_bytes(self, tmp_path):
        """Log file is rotated when it exceeds max_bytes."""
        log_path = str(tmp_path / "mem" / "audit.jsonl")
        log = MaintenanceAuditLog(path=log_path, max_bytes=100)

        # Write enough data to exceed 100 bytes
        for i in range(10):
            log.write("src", f"action_{i}", {"data": "x" * 20})

        # After rotation, the backup file should exist
        backup_path = log_path + ".1"
        assert os.path.exists(backup_path)
        # The backup should contain data (it was the old log before rotation)
        assert os.path.getsize(backup_path) > 0
        # Both files should exist and contain valid JSONL
        with open(backup_path) as f:
            for line in f:
                json.loads(line)  # should not raise

    def test_rotation_keeps_one_backup(self, tmp_path):
        """Rotation overwrites older backup, keeping only 1."""
        log_path = str(tmp_path / "mem" / "audit.jsonl")
        log = MaintenanceAuditLog(path=log_path, max_bytes=50)

        # Trigger multiple rotations
        for i in range(30):
            log.write("src", f"action_{i}", {"d": "x" * 20})

        backup = log_path + ".1"
        assert os.path.exists(backup)
        # No .2 backup
        assert not os.path.exists(log_path + ".2")
