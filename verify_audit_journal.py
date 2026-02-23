import os
import json
from datetime import datetime
from src.execution.audit_journal import AuditJournal, AuditRecord

# Define the path for the test journal
TEST_JOURNAL_PATH = ".memory/test_audit_journal.jsonl"

# Clean up previous test file if it exists
if os.path.exists(TEST_JOURNAL_PATH):
    os.remove(TEST_JOURNAL_PATH)

try:
    # 1. Create a sample AuditRecord
    sample_record = AuditRecord(
        task_file="test_task.md",
        story_id="TS-1",
        story_title="Test Story",
        llm_provider_per_phase={"design": "claude-3-opus"},
        session_id="test-session-123",
        total_turns=5,
        exit_code=0,
        duration_seconds=123.45,
        success=True,
        phases_completed=["design", "code", "verify"],
        error_summary=None
    )

    # 2. Create an AuditJournal instance
    journal = AuditJournal(journal_path=TEST_JOURNAL_PATH)

    # 3. Append the record
    journal.append_record(sample_record)

    # 4. Verify the file content
    if not os.path.exists(TEST_JOURNAL_PATH):
        print("FAIL: Journal file was not created.")
        exit(1)

    with open(TEST_JOURNAL_PATH, "r") as f:
        line = f.readline()
        if not line:
            print("FAIL: Journal file is empty.")
            exit(1)

        data = json.loads(line)
        if data["story_id"] != "TS-1" or data["success"] is not True:
            print(f"FAIL: Data mismatch in journal file. Got: {data}")
            exit(1)

    print("PASS: AuditRecord successfully appended and verified.")

except Exception as e:
    print(f"FAIL: An exception occurred: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

finally:
    # Clean up the test file
    if os.path.exists(TEST_JOURNAL_PATH):
        os.remove(TEST_JOURNAL_PATH)

