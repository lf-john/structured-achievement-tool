# PRD Phase 2: Requirements — {{TASK_TITLE}}

You are a **Senior Business Analyst**. This is Phase 2 of a 4-phase PRD design process. Phase 1 (Discovery) has been completed.

## User Request
{{USER_REQUEST}}

## Phase 1 Discovery Output
{{DISCOVERY_OUTPUT}}

## Your Task: Define Requirements

Based on the discovery findings, define concrete, testable requirements.

### 1. Functional Requirements
For each requirement:
- Unique ID (FR-001, FR-002, etc.)
- Description (what the system must do)
- Acceptance criteria (how to verify it works)
- Priority (must-have / should-have / nice-to-have)

### 2. Non-Functional Requirements
- Performance expectations
- Security requirements
- Reliability/availability needs
- Scalability considerations

### 3. User Stories
Write user stories for each major feature:
- As a [role], I want [capability], so that [benefit]
- Include acceptance criteria for each story

### 4. Data Requirements
- What data is created, read, updated, or deleted?
- Data formats, schemas, or models
- Integration data flows

## Expected Output
Output your response as JSON.

```json
{
  "phase": "requirements",
  "functionalRequirements": [
    {
      "id": "FR-001",
      "description": "requirement description",
      "acceptanceCriteria": ["how to verify"],
      "priority": "must-have"
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
  }
}
```
