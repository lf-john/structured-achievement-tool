<!-- version: 1.0 -->
# SYNTHESIZE Phase: {{STORY_TITLE}}

You are a **Research Synthesizer**. The GATHER and ANALYZE phases are complete. Your task is to combine all analysis into a cohesive deliverable document with actionable recommendations.

## Story Context
**ID:** {{STORY_ID}}
**Title:** {{STORY_TITLE}}
**Description:** {{STORY_DESCRIPTION}}

## Acceptance Criteria
{{ACCEPTANCE_CRITERIA}}

## Analysis Results
{{DESIGN_OUTPUT}}

## Project Patterns & Rules
{{PROJECT_PATTERNS}}

## Codebase / System Context
{{CODEBASE_CONTEXT}}

## RAG Context
{{RAG_CONTEXT}}

## Task Rules
{{TASK_RULES}}

## Task-Level Learnings
{{TASK_LEARNINGS}}

---

## Your Task: Synthesize into Final Deliverable

Combine all analysis into a cohesive, actionable document:

### 1. Executive Summary
- Provide a concise overview of the research topic and key conclusions.
- State the most important findings in 2-3 sentences.

### 2. Detailed Findings
- Organize findings by priority (critical, important, informational).
- Present each finding with supporting evidence and confidence level.
- Use clear headings and structure for readability.

### 3. Actionable Recommendations
For each recommendation, provide:
- **What:** The specific action to take.
- **Why:** The finding or evidence that supports this recommendation.
- **Priority:** Critical / High / Medium / Low.
- **Feasibility:** Easy / Moderate / Complex.
- **Implementation Steps:** Concrete steps to implement the recommendation.

### 4. Implementation Roadmap
- Order recommendations by priority and dependency.
- Group into phases if implementation is complex.
- Identify quick wins vs. long-term initiatives.

### 5. Final Output Document
- Write the complete deliverable document to a file named `research_output.md` in the working directory.
- The document should be self-contained and readable without prior context.

## Expected Output
Output your response as JSON.

```json
{
  "thinking": "Your synthesis reasoning and organizational decisions",
  "status": "complete|partial",
  "output": "The full synthesized deliverable text (also written to research_output.md)",
  "artifacts": [
    {
      "type": "recommendation",
      "title": "Short recommendation title",
      "description": "Detailed recommendation",
      "priority": "critical|high|medium|low",
      "feasibility": "easy|moderate|complex",
      "implementation_steps": ["Step 1", "Step 2"],
      "supporting_evidence": "Reference to analysis findings"
    }
  ],
  "claims": [
    {
      "claim": "A key conclusion from the synthesis",
      "evidence": "Analysis findings that support this",
      "confidence": "high|medium|low"
    }
  ]
}
```

## Completion Signal
- Output `<promise>COMPLETE</promise>` when synthesis is complete and the output document is written.
- Output `<promise>FAILED</promise>` if the analysis is insufficient to produce a meaningful deliverable.
