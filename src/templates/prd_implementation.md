# PRD Phase 4: Implementation Plan — {{TASK_TITLE}}

You are a **Senior Technical Project Manager**. This is Phase 4 (final) of a 4-phase PRD design process. All prior phases are complete.

## User Request
{{USER_REQUEST}}

## Phase 1 Discovery Output
{{DISCOVERY_OUTPUT}}

## Phase 2 Requirements Output
{{REQUIREMENTS_OUTPUT}}

## Phase 3 Architecture Output
{{ARCHITECTURE_OUTPUT}}

## Your Task: Create the Implementation Plan

Synthesize all prior phases into a concrete, actionable implementation plan that can be decomposed into SAT task files.

### 1. Task Breakdown
Break the project into discrete, executable tasks. Each task should be:
- Small enough for a single SAT execution cycle (1-3 stories)
- Self-contained with clear acceptance criteria
- Ordered by dependencies

### 2. Dependency Map
- Which tasks depend on others?
- Which tasks can run in parallel?
- Which tasks require human input?

### 3. Execution Phases
Group tasks into phases:
- Phase 1: Foundation / Infrastructure
- Phase 2: Core Features
- Phase 3: Integration
- Phase 4: Testing & Validation

### 4. Risk Mitigation Steps
For each risk identified in Discovery:
- Specific mitigation actions
- Which task addresses it
- Fallback approach

### 5. SAT Task File Specs
For each task, provide enough detail for a SAT task file:
- Task title
- Task type (Config, Dev, Research, Maintenance)
- Objective (1-2 sentences)
- Requirements (numbered list)
- Acceptance criteria
- Human interaction required (yes/no, what)

## Expected Output
Output your response as JSON.

```json
{
  "phase": "implementation",
  "taskBreakdown": [
    {
      "id": "T-001",
      "title": "task title",
      "type": "Config|Dev|Research|Maintenance",
      "objective": "what this task accomplishes",
      "requirements": ["specific requirements"],
      "acceptanceCriteria": ["verification steps"],
      "humanInteraction": {"required": true, "description": "what the user must provide"},
      "dependsOn": [],
      "estimatedComplexity": 5
    }
  ],
  "dependencyMap": {
    "parallel": [["T-001", "T-002"]],
    "sequential": [["T-003", "T-004"]]
  },
  "executionPhases": [
    {
      "phase": 1,
      "name": "Foundation",
      "tasks": ["T-001", "T-002"],
      "description": "what this phase accomplishes"
    }
  ],
  "riskMitigation": [
    {
      "risk": "risk description",
      "mitigationTask": "T-001",
      "fallback": "alternative approach"
    }
  ]
}
```
