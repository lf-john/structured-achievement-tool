# Vector Memory System - Quick Start Guide

## What is Vector Memory?

The Vector Memory system gives your orchestrator a "memory" that learns from every task you complete. When you start a new task, it automatically finds similar past tasks and uses that knowledge to provide better guidance.

## Prerequisites

### 1. Install Ollama (if not already installed)
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Start Ollama Service
```bash
ollama serve &
```

### 3. Pull the Embedding Model
```bash
ollama pull nomic-embed-text
```

### 4. Verify Installation
```bash
ollama list | grep nomic-embed-text
```

You should see `nomic-embed-text` in the list.

## How It Works

### Automatic Memory Building

Every time you complete a task:
1. The orchestrator automatically stores the task request + response
2. It generates an embedding (numerical representation) of the content
3. It saves both to the vector database

### Automatic Context Retrieval

When you start a new task:
1. The orchestrator searches for similar past tasks
2. It finds the top 3 most relevant previous tasks
3. It injects that context into the decomposition prompt
4. Your agent gets smarter over time!

## File Locations

### Vector Database
```
<project-path>/.memory/task_vectors.db
```

This file contains all your task embeddings and metadata.

### Backing Up Your Memory
```bash
# Backup
cp /path/to/project/.memory/task_vectors.db ~/backups/

# Restore
cp ~/backups/task_vectors.db /path/to/project/.memory/
```

## Example Usage

### Scenario: Building Authentication Features

**Task 1** (First time)
```markdown
Request: Implement JWT-based authentication system
```

The orchestrator processes this with no prior context (empty memory).

**Task 2** (Learning from Task 1)
```markdown
Request: Add password reset functionality
```

The orchestrator automatically finds Task 1 as similar and injects context:
```
Similar past tasks:
1. Implemented JWT-based auth with refresh tokens
   Metadata: {"success": true, "task_type": "development"}
```

**Task 3** (Learning from Tasks 1 & 2)
```markdown
Request: Create user registration endpoint
```

The orchestrator finds both previous auth-related tasks and provides comprehensive context.

## Viewing Memory Contents

### Check Database Size
```bash
ls -lh <project-path>/.memory/task_vectors.db
```

### Query Memory (SQLite)
```bash
sqlite3 <project-path>/.memory/task_vectors.db

# List all stored tasks
SELECT id, substr(text, 1, 100) as preview
FROM documents
ORDER BY created_at DESC
LIMIT 10;

# Count total tasks
SELECT COUNT(*) FROM documents;

# View metadata
SELECT metadata FROM documents LIMIT 5;
```

## Testing the System

### Run All Vector Memory Tests
```bash
cd /path/to/project
source venv/bin/activate
pytest tests/test_embedding_service.py tests/test_vector_store.py tests/test_orchestrator_vector_memory.py -v
```

### Test Ollama Connection
```bash
# Test if Ollama is responding
ollama run nomic-embed-text --embed "test text"
```

### Manual Test
```python
from src.core.embedding_service import EmbeddingService
from src.core.vector_store import VectorStore

# Create services
embedding_service = EmbeddingService()
vector_store = VectorStore(
    db_path="./test_vectors.db",
    embedding_service=embedding_service
)

# Add a document
doc_id = vector_store.add_document(
    "Implement user authentication with JWT tokens",
    {"task_type": "development", "priority": "high"}
)

# Search for similar documents
results = vector_store.search("add login feature", k=5)
for result in results:
    print(f"Score: {result['score']:.3f} - {result['text'][:100]}")
```

## Troubleshooting

### Ollama Not Running
```
Error: Ollama command not found
```

**Solution**: Start Ollama service
```bash
ollama serve &
```

### Model Not Found
```
Error: Model 'nomic-embed-text' not found
```

**Solution**: Pull the model
```bash
ollama pull nomic-embed-text
```

### Dimension Mismatch Error
```
Error: Dimension mismatch for inserted vector
```

**Solution**: Delete and recreate the database (it will auto-detect dimensions)
```bash
rm <project-path>/.memory/task_vectors.db
# Database will be recreated on next task
```

### Slow Embedding Generation
- Embeddings are generated locally, speed depends on your hardware
- First embedding may be slower as the model loads
- Subsequent embeddings are faster

### Database Locked
```
Error: database is locked
```

**Solution**: Close any SQLite connections to the database
```bash
# Kill any processes using the database
lsof | grep task_vectors.db
```

## Performance Notes

### Embedding Speed
- **First embedding**: 2-5 seconds (model loading)
- **Subsequent embeddings**: 0.1-0.5 seconds
- **Batch embeddings**: Processed sequentially

### Search Speed
- **Search query**: < 100ms for databases with < 1000 documents
- **Scales well**: sqlite-vec is optimized for vector search

### Storage
- **Per document**: ~3KB (768-dim float vector + text + metadata)
- **1000 documents**: ~3MB
- **10000 documents**: ~30MB

## Best Practices

### 1. Regular Backups
```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
cp .memory/task_vectors.db backups/vectors_$DATE.db
```

### 2. Clean Metadata
Store useful metadata for better filtering:
```python
metadata = {
    "task_name": "user-auth",
    "task_type": "development",
    "success": True,
    "timestamp": "2024-01-15",
    "tags": ["authentication", "security"],
    "complexity": "medium"
}
```

### 3. Monitor Memory Growth
```bash
# Check memory size weekly
du -h .memory/
```

### 4. Descriptive Task Text
Better task descriptions = better similarity matching:
- ✅ "Implement JWT-based authentication with refresh token support"
- ❌ "Add auth"

## Advanced Configuration

### Using a Different Embedding Model
```python
# In src/orchestrator.py
self.embedding_service = EmbeddingService(
    model_name="all-minilm"  # Smaller, faster model
)
```

### Custom Database Location
```python
orchestrator = Orchestrator(
    project_path="/path/to/project",
    vector_db_path="/custom/path/vectors.db"
)
```

### Adjusting Search Results
```python
# In src/orchestrator.py, line ~34
similar_tasks = self.vector_store.search(user_request, k=5)  # Get top 5 instead of 3
```

## FAQ

**Q: Does this send data to external servers?**
A: No, everything runs locally using Ollama.

**Q: Can I delete the vector database?**
A: Yes, it will be recreated automatically. You'll lose the accumulated memory.

**Q: How accurate is the similarity search?**
A: Very accurate for semantic similarity. It understands context, not just keywords.

**Q: Can I share memory across projects?**
A: Not by default, but you can copy the database file between projects.

**Q: Does it slow down task processing?**
A: Minimal impact: ~0.5s for embedding + search before task processing.

## Getting Help

If you encounter issues:

1. Check Ollama is running: `ollama list`
2. Verify model is installed: `ollama list | grep nomic-embed-text`
3. Run the test suite: `pytest tests/test_vector_store.py -v`
4. Check logs for error messages

For more details, see: `VECTOR_MEMORY_IMPLEMENTATION.md`
