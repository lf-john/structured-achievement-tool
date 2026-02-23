# Structured Achievement Tool (SAT)

Autonomous task orchestration system that decomposes user requests into TDD-driven stories, executes them via Ralph Pro, and learns from results using vector memory (RAG).

## Architecture

```
User writes .md file in Obsidian → SAT daemon detects <Pending> tag →
Orchestrator classifies & decomposes → Ralph Pro executes stories →
Results embedded in vector memory → Response written back to Obsidian
```

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| Daemon | `src/daemon.py` | Watches `~/GoogleDrive/DriveSyncFiles/claude-tasks/` for `.md` files with `<Pending>` tag |
| Orchestrator | `src/orchestrator.py` | Classification, decomposition, Ralph Pro delegation, vector memory |
| StoryAgent | `src/core/story_agent.py` | Classifies task type, decomposes into stories via Claude |
| LogicCore | `src/core/logic_core.py` | Claude CLI wrapper for LLM calls |
| EmbeddingService | `src/core/embedding_service.py` | Ollama nomic-embed-text embeddings (768-dim, 2048-token context) |
| VectorStore | `src/core/vector_store.py` | sqlite-vec similarity search |
| LangGraph | `src/core/langgraph_orchestrator.py` | State machine: DESIGN → TDD_RED → CODE → TDD_GREEN → VERIFY → LEARN |
| PhaseRunner | `src/core/phase_runner.py` | Executes phases via Claude/Gemini CLI |
| ContextRetriever | `src/core/context_retriever.py` | RAG context injection from vector memory |

### External Dependencies

- **Ralph Pro** (`~/ralph-pro/`): Node.js TDD execution engine. SAT writes PRD to `~/ralph-pro/data/projects/structured-achievement-tool/tasks/<task-id>/prd.json`, then spawns `node ralph-pro.js` to execute stories.
- **Ollama**: Local LLM inference (nomic-embed-text for embeddings). Runs as `ollama.service`.
- **Google Drive**: Task files synced via rclone FUSE mount at `~/GoogleDrive/`.
- **ntfy.sh**: Push notifications to topic `johnlane-claude-tasks`.

## Task File Markers

Files use tag-based state machine:
- `<Pending>` — Ready for processing (daemon picks up)
- `<Working>` — Currently being processed
- `<Finished>` — Completed successfully
- `<Failed>` — Execution failed
- `<Cancel>` — User requested cancellation
- `# <Pending>` — Response file placeholder (# prevents triggering; user removes # to continue)

## Development

### Python Environment

```bash
cd ~/projects/structured-achievement-tool
source venv/bin/activate
```

### Running Tests

```bash
# All tests (excludes 2 known-broken import tests)
pytest tests/ --ignore=tests/test_US_001_full_sat_loop_integration.py --ignore=tests/test_daemon.py -v

# Specific module
pytest tests/test_embedding_service.py -v
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
- **Graceful degradation**: Vector memory failures must not break task processing. Always wrap in try/except with logging.
- **Text truncation**: EmbeddingService truncates to 7500 chars (~2048 tokens) before sending to Ollama. The orchestrator keeps embedded documents concise.
- **Ollama resilience**: EmbeddingService auto-detects Ollama failures and attempts `systemctl restart ollama` before retrying.

## Key Constraints

- nomic-embed-text context window: **2048 tokens** (~7500 chars). Never send raw task logs to embedding API.
- Vector DB at `.memory/vectors.db` — do not delete; contains cross-task learning history.
- Ralph Pro data at `~/ralph-pro/data/projects/structured-achievement-tool/` — PRD and progress files live there.
- Daemon polls every 5 seconds. Uses `os.fsync()` for Google Drive FUSE reliability.
