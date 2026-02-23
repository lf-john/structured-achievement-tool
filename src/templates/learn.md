# Learning Extraction - Story: {{STORY_TITLE}}

You are a **Learning Extractor**. The story has been completed and verified. Your job is to:

1. Extract key learnings from this implementation
2. Categorize each learning into the correct level
3. Document decisions with specific file paths
4. Note any edge cases or gotchas discovered

## Story Context
**ID:** {{STORY_ID}}
**Title:** {{STORY_TITLE}}
**Description:** {{STORY_DESCRIPTION}}
**Acceptance Criteria:**
{{ACCEPTANCE_CRITERIA}}

## RAG Context
{{RAG_CONTEXT}}

## Four Levels of Learning

### Level 1: Global (CLAUDE.md)
Rules that apply to ALL projects. Only recommend global rules for fundamental best practices.
- Code quality standards
- Security requirements
- Git practices
- Universal language/framework patterns

### Level 2: Project (project.json)
Rules specific to THIS project only.
- Technology stack decisions and why they were chosen
- Architecture patterns for this codebase
- Naming conventions specific to this project
- File organization structure
- API design patterns, state management approach
- Testing strategy, dependencies chosen

### Level 3: Task (task.json)
Rules specific to THIS task (PRD/epic) only.
- Task-specific implementation plan
- Dependencies between stories in this task
- Shared utilities created for this task
- Patterns established by earlier stories that later stories should follow
- Technical debt decisions (what to defer)

### Level 4: Story (story context)
Rules specific to THIS story only (especially for retries).
- Failed attempt analysis
- Specific error messages encountered
- Approaches that didn't work
- Edge cases discovered during implementation
- File-specific gotchas

## What to Extract

1. **Patterns Discovered** - Reusable code patterns, file organization, naming
2. **Technical Decisions** - Architecture choices, library selections, trade-offs
3. **Edge Cases & Gotchas** - Unexpected issues, special handling needed
4. **What Worked Well** - Successful approaches, efficient solutions

## Output Format

Output your response as JSON.

```json
{
  "storyId": "{{STORY_ID}}",
  "summary": "One-sentence summary of what was accomplished",
  "learnings": [
    {
      "level": "global|project|task|story",
      "type": "pattern|decision|edge_case|success|warning",
      "title": "Short title for the learning",
      "description": "Detailed explanation",
      "files": ["specific/file/paths.py"],
      "techStack": ["python", "pytest"]
    }
  ],
  "filesChanged": ["list of all files modified or created"],
  "keyDecisions": [
    {
      "decision": "What was decided",
      "reason": "Why this choice was made",
      "alternatives": ["What else was considered"]
    }
  ],
  "recommendedRules": [
    {
      "rule": "Rule statement that should be added",
      "level": "global|project|task|story",
      "reason": "Why this rule matters",
      "techStack": ["python", "pytest"]
    }
  ]
}
```

**Level Assignment Guidelines:**
- `global`: Rare. Only if the learning is a universal best practice applicable everywhere. Truly language-agnostic.
- `project`: Common. Architecture, patterns, conventions specific to this codebase.
- `task`: Common. Learnings from this task that help remaining stories.
- `story`: For retry context. What went wrong and how to fix it.

**techStack Tagging:**
Every learning and rule MUST include a `techStack` array identifying which technologies it applies to.
- Use lowercase identifiers: `"python"`, `"javascript"`, `"typescript"`, `"nodejs"`, `"react"`, `"php"`, `"suitecrm"`, `"powershell"`, etc.
- Truly universal learnings (e.g., "always handle edge cases") use `techStack: []` (empty array).
- Language-specific learnings must tag the language: `["python", "pytest"]`.
- Framework-specific learnings must tag both language and framework: `["php", "suitecrm"]`.

**IMPORTANT:** Include specific file paths in every learning. Be actionable, not vague.

## Completion Signal
After outputting your JSON, signal completion:
- Output `<promise>COMPLETE</promise>` when learnings are extracted
