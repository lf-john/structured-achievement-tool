<!-- version: 1.0 -->
# PRD Phase 3: Architecture — {{TASK_TITLE}}

You are a **Senior Solutions Architect**. This is Phase 3 of a 4-phase PRD design process. Phases 1-2 are complete and user-reviewed.

## User Request
{{USER_REQUEST}}

## Phase 1 Discovery Output
{{DISCOVERY_OUTPUT}}

## Phase 2 Requirements Output
{{REQUIREMENTS_OUTPUT}}

## SAT Execution Context

The implementation will be executed by SAT (Structured Achievement Tool), an autonomous task execution system. When designing the architecture, consider:

- **SAT executes stories via typed workflows** — development (TDD), config (plan/execute/verify), maintenance, debug, research, review, and conversation. Design components to be testable.
- **Stories should be small** (1-3 files, independently executable). Design architecture so components can be built incrementally.
- **SAT has vector memory (RAG)** — learnings from past tasks are available to future tasks. Design for iterative refinement.
- **Verification is automated** — stories need testable acceptance criteria that can be checked programmatically.

## Your Task: Design the Architecture

### 1. Solution Approaches
Present 2-3 fundamentally different approaches. For each: what it optimizes for, what it sacrifices, rough complexity. Recommend one with rationale.

### 2. System Architecture
High-level components, technology stack with rationale, integration points.

### 3. Component Design
For each major component: purpose, inputs/outputs, key interfaces, technology choice.

### 4. Data Architecture
Storage decisions, data flows, key schemas.

### 5. MVP Boundary
Clear line between MVP (minimum to deliver core value) and post-MVP.

### 6. Feasibility Check
Validate against real constraints: API availability, licensing, cost, constraints from Phase 1.

### 7. Self-Audit
- Does architecture satisfy all must-have requirements?
- Is MVP realistic and valuable on its own?
- Any single points of failure?
- Any unvalidated assumptions?

### 8. Questions for the User
2-3 questions about MVP boundary and integration details.

## Expected Output
Output your response as JSON.

```json
{
  "phase": "architecture",
  "solutionApproaches": [
    {
      "name": "approach name",
      "description": "what this approach does",
      "optimizesFor": "what it's good at",
      "sacrifices": "what it gives up",
      "complexity": "low/medium/high"
    }
  ],
  "recommendedApproach": "name of recommended approach",
  "recommendationRationale": "why this approach",
  "systemArchitecture": {
    "components": [
      {"name": "name", "purpose": "what it does", "technology": "tech stack"}
    ],
    "integrationPoints": ["how components connect"],
    "technologyStack": {"category": "choice with rationale"}
  },
  "componentDesign": [
    {
      "name": "component name",
      "purpose": "responsibility",
      "inputs": ["what it receives"],
      "outputs": ["what it produces"],
      "interfaces": ["API endpoints or interfaces"],
      "technology": "specific tech"
    }
  ],
  "dataArchitecture": {
    "storage": ["database/storage decisions"],
    "dataFlows": ["how data moves"],
    "schemas": ["key data models"]
  },
  "mvpBoundary": {
    "mvp": ["what ships first"],
    "postMvp": ["what can wait"]
  },
  "feasibilityCheck": {
    "passed": true,
    "concerns": ["any feasibility concerns"]
  },
  "selfAudit": {
    "passed": true,
    "revisions": ["revisions made, or empty"]
  },
  "questionsForUser": [
    "Question 1: Does the MVP boundary match your minimum viable first delivery?",
    "Question 2: For external integrations — do you have API credentials/documentation already?"
  ]
}
```
