# SAT Corrections Memory

Rules extracted from user feedback (ME: annotations). Injected into agent prompts.
Last updated: 2026-03-06.

## Behavioral — System Capabilities

- **[B1]** The system has full file access. Never claim "I cannot access your files." SAT runs as the user and has access to everything the user has.
- **[B2]** The system has browser automation. Playwright is installed. Never deny browser automation capabilities.
- **[B3]** Research before asking. When the system needs technical information, research it independently. Do not ask the user to research things the system can find itself.
- **[B4]** Exhaust programmatic options before suggesting manual steps. Do not ask the user to create accounts or perform manual tasks when an API or automated approach exists.

## Quality — Output Standards

- **[Q1]** Instructions must be actionable and specific. When writing instructions for a human, enumerate every click, credential, and system. Or minimize human effort by requesting only the minimum needed to finish autonomously.
- **[Q2]** Minimize human work in all workflows. Optimize for the absolute minimum human effort. Provide context but format it so relevant parts are easy to find.
- **[Q3]** All agent/subagent output must use JSON format. JSON schema validation for all agents. Each agent can have required and optional JSON parts (thinking, code, summary).
- **[Q4]** Data accuracy is a required quality check, not optional.
- **[Q5]** Template examples must match the project's tech stack. Never use language-specific examples that don't match the project. Dynamically substitute based on the project's actual technology stack(s).

## Workflow — Task Classification and Routing

- **[W1]** "Phase 2" means "later," not "out of scope." Future phases are deferred, not excluded.
- **[W2]** Notification is a Decomp decision, not a workflow phase. Decomp determines when/if to notify by adding a `notify` attribute to stories. The story executor handles notification after completion. This avoids building notification logic into every workflow.
- **[W3]** Content has three complexity tiers:
  1. **Simple** — Conversation workflow with file-write node. Short templates, internal docs, quick summaries.
  2. **Medium** — Research story with file-write node. Requires gathering information before writing.
  3. **Complex** — Research story followed by Content story. Full pipeline for substantial deliverables.
- **[W4]** Approval workflows support two rejection types: (1) Rejection (blocks + notifies) and (2) Rejection with Approval Instructions (loops back for revision).
- **[W5]** Unknown story types: closest-match + notify. Use closest-match mapping but send an ntfy explaining what happened, the story, and the type selected.
- **[W6]** Workflow type is determined by story `type` alone. The `tdd` field is redundant and should be removed.

## Cost — LLM Routing

- **[C1]** Cost-conscious LLM usage is required. Local LLMs for grunt work; cloud APIs for high-value tasks.
- **[C2]** The LLM does NOT decide model routing. Use pre-determined complexity ratings from the routing engine. No dynamic LLM-based routing decisions.
- **[C3]** Use local LLM for RAG summary. Qwen3 8B via Ollama, not cloud APIs.
- **[C4]** Prefer RAG retrieval over prompt injection for learned lessons.
- **[C5]** Reuse existing infrastructure. Use existing Mautic, SuiteCRM, N8N instances. Do not deploy fresh ones.
- **[C6]** Reuse SAT's routing engine for all LLM routing needs. Do not build separate routing for individual projects.

## Communication — Response Handling

- **[R1]** Address ALL user feedback before proceeding. Every ME: annotation must be addressed. Do not skip, summarize, or defer.
- **[R2]** Do not implement until the plan is confirmed. When the user provides corrections to a plan, edit the plan first.
- **[R3]** Reference previous instructions rather than re-inventing. Find and reference existing instructions instead of creating new, potentially conflicting ones.
- **[R4]** Use precise language. Say "X did not work for us because of Y." Do not narrow scope unnecessarily.
- **[R5]** Validate questions before asking. Verify the answer isn't already available, can't be researched independently, and is specific enough to be actionable.
- **[R6]** "Implement this" means act, not acknowledge. Directives are action requests, not discussion topics.

## Architecture

- **[A1]** Code is implemented locally. PRs merge into main on GitHub.
- **[A2]** Artifacts flow between phases, not reasoning/thinking. Thinking stays with the generating agent (logged for debugging). Only diffs, test results, and acceptance criteria are forwarded.
- **[A3]** User cancellation via `<Cancel>` file tag. SAT also handles graceful shutdown internally (SIGTERM, session invalidation, orphan cleanup).
- **[A4]** SAT both builds AND operates systems. It is not just a build tool.
- **[A5]** Weekly calibration produces recommendations, not auto-applied changes. User will decide when/if to change to monthly.
- **[A6]** Confidence scoring 0.5–0.79: notify user via ntfy AND log. User can interrupt if needed.
- **[A7]** Notification via Decomp must be implemented in code, not just recorded in learnings. Decomp adds `notify` attribute; story executor sends notification on completion.
- **[A8]** Every story must have acceptance criteria. Decomp creates these during decomposition.
- **[A9]** Multi-story tasks end with a Verify story that checks the combined result against task-level acceptance criteria. Failure triggers a Debug instance.
- **[A10]** After a failed-then-fixed task, present both attempts to user for selection (original, fixed, or reject-and-rework).
- **[A11]** Artifact manifests (files expected to be created/modified) are part of task-level acceptance criteria, verified by the Verify story.
- **[A12]** Content deliverable format is specified in acceptance criteria, not hardcoded rules. Could be .md, .xlsx, .pdf, .docx, etc.
