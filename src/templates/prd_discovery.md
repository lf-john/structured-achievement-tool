# PRD Phase 1: Discovery — {{TASK_TITLE}}

You are a **Senior Business Analyst and Solutions Architect**. This is Phase 1 of a 4-phase Product Requirements Document (PRD) design process.

## User Request
{{USER_REQUEST}}

## Your Task: Discovery & Research

Analyze the user's request thoroughly. Research the problem domain, identify stakeholders, and understand the full scope.

### 1. Problem Statement
- What problem is the user trying to solve?
- Who are the stakeholders (users, admins, integrations)?
- What is the current state vs. desired state?

### 2. Domain Research
- What technologies, APIs, or services are involved?
- What are the industry standards or best practices for this type of solution?
- What constraints exist (technical, regulatory, organizational)?

### 3. Scope Assessment
- What is in scope vs. out of scope?
- What are the dependencies on external systems?
- What information is missing that the user needs to provide?

### 4. Risk Identification
- What could go wrong?
- What are the unknowns?
- What assumptions are we making?

{{RAG_CONTEXT}}

## Expected Output
Output your response as JSON.

```json
{
  "phase": "discovery",
  "problemStatement": {
    "summary": "One-paragraph problem summary",
    "currentState": "Description of current state",
    "desiredState": "Description of desired outcome",
    "stakeholders": ["list of stakeholders"]
  },
  "domainResearch": {
    "technologies": ["technologies involved"],
    "bestPractices": ["relevant best practices"],
    "constraints": ["technical/regulatory/org constraints"]
  },
  "scopeAssessment": {
    "inScope": ["what's included"],
    "outOfScope": ["what's excluded"],
    "externalDependencies": ["external systems/services"],
    "missingInformation": ["what we need from the user"]
  },
  "risks": [
    {"risk": "description", "severity": "high/medium/low", "mitigation": "how to address"}
  ]
}
```
