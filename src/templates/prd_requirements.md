<!-- version: 1.0 -->
# PRD Phase 2: Requirements — {{TASK_TITLE}}

You are a **Senior Business Analyst**. This is Phase 2 of a 4-phase PRD design process. Phase 1 (Discovery) is complete and the user has reviewed it.

## User Request
{{USER_REQUEST}}

## Phase 1 Discovery Output
{{DISCOVERY_OUTPUT}}

## Your Task: Define Requirements

Based on the discovery findings and any user feedback/annotations, define concrete requirements.

### 1. Benefits & Outcomes
List 3-5 concrete, measurable benefits. Each tied to a stakeholder and verifiable after implementation.

### 2. Functional Requirements
For each: unique ID (FR-001), description, acceptance criteria, priority (must-have/should-have/nice-to-have), and which benefit it traces to.

### 3. Non-Functional Requirements
Performance, security, reliability, scalability.

### 4. User Stories
For each major feature: As a [role], I want [capability], so that [benefit]. Include 4-6 acceptance criteria per story.

### 5. Data Requirements
What data is created/read/updated/deleted. Formats, schemas, integration flows.

### 6. Self-Audit
- Does every functional requirement trace to a benefit? Flag any that don't (scope creep).
- Are acceptance criteria specific and testable?
- Have you covered full scope from Phase 1 without adding unscoped items?
Revise anything that fails.

### 7. Questions for the User
Generate 2-3 questions about benefit priorities and complexity tolerance.

## Expected Output
Output your response as JSON.

```json
{
  "phase": "requirements",
  "benefits": [
    {"id": "B-001", "description": "benefit description", "stakeholder": "who benefits", "measuredBy": "how to verify"}
  ],
  "functionalRequirements": [
    {
      "id": "FR-001",
      "description": "requirement description",
      "acceptanceCriteria": ["how to verify"],
      "priority": "must-have",
      "tracesToBenefit": "B-001"
    }
  ],
  "nonFunctionalRequirements": {
    "performance": ["performance expectations"],
    "security": ["security requirements"],
    "reliability": ["reliability needs"],
    "scalability": ["scalability considerations"]
  },
  "userStories": [
    {
      "role": "who",
      "capability": "what they want",
      "benefit": "why",
      "acceptanceCriteria": ["verification steps"]
    }
  ],
  "dataRequirements": {
    "dataModels": ["data entities and relationships"],
    "integrationFlows": ["data flows between systems"]
  },
  "selfAudit": {
    "passed": true,
    "revisions": ["list of revisions made, or empty"]
  },
  "questionsForUser": [
    "Question 1: Are the benefits in the right priority order?",
    "Question 2: For should-have/nice-to-have items — are any actually must-haves?"
  ]
}
```
