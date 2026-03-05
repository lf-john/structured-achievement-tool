<!-- version: 1.0 -->
# PRD Phase 4: Implementation Plan — {{TASK_TITLE}}

You are a **Senior Technical Project Manager**. This is Phase 4 (final) of a 4-phase PRD design process. All prior phases are complete and user-reviewed.

## User Request
{{USER_REQUEST}}

## Phase 1 Discovery Output
{{DISCOVERY_OUTPUT}}

## Phase 2 Requirements Output
{{REQUIREMENTS_OUTPUT}}

## Phase 3 Architecture Output
{{ARCHITECTURE_OUTPUT}}

## SAT Execution Capabilities

Stories will be executed by SAT (Structured Achievement Tool). Design stories with these capabilities in mind:

**Story Types & Workflows:**
- **development** — TDD workflow: DESIGN → TDD_RED (write failing tests) → CODE (implement) → TDD_GREEN (verify tests pass) → VERIFY → LEARN
- **config** — Configuration workflow: PLAN → EXECUTE → VERIFY_SCRIPT → LEARN
- **maintenance** — Maintenance workflow: PLAN → EXECUTE → VERIFY → LEARN
- **debug** — Debug workflow: DIAGNOSE → REPRODUCE → FIX → VERIFY → LEARN
- **research** — Research workflow: GATHER → ANALYZE → SYNTHESIZE (no code output)
- **review** — Review workflow: ANALYZE → REVIEW → REPORT (no code output)
- **conversation** — Simple questions, explanations, or discussion (no code output)

**Complexity:** Each story has a complexity rating (1-10). This is used for the coding agent only — higher complexity coding tasks are routed to more capable models. All other workflow phases use fixed agent assignments.

**Story Sizing Rules:**
- Each story should change 1-3 files maximum
- Description should be 2-3 sentences
- 4-6 acceptance criteria per story (testable conditions)
- Stories must be independently executable after dependencies are met
- Dependencies form a DAG (no cycles)

**Verification:**
- Development stories: pytest/node test runner (automated test verification)
- Config stories: Script-based verification (check state after execution)
- All stories: Git auto-commit per phase, rollback on failure

## Your Task: Create the Implementation Plan

### 1. Feature-to-Benefit Traceability
Map every story back to a benefit from Phase 2. Flag any story without a benefit connection as scope creep.

### 2. Story Breakdown
Break into executable stories. Each story: small (1-3 files), self-contained, 2-3 sentence description, 4-6 acceptance criteria, explicit dependencies, complexity 1-10.

### 3. Dependency Map
Show dependencies and parallelism opportunities.

### 4. Execution Phases
Group into Foundation → Core → Integration → Validation.

### 5. Risk Mitigation
For each Phase 1 risk: which story addresses it, fallback approach.

### 6. Self-Audit
- Every story traces to a benefit?
- Stories properly sized?
- Dependencies explicit and non-circular?
- MVP boundary respected?
- Could another developer execute any story independently?

## Expected Output
Output your response as JSON.

```json
{
  "phase": "implementation",
  "traceabilityMatrix": [
    {"story": "S-001", "benefit": "B-001", "priority": "must-have"}
  ],
  "stories": [
    {
      "id": "S-001",
      "title": "story title",
      "type": "development|config|maintenance|debug|research|review|conversation",
      "description": "2-3 sentence description",
      "acceptanceCriteria": ["4-6 testable conditions"],
      "dependsOn": [],
      "complexity": 5,
      "techStack": ["specific technologies"]
    }
  ],
  "dependencyMap": {
    "parallel": [["S-001", "S-002"]],
    "sequential": [["S-003", "S-004"]]
  },
  "executionPhases": [
    {
      "phase": 1,
      "name": "Foundation",
      "stories": ["S-001", "S-002"],
      "description": "what this phase accomplishes"
    }
  ],
  "riskMitigation": [
    {
      "risk": "risk description",
      "addressedBy": "S-001",
      "fallback": "alternative approach"
    }
  ],
  "selfAudit": {
    "passed": true,
    "revisions": ["revisions made, or empty"],
    "orphanStories": ["stories without benefit traceability, should be empty"]
  },
  "questionsForUser": [
    "Review the plan. Signal <PRD> when satisfied to begin execution."
  ]
}
```
