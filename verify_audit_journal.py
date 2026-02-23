import json
import os
from datetime import datetime
from pathlib import Path
import sys

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.execution.audit_journal import AuditJournal, AuditRecord

def run_verification():
    """
    Verifies the AuditJournal functionality.
    Returns True if verification passes, False otherwise.
    """
    test_journal_path = Path(".memory/test_audit_journal.jsonl")
    test_journal_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean up previous test file if it exists
    if test_journal_path.exists():
        test_journal_path.unlink()

    try:
        # 1. Create a sample AuditRecord
        record = AuditRecord(
            task_file="test_task.md",
            story_id="TS-1",
            story_title="Test Story",
            llm_provider_per_phase={"design": "claude-3-opus", "code": "gemini-1.5-pro"},
            session_id="test-session-123",
            total_turns=5,
            exit_code=0,
            duration_seconds=123.45,
            success=True,
            phases_completed=["design", "code", "verify"],
            error_summary=None,
        )

        # 2. Instantiate AuditJournal and append the record
        journal = AuditJournal(journal_path=test_journal_path)
        journal.append_record(record)

        # 3. Verify the file was created and contains the correct data
        if not test_journal_path.exists():
            print("FAIL: Journal file was not created.")
            return False

        with open(test_journal_path, "r") as f:
            line = f.readline()
            if not line:
                print("FAIL: Journal file is empty.")
                return False

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                print("FAIL: Could not decode JSON from journal file.")
                return False

        # 4. Check if the written data matches the original record
        # Pydantic's model_dump_json takes care of serialization details like datetime
        expected_data = json.loads(record.model_dump_json())

        if data["story_id"] != expected_data["story_id"]:
             print(f"FAIL: story_id mismatch. Got {data['story_id']}, expected {expected_data['story_id']}")
             return False

        if data["success"] != expected_data["success"]:
             print(f"FAIL: success mismatch. Got {data['success']}, expected {expected_data['success']}")
             return False

        print("PASS: AuditJournal correctly appended the record as a JSON line.")
        return True

    except Exception as e:
        print(f"An unexpected error occurred during verification: {e}")
        return False
    finally:
        # 5. Clean up the test file
        if test_journal_path.exists():
            test_journal_path.unlink()
            print(f"Cleaned up {test_journal_path}")

if __name__ == "__main__":
    if run_verification():
        sys.exit(0)
    else:
        sys.exit(1)
