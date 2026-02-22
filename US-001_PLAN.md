# Execution Plan: US-001 - Create End-to-End Integration Test for Full SAT Loop

**Story ID:** US-001
**Phase:** PLAN
**Created:** 2026-02-22
**Engineer:** Senior Systems Engineer and Architect

---

## Executive Summary

This plan outlines the creation of a comprehensive end-to-end integration test that validates the complete SAT (Structured Achievement Tool) workflow. The test will verify the entire loop from task file creation through daemon detection, orchestrator processing, classification, decomposition, and response generation.

**Risk Level:** LOW
**Production Impact:** NONE (test-only changes)
**Estimated Duration:** 60-90 minutes implementation + verification

---

## 1. System Analysis

### 1.1 Current System State

The SAT system currently consists of:
- **Daemon** (`src/daemon.py`): Monitors inbox directory for task files
- **Orchestrator** (`src/orchestrator.py`): LangGraph-based workflow engine
- **StoryAgent** (`src/core/story_agent.py`): Handles classification and decomposition
- **PhaseRunner**: Executes CLI phases (PLAN, EXECUTE, VERIFY)
- **LogicCore** (`src/core/logic_core.py`): Core business logic

### 1.2 Components Requiring Integration

```
User → Task File (<User>) → Daemon (detects) → <Working> marker
                                ↓
                         Orchestrator (process)
                                ↓
                    ┌───────────┴────────────┐
                    ↓                        ↓
              StoryAgent               PhaseRunner
           (classify/decompose)      (PLAN/EXEC/VERIFY)
                    ↓                        ↓
                    └───────────┬────────────┘
                                ↓
                    Response File + <Finished>
```

### 1.3 Test Scope

**In Scope:**
- File system operations (real, not mocked)
- Daemon file detection
- Marker state transitions
- Orchestrator workflow execution
- Classification accuracy
- Decomposition structure validation
- Response file generation
- Complete loop timing (<60s)

**Out of Scope:**
- Network operations
- External API calls
- Database interactions
- Production file system modifications

### 1.4 Dependencies

**Existing (No Changes Needed):**
- pytest (installed)
- asyncio (stdlib)
- pathlib (stdlib)
- tempfile (stdlib)
- threading (stdlib)

**No New Dependencies Required**

---

## 2. Execution Steps

### 2.1 File Creation

#### File: `tests/test_US_001_full_loop_integration.py`

**Purpose:** Comprehensive integration test for full SAT loop

**Structure:**
```python
import pytest
import asyncio
import tempfile
import threading
import time
from pathlib import Path
from src.daemon import Daemon
from src.orchestrator import LangGraphOrchestrator
from src.core.story_agent import StoryAgent

class TestFullLoopIntegration:
    """End-to-end integration test for complete SAT workflow"""

    @pytest.fixture
    def test_env(self):
        """Setup isolated test environment"""
        # Create temporary directory structure
        # Initialize test files
        # Yield paths
        # Cleanup on teardown

    @pytest.mark.asyncio
    async def test_full_sat_loop(self, test_env):
        """
        Validates all 9 acceptance criteria:
        AC1: Creates task file with <User> marker
        AC2: Daemon detects and changes to <Working>
        AC3: Orchestrator classifies task correctly
        AC4: Orchestrator decomposes to PRD structure
        AC5: Response file written with proper formatting
        AC6: Final marker changes to <Finished>
        AC7: Runs in isolated environment
        AC8: Completes in <60 seconds
        AC9: 100% success rate (all assertions pass)
        """
        # Test implementation
```

**Key Components:**

1. **Test Fixture: `test_env`**
   ```python
   @pytest.fixture
   def test_env(self):
       with tempfile.TemporaryDirectory() as tmpdir:
           test_path = Path(tmpdir)
           inbox_path = test_path / "inbox"
           inbox_path.mkdir()

           task_file = inbox_path / "US-999_test_task.md"
           task_file.write_text("# <User>\nTest task content\n")

           yield {
               'root': test_path,
               'inbox': inbox_path,
               'task_file': task_file
           }
           # Automatic cleanup via context manager
   ```

2. **Daemon Thread Management**
   ```python
   daemon = Daemon(inbox_path=test_env['inbox'])
   daemon_thread = threading.Thread(target=daemon.run, daemon=True)
   daemon_thread.start()
   ```

3. **Marker Monitoring**
   ```python
   def wait_for_marker(file_path, expected_marker, timeout=10):
       start = time.time()
       while time.time() - start < timeout:
           content = file_path.read_text()
           if expected_marker in content:
               return True
           time.sleep(0.1)
       return False
   ```

4. **Orchestrator Execution**
   ```python
   orchestrator = LangGraphOrchestrator(
       project_path=test_env['root']
   )
   result = await orchestrator.process_task(test_env['task_file'])
   ```

5. **Assertions**
   ```python
   # AC1: Task file created with <User>
   assert test_env['task_file'].exists()
   assert '<User>' in test_env['task_file'].read_text()

   # AC2: Daemon changes to <Working>
   assert wait_for_marker(test_env['task_file'], '<Working>', timeout=5)

   # AC3-6: Orchestrator processing
   # ... (classification, decomposition, response, <Finished>)

   # AC8: Timing constraint
   assert elapsed_time < 60.0

   # AC9: Implicit (all assertions passed)
   ```

### 2.2 Implementation Checklist

- [ ] Create `tests/test_US_001_full_loop_integration.py`
- [ ] Implement `test_env` fixture
- [ ] Implement helper functions (marker monitoring, file validation)
- [ ] Implement main test method `test_full_sat_loop`
- [ ] Add timeout handling
- [ ] Add comprehensive assertions for all ACs
- [ ] Test cleanup logic
- [ ] Create verification script (✓ COMPLETE)

### 2.3 Commands to Execute

```bash
# 1. Make verification script executable (DONE)
chmod +x verify_script.sh

# 2. Run verification (after test file created)
./verify_script.sh

# 3. Alternative: Direct pytest execution
pytest tests/test_US_001_full_loop_integration.py -v --tb=short -s
```

---

## 3. Verification Strategy

### 3.1 Automated Verification

**Script:** `verify_script.sh` (✓ Created and executable)

**Location:** `/home/johnlane/projects/structured-achievement-tool/verify_script.sh`

**What It Does:**
1. Checks pytest availability
2. Verifies test file exists
3. Runs test with 90-second timeout (buffer over 60s requirement)
4. Reports success/failure with clear messaging
5. Returns exit code 0 on success, 1 on failure

**Usage:**
```bash
./verify_script.sh
```

### 3.2 Success Criteria

The test passes if ALL of the following are true:

✓ Task file created in temporary directory
✓ Initial marker is `<User>`
✓ Daemon detects file within 5 seconds
✓ Marker changes to `<Working>`
✓ Orchestrator classifies task (output validated)
✓ Orchestrator decomposes to PRD structure (schema validated)
✓ Response file exists with proper formatting
✓ Final marker is `<Finished>`
✓ Total execution time < 60 seconds
✓ No exceptions raised
✓ Temporary directory cleaned up

### 3.3 Verification Phases

**Phase 1: Pre-Test Validation**
- Verify test file exists
- Check dependencies available
- Confirm pytest installed

**Phase 2: Test Execution**
- Run integration test
- Monitor for timeout (90s max)
- Capture output/errors

**Phase 3: Result Validation**
- Check exit code (0 = success)
- Parse pytest output
- Verify all assertions passed

**Phase 4: Post-Test Cleanup**
- Confirm temp directories removed
- Check for leaked resources
- Validate production unchanged

---

## 4. Rollback Plan

### 4.1 Failure Scenarios

| Scenario | Detection | Rollback Action |
|----------|-----------|----------------|
| Test file syntax error | Pytest import failure | `rm tests/test_US_001_full_loop_integration.py` |
| Timeout exceeded | Script exit code 124 | Investigate component performance |
| Assertion failure | Pytest output shows failure | Debug failing component |
| Temp directory leak | Manual inspection | `rm -rf /tmp/sat_test_*` |
| Production file corruption | File system check | Restore from git |

### 4.2 Rollback Commands

```bash
# Remove test file if problematic
rm tests/test_US_001_full_loop_integration.py

# Remove verification script
rm verify_script.sh

# Clean any leaked temporary directories
rm -rf /tmp/sat_test_*
rm -rf /tmp/tmp*sat*

# Reset git state (if needed)
git checkout tests/
git clean -fd tests/
```

### 4.3 Safety Measures

**Isolation Guarantees:**
- Test uses `tempfile.TemporaryDirectory()` with automatic cleanup
- No production paths hardcoded
- Daemon configured to watch test inbox only
- All file operations scoped to temporary directory

**Resource Management:**
- Daemon thread set as daemon=True (auto-terminates)
- Fixtures use context managers for cleanup
- Timeout prevents infinite hangs
- No persistent state modifications

**Validation:**
- Pre-test: Verify test environment isolated
- During test: Monitor resource usage
- Post-test: Confirm cleanup occurred
- Always: Check production files unchanged

---

## 5. Implementation Timeline

### Phase 1: Setup (10 minutes)
- [x] Create verification script
- [x] Make script executable
- [ ] Review existing daemon/orchestrator code

### Phase 2: Test Development (40 minutes)
- [ ] Create test file skeleton
- [ ] Implement test fixture
- [ ] Implement helper functions
- [ ] Implement main test logic
- [ ] Add comprehensive assertions

### Phase 3: Testing & Refinement (20 minutes)
- [ ] Run initial test
- [ ] Debug any failures
- [ ] Optimize timing/polling intervals
- [ ] Verify cleanup works

### Phase 4: Verification (10 minutes)
- [ ] Run verification script
- [ ] Validate all ACs met
- [ ] Document any edge cases
- [ ] Mark story as complete

**Total Estimated Time:** 80 minutes

---

## 6. Technical Considerations

### 6.1 Timing Constraints

**60-Second Requirement:**
- Daemon detection: ~1-2 seconds
- Orchestrator startup: ~2-3 seconds
- Classification: ~5-10 seconds
- Decomposition: ~10-15 seconds
- Response generation: ~10-15 seconds
- Marker updates: ~1-2 seconds
- **Buffer:** ~15-20 seconds

**Mitigation Strategies:**
- Use asyncio for concurrent operations
- Optimize polling intervals (100ms)
- Mock slow external calls if needed
- Cache LLM responses in test mode

### 6.2 Marker State Machine

```
<User> ──daemon──> <Working> ──orchestrator──> <Finished>
  ^                    │                            │
  │                    │                            │
  │                    └──(error)──> <Failed>       │
  │                                                  │
  └──────────────────────────────────────────────────┘
```

### 6.3 File Format Validation

**Task File:**
```markdown
# <User>
## Story
US-999: Test story description

## Acceptance Criteria
- AC1: Test criterion
```

**Response File:**
```markdown
# <Finished>
## Classification
Type: feature/bug/research
Complexity: low/medium/high

## Decomposition
[PRD structure validated]

## Execution Plan
[Steps and verification]
```

### 6.4 Error Handling

**Expected Errors:**
- Timeout: Test takes >60 seconds → FAIL
- Daemon not detecting: Polling timeout → FAIL
- Classification fails: LLM error → FAIL
- Decomposition invalid: Schema validation → FAIL
- Response missing: File not created → FAIL

**Unexpected Errors:**
- Permission denied → Check temp dir permissions
- Out of memory → Reduce buffer sizes
- Process killed → Check system resources

---

## 7. Acceptance Criteria Mapping

| AC | Validation Method | Assertion |
|----|-------------------|-----------|
| AC1 | File exists with marker | `assert '<User>' in content` |
| AC2 | Marker change detected | `assert wait_for_marker(..., '<Working>')` |
| AC3 | Classification output | `assert 'Type:' in result['classification']` |
| AC4 | PRD structure | `assert validate_prd_schema(result['prd'])` |
| AC5 | Response file | `assert response_file.exists()` |
| AC6 | Final marker | `assert '<Finished>' in response_content` |
| AC7 | Isolated environment | `assert str(test_path).startswith('/tmp')` |
| AC8 | Timing | `assert elapsed_time < 60.0` |
| AC9 | Success rate | Implicit (all assertions pass) |

---

## 8. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Test flakiness | Medium | High | Add retries, increase timeouts |
| Daemon race condition | Low | Medium | Use robust polling with backoff |
| LLM timeout | Medium | High | Mock LLM calls or use cached responses |
| Temp dir cleanup failure | Low | Low | Explicit cleanup in finally block |
| Production file corruption | Very Low | Critical | Verify isolation before test run |

---

## 9. Success Metrics

### Quantitative
- Test passes: 100% (all assertions)
- Execution time: <60 seconds
- Cleanup rate: 100% (no leaked files)
- Flakiness: 0% (deterministic results)

### Qualitative
- Test provides clear failure messages
- Easy to debug when failing
- Comprehensive coverage of workflow
- Serves as documentation for full loop

---

## 10. Next Steps

1. **Immediate:**
   - Create test file: `tests/test_US_001_full_loop_integration.py`
   - Implement test logic per this plan
   - Run verification script

2. **After Success:**
   - Document any timing optimizations discovered
   - Update project patterns with test insights
   - Consider creating similar tests for error paths

3. **Future Enhancements:**
   - Parameterized tests for different task types
   - Performance benchmarking
   - Parallel execution testing
   - Failure scenario coverage

---

## Conclusion

This plan provides a comprehensive approach to creating an end-to-end integration test that validates the complete SAT workflow. The test design emphasizes:

- **Isolation:** Uses temporary directories, no production impact
- **Comprehensiveness:** Covers all 9 acceptance criteria
- **Reliability:** Deterministic, with proper timeout handling
- **Maintainability:** Clear structure, well-documented

The verification script is ready (`verify_script.sh`), and the implementation can proceed according to the detailed steps outlined above.

---

**Plan Status:** COMPLETE
**Verification Script:** ✓ Created (`verify_script.sh`)
**Ready for:** EXECUTE phase

<promise>COMPLETE</promise>
