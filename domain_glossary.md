# SAT Domain Glossary

Canonical definitions for terms used across SAT prompts, code, and documentation.
Injected into agent prompts to prevent terminology drift.

## Core Concepts

| Term | Definition |
|------|-----------|
| **Task** | A user request expressed as a markdown file. Contains requirements and acceptance criteria. |
| **Story** | An atomic unit of work decomposed from a task. Has a type, complexity, and dependencies. |
| **Phase** | A single step within a story's workflow (e.g., DESIGN, TDD_RED, CODE, VERIFY, LEARN). |
| **Workflow** | A LangGraph state machine defining the sequence of phases for a story type. |
| **DAG** | Directed Acyclic Graph. Stories within a task are organized as a DAG based on `dependsOn` relationships. |

## Story Types

| Type | Description | Workflow |
|------|-------------|----------|
| **dev** | Software development with tests. | DESIGN → TDD_RED → CHECK → CODE → CHECK → VERIFY → LEARN |
| **config** | Infrastructure or configuration changes. | PLAN → EXECUTE → VERIFY_SCRIPT → LEARN |
| **maintenance** | Codebase upkeep, dependency updates. | PLAN → EXECUTE → VERIFY → LEARN |
| **debug** | Bug investigation and fix. | DIAGNOSE → REPRODUCE → FIX → VERIFY → LEARN |
| **research** | Information gathering, no code output. | GATHER → ANALYZE → SYNTHESIZE |
| **content** | Documentation, templates, written deliverables. | Three tiers: Simple, Medium, Complex. |
| **review** | Code or architecture review. | ANALYZE → REVIEW → REPORT |

## Content Tiers

| Tier | Description | Workflow |
|------|-------------|----------|
| **Simple** | Short templates, internal docs, quick summaries. | Conversation + file-write |
| **Medium** | Docs requiring research before writing. | Research story + file-write |
| **Complex** | Substantial deliverables (battlecards, sequences). | Research story → Content story |

## File State Tags

| Tag | Meaning |
|-----|---------|
| `<Pending>` | Ready for SAT to process |
| `<Working>` | Currently being processed |
| `<Finished>` | Completed successfully |
| `<Failed>` | Execution failed |
| `<Cancel>` | User requested cancellation |
| `# <User>` | Response placeholder — user removes `#` to continue |

## System Components

| Component | Description |
|-----------|-------------|
| **Daemon** | File watcher that detects `<Pending>` tags and triggers processing |
| **Monitor** | Queue manager that handles retries, stuck detection, and task scheduling |
| **Orchestrator** | Main controller: classifies, decomposes, executes, and writes results |
| **Classifier** | Determines task type (dev, config, content, etc.) |
| **Decomposer** | Breaks tasks into stories with dependencies and complexity ratings |
| **Routing Engine** | Selects LLM provider based on agent complexity ratings |
| **Memory Core** | Persistent knowledge system: vector memory, corrections, learnings, audit trail |
| **Mediator** | Post-code review agent that checks for quality issues before verification |

## LLM Routing

| Term | Definition |
|------|-----------|
| **Provider** | An LLM model accessible via CLI or API (e.g., claude-sonnet, qwen3-8b) |
| **Power Rating** | Numeric capability score for a provider (1-10). Higher = more capable. |
| **Complexity** | Agent-level difficulty rating (1-10). Determines minimum power rating needed. |
| **Local model** | LLM running via Ollama on GPU. Zero API cost. |
| **Cloud model** | LLM accessed via API (Anthropic, Google, OpenAI). Per-token cost. |

## Quality Pipeline

| Term | Definition |
|------|-----------|
| **Corrections** | Persistent rules from user feedback. Injected into prompts. |
| **Product Constitution** | System-wide behavioral rules and quality targets. |
| **Confidence Score** | 0.0-1.0 rating on classification certainty. Below 0.5 → escalate. |
| **Circuit Breaker** | Auto-stop after 3 consecutive failures of same type. |
| **Calibration** | Monthly review producing recommendations (advisory, not auto-applied). |
