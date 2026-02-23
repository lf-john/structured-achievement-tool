
import json
import os
from datetime import datetime
from src.execution.audit_journal import AuditJournal, AuditRecord

def run_verification():
    """
    Verifies that the AuditJournal correctly appends a record
    to the specified journal file.
    """
    journal_path = ".memory/test_audit_journal.jsonl"
    if os.path.exists(journal_path):
        os.remove(journal_path)

    # 1. Create a sample AuditRecord
    record = AuditRecord(
        task_file="test_task.md",
        story_id="TS-1",
        story_title="Test Story",
        llm_provider_per_phase={"design": "claude-3-opus"},
        session_id="test-session-123",
        total_turns=5,
        exit_code=0,
        duration_seconds=123.45,
        success=True,
        phases_completed=["design", "code"],
        error_summary=None
    )

    # 2. Append the record using AuditJournal
    journal = AuditJournal(journal_path=journal_path)
    journal.append_record(record)

    # 3. Verify the file content
    if not os.path.exists(journal_path):
        print("FAIL: Journal file was not created.")
        return False

    with open(journal_path, "r") as f:
        line = f.readline()
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            print(f"FAIL: Could not decode JSON from line: {line}")
            return False

    # 4. Clean up
    os.remove(journal_path)

    # 5. Assertions
    expected_keys = set(AuditRecord.model_fields.keys())
    actual_keys = set(data.keys())

    if actual_keys != expected_keys:
        print(f"FAIL: JSON keys do not match AuditRecord fields.")
        print(f"Expected: {expected_keys}")
        print(f"Actual:   {actual_keys}")
        return False
    
    if data['story_id'] != 'TS-1':
        print(f"FAIL: story_id mismatch. Expected 'TS-1', got '{data['story_id']}'")
        return False

    print("PASS: Audit record successfully written and verified.")
    return True

if __name__ == "__main__":
    if not run_verification():
        exit(1)
