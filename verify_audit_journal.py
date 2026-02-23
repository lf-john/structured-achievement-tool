import sys
from pathlib import Path
from datetime import datetime
import json
import os

# Add src to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.execution.audit_journal import AuditJournal, AuditRecord

def run_verification():
    try:
        # 1. Create a dummy record
        record = AuditRecord(
            task_file="test.md",
            story_id="test-story",
            story_title="Test Story",
            llm_provider_per_phase={"design": "claude"},
            session_id="test-session",
            total_turns=5,
            exit_code=0,
            duration_seconds=123.45,
            success=True,
            phases_completed=["design", "code"],
            error_summary=None,
        )

        # 2. Append it to a temporary journal file
        journal_path = Path(".memory/test_audit_journal.jsonl")
        if journal_path.exists():
            journal_path.unlink()

        journal = AuditJournal(journal_path=journal_path)
        journal.append_record(record)

        # 3. Read the file and verify its content
        with open(journal_path, "r") as f:
            content = f.read()

        data = json.loads(content)

        # 4. Assert correctness
        assert data['story_id'] == "test-story"
        assert data['success'] is True
        assert content.strip().endswith("}") # check it's a single line json

        print("Verification successful!")
        # Clean up
        if journal_path.exists():
            journal_path.unlink()
        
        return True

    except Exception as e:
        print(f"Verification failed: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    if not run_verification():
        sys.exit(1)
