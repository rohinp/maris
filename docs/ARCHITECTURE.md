# MARIS Architecture

## System Overview

MARIS is a local-first, multi-agent repository intelligence system designed to help developers understand and navigate source code without sending data to external services.

## Core Principles

### 1. Retrieval First
Quality answers depend on quality retrieval. MARIS prioritizes:
- AST-aware indexing over generic chunking
- Symbol-aware retrieval over text similarity
- Dependency-aware context over isolated snippets

### 2. Code as a Graph
Repositories are graphs of interconnected symbols, not flat file collections. MARIS maintains:
- Symbol relationships (calls, imports, inheritance)
- Dependency chains
- Impact propagation paths

### 3. Local First
All processing happens locally:
- No external API calls
- No data leaves the machine
- Full privacy and control

### 4. Specialized Agents
Single-responsibility agents sharing a common knowledge layer:
- Indexing Agent: Parse and extract
- Documentation Agent: Generate docs
- Q&A Agent: Answer questions
- Impact Analysis Agent: Assess changes
- Git Archaeology Agent: Track evolution

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Repository Files                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Indexing Agent                            │
│  • Tree-sitter parsing                                       │
│  • Symbol extraction                                         │
│  • Dependency analysis                                       │
│  • Embedding generation                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Repository Knowledge Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Symbol Store │  │ Dependency   │  │ Vector Store │      │
│  │  (DuckDB)    │  │    Graph     │  │  (LanceDB)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Specialized Agents                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │Documentation │  │     Q&A      │  │   Impact     │      │
│  │    Agent     │  │    Agent     │  │   Analysis   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### Indexing Agent

**Responsibilities:**
- Parse source files using Tree-sitter
- Extract symbols (classes, functions, methods, etc.)
- Build dependency relationships
- Generate embeddings for semantic search
- Store structured data

**Technology:**
- Tree-sitter for parsing
- Language-specific grammars
- Incremental updates via filesystem watching

**Output:**
- Symbols in DuckDB
- Dependencies in DuckDB
- Embeddings in LanceDB

### Repository Knowledge Layer

**Purpose:**
Central abstraction for all repository intelligence operations.

**Interfaces:**

```python
class RepositoryKnowledgeService:
    # Symbol operations
    def find_symbol(name: str) -> List[Symbol]
    def get_symbol_by_id(id: str) -> Symbol

    # Dependency operations
    def find_callers(symbol: Symbol) -> List[Symbol]
    def find_callees(symbol: Symbol) -> List[Symbol]

    # Retrieval operations
    def retrieve_context(question: str) -> RetrievalContext
    def semantic_search(query: str) -> List[Symbol]

    # Impact analysis
    def impacted_symbols(symbol: Symbol) -> Set[Symbol]

    # History operations
    def get_symbol_history(symbol: Symbol) -> List[Commit]
```

**Storage:**
- **DuckDB**: Structured queries (symbols, relationships, commits)
- **LanceDB**: Vector similarity search (embeddings)

### Storage Layer

#### DuckDB Metadata Store

**Schema:**

```sql
-- Symbols table
CREATE TABLE symbols (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    language VARCHAR NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    signature TEXT,
    docstring TEXT,
    parent_id VARCHAR
);

-- Dependencies table
CREATE TABLE dependencies (
    id VARCHAR PRIMARY KEY,
    from_symbol_id VARCHAR NOT NULL,
    to_symbol_id VARCHAR NOT NULL,
    relationship_type VARCHAR NOT NULL
);

-- Files table
CREATE TABLE files (
    path VARCHAR PRIMARY KEY,
    language VARCHAR NOT NULL,
    last_indexed_at TIMESTAMP NOT NULL,
    line_count INTEGER,
    symbol_count INTEGER
);
```

**Indexes:**
- `idx_symbols_name` on `symbols(name)`
- `idx_symbols_file` on `symbols(file_path)`
- `idx_dependencies_from` on `dependencies(from_symbol_id)`
- `idx_dependencies_to` on `dependencies(to_symbol_id)`

#### LanceDB Vector Store

**Schema:**

```python
{
    "symbol_id": str,        # Foreign key to DuckDB
    "vector": List[float],   # 768-dimensional embedding
    "text": str,             # Original text
    "metadata": {
        "symbol_name": str,
        "type": str,
        "file": str,
        "language": str
    }
}
```

**Embedding Model:**
- Primary: `nomic-embed-text` (768 dimensions)
- Alternative: `bge-large`

### Retrieval Pipeline

```
User Question
     │
     ▼
Vector Search (semantic similarity)
     │
     ▼
Symbol Expansion (get full symbol details)
     │
     ▼
Dependency Expansion (traverse call graph)
     │
     ▼
Context Assembly (build LLM context)
     │
     ▼
LLM Reasoning (Ollama)
     │
     ▼
Answer
```

**Key Features:**
- Combines semantic search with graph traversal
- Expands context using dependency relationships
- Prioritizes relevant symbols over arbitrary chunks

## Data Flow

### Indexing Flow

```
1. File Change Detection
   ├─ Filesystem watcher
   └─ Git diff

2. Parse File
   ├─ Tree-sitter AST
   └─ Language-specific grammar

3. Extract Symbols
   ├─ Classes, functions, methods
   ├─ Signatures and docstrings
   └─ Line ranges

4. Extract Dependencies
   ├─ Function calls
   ├─ Imports
   └─ Inheritance

5. Generate Embeddings
   ├─ Symbol signature + docstring
   └─ Ollama nomic-embed-text

6. Store Data
   ├─ Symbols → DuckDB
   ├─ Dependencies → DuckDB
   └─ Embeddings → LanceDB
```

### Query Flow

```
1. User Question
   └─ Natural language query

2. Semantic Search
   ├─ Generate query embedding
   └─ LanceDB similarity search

3. Symbol Retrieval
   ├─ Get top-k symbols
   └─ Fetch full details from DuckDB

4. Context Expansion
   ├─ Find callers/callees
   ├─ Traverse dependencies
   └─ Gather related symbols

5. Context Assembly
   ├─ Format for LLM
   └─ Include code snippets

6. LLM Reasoning
   ├─ Ollama (Qwen/Gemma)
   └─ Generate answer

7. Return Response
   └─ Formatted answer with references
```

## Technology Stack

### Core Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.11+ | Implementation |
| Parsing | Tree-sitter | AST parsing |
| Metadata Store | DuckDB | Structured queries |
| Vector Store | LanceDB | Similarity search |
| LLM Runtime | Ollama | Local inference |
| Agent Framework | LangGraph | Workflow orchestration |

### Language Support (MVP)

- Scala (`.scala`)
- Java (`.java`)
- Python (`.py`)
- TypeScript (`.ts`, `.tsx`)

### LLM Models

**MVP:**
- Qwen2.5 8B
- Gemma 3 12B

**Recommended:**
- Qwen2.5 32B

**Future:**
- Qwen2.5 72B
- DeepSeek R1 Distill

## Performance Characteristics

### Indexing Performance

| Metric | Target | Notes |
|--------|--------|-------|
| Parse rate | >100 files/sec | Small files |
| Symbol extraction | >1000 symbols/sec | |
| Embedding generation | >50 symbols/sec | Depends on Ollama |
| Full repo (10k files) | <10 minutes | Initial indexing |

### Query Performance

| Operation | Target | Notes |
|-----------|--------|-------|
| Symbol lookup | <10ms | DuckDB indexed query |
| Dependency traversal | <100ms | Depth 3 |
| Semantic search | <200ms | LanceDB vector search |
| Context retrieval | <500ms | Full pipeline |

## Scalability Considerations

### Storage

- **DuckDB**: Handles millions of symbols efficiently
- **LanceDB**: Scales to millions of embeddings
- **Disk Space**: ~1MB per 1000 symbols (approximate)

### Memory

- **Indexing**: ~500MB baseline + file content
- **Query**: ~1GB baseline + LLM model size
- **LLM Models**:
  - 8B: ~5GB RAM
  - 32B: ~20GB RAM
  - 72B: ~40GB RAM

### Incremental Updates

- Only re-index changed files
- Batch updates to reduce overhead
- Maintain indexing metadata for change detection

## Security & Privacy

### Local-First Design

- All data stays on local machine
- No external API calls required
- No telemetry or tracking

### Data Storage

- Databases stored locally
- No cloud synchronization
- User controls all data

### Access Control

- File system permissions
- No network exposure
- Single-user design

## Future Enhancements

### Phase 2 (Post-MVP)

- Impact Analysis Agent
- Git Archaeology Agent
- Test Suggestion Agent

### Phase 3

- Architecture Evolution Agent
- Cross-repository analysis
- Temporal queries

### Phase 4

- Graph database integration (KuzuDB/Neo4j)
- Advanced dependency analysis
- Code evolution tracking

## Design Decisions

### Why Tree-sitter?

- Mature ecosystem
- Multi-language support
- Incremental parsing
- Existing grammars

### Why DuckDB?

- Embedded database
- SQL interface
- Excellent performance
- No server required

### Why LanceDB?

- Embedded vector database
- Fast similarity search
- Arrow-native
- No server required

### Why Ollama?

- Local inference
- Easy model management
- Good performance
- Active development

### Why LangGraph?

- Explicit workflows
- State management
- Tool orchestration
- Deterministic execution

## References

- [Project Profile](../.codex/project-profile.md)
- [Repository Knowledge Layer Spec](../.codex/specs/repository-knowledge-layer.md)
- [Indexing Agent Spec](../.codex/specs/indexing-agent.md)
- [Getting Started Guide](./GETTING_STARTED.md)