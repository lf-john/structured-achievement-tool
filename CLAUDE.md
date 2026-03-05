# Structured Achievement Tool (SAT)

Autonomous task orchestration system that decomposes user requests into stories, executes them via LangGraph workflows, and learns from results using vector memory (Memory Core).

## Architecture

```
User writes .md file in Obsidian → SAT daemon detects <Pending> tag →
Orchestrator classifies & decomposes → Story executor runs workflows →
Results embedded in vector memory → Response written back to Obsidian
```

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| Daemon | `src/daemon.py` | Watches `~/GoogleDrive/DriveSyncFiles/sat-tasks/` for `.md` files with `<Pending>` tag |
| Monitor | `src/monitor.py` | Queue management: retries, stuck detection, task scheduling |
| Orchestrator | `src/orchestrator_v2.py` | Classification, decomposition, execution, vector memory |
| StoryAgent | `src/agents/story_agent.py` | Classifies task type, decomposes into stories with dependencies |
| RoutingEngine | `src/llm/routing_engine.py` | Selects LLM provider by agent complexity rating |
| CLIRunner | `src/llm/cli_runner.py` | Async subprocess spawner for LLM CLI tools |
| EmbeddingService | `src/core/embedding_service.py` | Ollama nomic-embed-text embeddings (768-dim) |
| VectorStore | `src/core/vector_store.py` | sqlite-vec similarity search |
| ContextRetriever | `src/core/context_retriever.py` | RAG context injection from vector memory |

### External Dependencies

- **Ollama**: Local LLM inference (nomic-embed-text for embeddings, Qwen3 8B for local tasks). Runs as `ollama.service`.
- **Google Drive**: Task files synced via rclone FUSE mount at `~/GoogleDrive/`.
- **ntfy.sh**: Push notifications to topic `johnlane-claude-tasks`.
- **GitHub**: Code repository at `lf-john/structured-achievement-tool` (private).

## Governance Documents

These files are injected into agent prompts to enforce consistent behavior:

| Document | Purpose |
|----------|---------|
| `corrections.md` | Persistent rules from user feedback (ME: annotations) |
| `product_constitution.md` | Quality targets, cost rules, escalation, safety constraints |
| `domain_glossary.md` | Canonical term definitions to prevent terminology drift |
| `coding_standards.md` | Python style, testing, security, git practices |

## Task File Markers

Files use tag-based state machine:
- `<Pending>` — Ready for processing (daemon picks up)
- `<Working>` — Currently being processed
- `<Finished>` — Completed successfully
- `<Failed>` — Execution failed
- `<Cancel>` — User requested cancellation
- `# <User>` — Response file placeholder (# prevents triggering; user removes # to continue)

## Development

### Python Environment

```bash
cd ~/projects/structured-achievement-tool
source venv/bin/activate
```

### Linting

```bash
ruff check src/ tests/          # Check for lint errors
ruff check --fix src/ tests/    # Auto-fix what's possible
```

### Running Tests

```bash
pytest tests/ -v                           # All tests
pytest tests/test_embedding_service.py -v  # Specific module
pytest tests/ -v -k "not integration"      # Skip integration tests
```

### Service Management

```bash
systemctl --user status sat.service
systemctl --user restart sat.service
journalctl --user -u sat.service -f
```

## Conventions

- **TDD**: All features built test-first. Tests in `tests/` mirror `src/` structure.
- **Mocking**: Use `unittest.mock.patch` for Ollama, subprocess, and external APIs.
- **Graceful degradation**: Vector memory failures must not break task processing.
- **Conventional commits**: `type(scope): description` (feat, fix, chore, ci, docs, test, refactor).
- **Pre-commit hooks**: ruff + detect-secrets + whitespace checks run on every commit.
- **Branch isolation**: All code changes on branches, merged via PR.

## Key Constraints

- nomic-embed-text context window: **2048 tokens** (~7500 chars). Never send raw task logs to embedding API.
- Vector DB at `.memory/vectors.db` — do not delete; contains cross-task learning history.
- LLM routing is deterministic via routing engine — never hardcode a model selection.
- Daemon polls every 5 seconds. Uses `os.fsync()` for Google Drive FUSE reliability.
- Cost tracking: alert at $2/task, $50/month. Hard stop at $100/month.
