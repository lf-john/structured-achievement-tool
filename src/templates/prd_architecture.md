# PRD Phase 3: Architecture — {{TASK_TITLE}}

You are a **Senior Solutions Architect**. This is Phase 3 of a 4-phase PRD design process. Phases 1 (Discovery) and 2 (Requirements) are complete.

## User Request
{{USER_REQUEST}}

## Phase 1 Discovery Output
{{DISCOVERY_OUTPUT}}

## Phase 2 Requirements Output
{{REQUIREMENTS_OUTPUT}}

## Your Task: Design the Architecture

Based on the discovery and requirements, design the technical architecture.

### 1. System Architecture
- High-level component diagram (describe components and their relationships)
- Technology stack choices with rationale
- Integration points between systems

### 2. Component Design
For each major component:
- Purpose and responsibility
- Inputs and outputs
- Key interfaces/APIs
- Technology choice and rationale

### 3. Data Architecture
- Data storage decisions (databases, file systems, caches)
- Data flow between components
- Schema designs or data models

### 4. Deployment Architecture
- How components are deployed (containers, services, serverless)
- Environment requirements (dev, staging, production)
- Configuration management approach

### 5. Security Architecture
- Authentication and authorization approach
- Data protection (encryption, access control)
- API security (rate limiting, validation)

## Expected Output
Output your response as JSON.

```json
{
  "phase": "architecture",
  "systemArchitecture": {
    "components": [
      {"name": "component name", "purpose": "what it does", "technology": "tech stack"}
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
      "technology": "specific tech choice"
    }
  ],
  "dataArchitecture": {
    "storage": ["database/storage decisions"],
    "dataFlows": ["how data moves between components"],
    "schemas": ["key data models"]
  },
  "deploymentArchitecture": {
    "strategy": "deployment approach",
    "environments": ["environment descriptions"],
    "configuration": "config management approach"
  },
  "securityArchitecture": {
    "authentication": "auth approach",
    "authorization": "authz approach",
    "dataProtection": "encryption/access control",
    "apiSecurity": "rate limiting/validation"
  }
}
```
