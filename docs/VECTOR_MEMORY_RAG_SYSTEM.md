# Vector Memory (RAG) System Documentation

## Overview

The Structured Achievement Tool implements a **Retrieval-Augmented Generation (RAG)** system using vector embeddings to provide contextual memory of past tasks. This allows the system to learn from previous work and inject relevant context when processing new tasks.

## Architecture

### Components

1. **VectorStore** (`src/core/vector_store.py`)
   - Manages storage and retrieval of document embeddings
   - Uses SQLite with `sqlite-vec` extension for efficient similarity search
   - Stores both document text/metadata and vector embeddings
   - Provides semantic search capabilities via cosine similarity

2. **EmbeddingService** (`src/core/embedding_service.py`)
   - Generates vector embeddings from text using Ollama
   - Uses the `nomic-embed-text` model by default
   - Supports both single-text and batch embedding operations

3. **Orchestrator Integration** (`src/orchestrator.py`)
   - Automatically initializes VectorStore on startup
   - Searches for similar tasks before decomposition
   - Injects context from similar tasks into prompts
   - Stores completed tasks with metadata in vector memory

## How It Works

### 1. Initialization

When the Orchestrator starts, it:
```python
orchestrator = Orchestrator(project_path="/path/to/project")
```

This automatically:
- Creates a `.memory/` directory in the project path
- Initializes a SQLite database at `.memory/task_vectors.db`
- Sets up the VectorStore with the EmbeddingService

### 2. Task Processing Flow

For each new task:

1. **Search Similar Tasks** (lines 48-56 in `orchestrator.py`):
   ```python
   similar_tasks = self.vector_store.search(user_request, k=3)
   ```
   - Embeds the user request using the EmbeddingService
   - Performs cosine similarity search in the vector database
   - Returns up to 3 most similar past tasks

2. **Inject Context** (lines 50-56):
   - Formats similar task information
   - Appends context to the original user request
   - Creates an "enriched request" with relevant historical context

3. **Decompose with Context** (line 77):
   ```python
   prd = self.agent.decompose(enriched_request, task_type)
   ```
   - The StoryAgent receives both the original request AND similar task context
   - This helps the agent make better decisions based on past successes

4. **Store Completed Task** (lines 119-133):
   - After task execution, combines request + response + metadata
   - Embeds the complete task information
   - Stores it in the vector database for future retrieval

### 3. Data Persistence

- **Database Location**: `<project_path>/.memory/task_vectors.db`
- **Schema**:
  - `documents` table: Stores text, metadata, and timestamps
  - `vec_documents` virtual table: Stores embeddings as FLOAT arrays
  - Linked via `doc_id` foreign key

- **Metadata Stored**:
  ```python
  {
      "task_name": "task_001",
      "task_type": "development",
      "success": True,
      "file_path": "/path/to/001_task.md"
  }
  ```

## Usage Examples

### Basic Usage (Automatic)

The RAG system works automatically - no manual intervention needed:

```python
# Just use the orchestrator normally
orchestrator = Orchestrator(project_path="./my-project")
await orchestrator.process_task_file("./tasks/001_feature.md")

# The system automatically:
# 1. Searches for similar past tasks
# 2. Injects relevant context
# 3. Stores the completed task
```

### Manual Vector Store Operations

You can also interact with the VectorStore directly:

```python
from src.core.vector_store import VectorStore
from src.core.embedding_service import EmbeddingService

# Initialize
embedding_service = EmbeddingService(model_name="nomic-embed-text")
vector_store = VectorStore(
    db_path="./memory/vectors.db",
    embedding_service=embedding_service
)

# Add documents
doc_id = vector_store.add_document(
    text="Implemented user authentication with JWT",
    metadata={"task": "auth-001", "success": True}
)

# Search for similar documents
results = vector_store.search("add login feature", k=5)
for result in results:
    print(f"Score: {result['score']:.3f}")
    print(f"Text: {result['text']}")
    print(f"Metadata: {result['metadata']}")
```

## Configuration

### Custom Database Path

```python
orchestrator = Orchestrator(
    project_path="/path/to/project",
    vector_db_path="/custom/path/vectors.db"
)
```

### Custom Embedding Model

```python
from src.core.embedding_service import EmbeddingService

embedding_service = EmbeddingService(model_name="custom-model")
vector_store = VectorStore(
    db_path="./vectors.db",
    embedding_service=embedding_service
)
```

### Adjusting Search Results

The number of similar tasks to retrieve can be adjusted:

```python
# In orchestrator.py, line 48:
similar_tasks = self.vector_store.search(user_request, k=5)  # Changed from k=3
```

## Testing

### Test Coverage

- **VectorStore**: 98% code coverage
- **EmbeddingService**: 40% coverage (mocked Ollama calls)
- **Total**: 22 passing tests

### Running Tests

```bash
# Run all vector memory tests
pytest tests/test_vector_store.py tests/test_orchestrator_vector_memory.py -v

# Run with coverage
coverage run -m pytest tests/test_vector_store.py tests/test_orchestrator_vector_memory.py
coverage report --include="src/core/vector_store.py,src/core/embedding_service.py"
```

### Verification Scripts

Two verification scripts are provided:

1. **Memory Structure Verification**:
   ```bash
   python3 verify_memory_structure.py
   ```
   - Verifies `.memory/` directory creation
   - Confirms database file structure
   - Tests basic add/search operations

2. **RAG Context Injection Verification**:
   ```bash
   python3 verify_rag_context.py
   ```
   - Verifies similar task search
   - Confirms context injection into prompts
   - Validates task storage after completion

## Performance Considerations

### Embedding Generation

- **Time**: ~100-500ms per embedding (depends on Ollama server)
- **Dimension**: 768 floats for `nomic-embed-text` model
- **Caching**: No caching currently implemented

### Vector Search

- **Algorithm**: Cosine similarity via `sqlite-vec`
- **Complexity**: O(n) for full scan (acceptable for small-medium datasets)
- **Time**: < 10ms for databases under 10,000 documents

### Storage

- **Text**: Stored as-is in SQLite TEXT columns
- **Embeddings**: Packed as binary FLOAT arrays
- **Size**: ~3KB per document (768 floats × 4 bytes + text + metadata)

### Scaling Considerations

For large-scale deployments (>10,000 tasks):
1. Consider using a dedicated vector database (Pinecone, Weaviate, Qdrant)
2. Implement batch embedding for efficiency
3. Add embedding caching to avoid re-embedding similar texts
4. Use approximate nearest neighbor (ANN) algorithms

## Troubleshooting

### Common Issues

1. **"Ollama embedding failed"**
   - Ensure Ollama is running: `ollama serve`
   - Pull the model: `ollama pull nomic-embed-text`
   - Check model name spelling

2. **"Module sqlite_vec not found"**
   - Install: `pip install sqlite-vec`
   - Ensure virtual environment is activated

3. **Empty search results**
   - Check if documents exist: `SELECT COUNT(*) FROM documents`
   - Verify embeddings were generated (check `vec_documents` table)
   - Try increasing `k` parameter in search

4. **Database locked errors**
   - Ensure proper cleanup: call `vector_store.close()`
   - Check for orphaned connections
   - Consider using WAL mode for concurrent access

## Future Enhancements

### Planned Improvements

1. **Embedding Cache**: Cache embeddings for frequently searched queries
2. **Metadata Filtering**: Filter search by task type, success status, date range
3. **Hybrid Search**: Combine vector similarity with keyword search (BM25)
4. **Batch Processing**: Optimize for bulk task imports
5. **Analytics Dashboard**: Visualize task relationships and patterns
6. **Auto-tuning**: Automatically adjust `k` based on result quality

### Advanced Features

1. **Reranking**: Use cross-encoder models for result reranking
2. **Query Expansion**: Automatically expand queries with synonyms
3. **Temporal Weighting**: Prefer recent tasks over old ones
4. **Success Weighting**: Boost results from successful tasks
5. **Multi-modal**: Support code snippets, diagrams, screenshots

## References

- **sqlite-vec**: https://github.com/asg017/sqlite-vec
- **Ollama**: https://ollama.ai/
- **nomic-embed-text**: https://huggingface.co/nomic-ai/nomic-embed-text-v1
- **RAG Pattern**: https://arxiv.org/abs/2005.11401

## License

See project LICENSE file.

---

**Last Updated**: 2024-01-15
**Version**: 1.0
**Status**: Production Ready ✓
