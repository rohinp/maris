# Indexing Agent Specification

Last updated: 2026-06-24

Status: Active

## Purpose
Convert source code into structured knowledge by parsing repositories, extracting symbols, building dependency graphs, generating embeddings, and storing results in the Repository Knowledge Layer.

## Responsibilities
1. Parse source files using Tree-sitter
2. Extract symbols (classes, functions, methods, etc.)
3. Build dependency relationships (calls, imports, references)
4. Generate embeddings for semantic search
5. Store structured data in DuckDB and LanceDB
6. Support incremental updates (only re-index changed files)

## Workflow

```
Repository Files
    ↓
Tree-sitter Parsing
    ↓
Symbol Extraction
    ↓
Dependency Extraction
    ↓
Embedding Generation
    ↓
Storage (DuckDB + LanceDB)
```

## Input
- Repository root path
- List of file paths to index (or all files for initial indexing)
- Language configuration (which languages to support)

## Output
- Structured symbol data in DuckDB
- Embeddings in LanceDB
- Indexing statistics (files processed, symbols extracted, errors)

## Symbol Extraction Rules

### Scala
- **Packages**: `package` declarations
- **Classes**: `class`, `case class`, `abstract class`
- **Traits**: `trait` declarations
- **Objects**: `object` declarations
- **Methods**: `def` declarations
- **Fields**: `val`, `var` declarations
- **Functions**: Top-level `def` in objects

### Java
- **Packages**: `package` declarations
- **Classes**: `class`, `abstract class`
- **Interfaces**: `interface` declarations
- **Methods**: Method declarations
- **Fields**: Field declarations
- **Constructors**: Constructor declarations

### Python
- **Modules**: File-level scope
- **Classes**: `class` declarations
- **Functions**: `def` declarations (top-level and methods)
- **Variables**: Top-level assignments
- **Constants**: UPPER_CASE assignments

### TypeScript
Status: Planned. TypeScript extensions are mapped in `ParserFactory`, but no TypeScript parser is currently registered.

- **Modules**: File-level scope
- **Classes**: `class` declarations
- **Interfaces**: `interface` declarations
- **Functions**: `function` declarations and arrow functions
- **Methods**: Class method declarations
- **Types**: `type` aliases

## Dependency Extraction Rules

### Call Relationships
- Method invocations: `object.method()`
- Function calls: `function()`
- Constructor calls: `new Class()`

### Import Relationships
- Scala: `import package.Class`
- Java: `import package.Class;`
- Python: `import module`, `from module import symbol`
- TypeScript: `import { symbol } from 'module'`

### Inheritance Relationships
- Scala: `extends`, `with`
- Java: `extends`, `implements`
- Python: `class Child(Parent)`
- TypeScript: `extends`, `implements`

## Embedding Strategy

### What to Embed
1. **Symbol signature + docstring** (if present)
2. **Symbol name + context** (parent class, file path)
3. **Symbol body** (for small functions/methods <50 lines)

### Embedding Format
```python
{
    "symbol_id": "unique_id",
    "text": "class GraphRunner { def retryExecuteNode(...) { ... } }",
    "metadata": {
        "symbol_name": "GraphRunner.retryExecuteNode",
        "type": "method",
        "file": "GraphRunner.scala",
        "language": "scala"
    }
}
```

### Embedding Model
- Primary: `nomic-embed-text` via Ollama
- Dimension: 768
- Batch size: 32 symbols at a time

## Incremental Indexing

✅ **Implemented via Git Agent** (June 2026)

### Change Detection
1. ✅ **Git diff**: Compare working tree with last indexed commit (IMPLEMENTED)
   - Uses `git diff --name-status` to detect changes
   - Tracks last indexed commit in `.maris/last_commit`
   - Categorizes files: added, modified, deleted, renamed
2. **Filesystem watcher**: Monitor file changes in real-time (FUTURE)
3. **Timestamp comparison**: Check file modification times (FUTURE)

### Update Strategy
1. ✅ Detect changed files using GitAgent
2. ✅ Delete old symbols from changed files
3. ✅ Re-parse and extract symbols from changed files
4. ✅ Update dependency relationships
5. ✅ Regenerate embeddings for changed symbols
6. ✅ Update storage
7. ✅ Save current commit hash after successful indexing

### Optimization
- ✅ Only re-index files that actually changed
- ✅ Batch updates to reduce storage overhead
- ✅ Maintain indexing metadata (last indexed commit in `.maris/last_commit`)
- ✅ ~100x performance improvement for typical changes (10 files vs 1000 files)

### CLI Usage
```bash
# Incremental indexing
maris index --incremental
maris index -i

# Full indexing
maris index src/ --recursive
```

### Implementation Details
See [Git Agent Documentation](../../docs/GIT_AGENT.md) for complete details.

## Storage Schema

### DuckDB Tables

#### symbols
```sql
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
    parent_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_symbols_file ON symbols(file_path);
CREATE INDEX idx_symbols_type ON symbols(type);
```

#### dependencies
```sql
CREATE TABLE dependencies (
    id VARCHAR PRIMARY KEY,
    from_symbol_id VARCHAR NOT NULL,
    to_symbol_id VARCHAR NOT NULL,
    relationship_type VARCHAR NOT NULL, -- 'calls', 'imports', 'extends', 'implements'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (to_symbol_id) REFERENCES symbols(id)
);

CREATE INDEX idx_dependencies_from ON dependencies(from_symbol_id);
CREATE INDEX idx_dependencies_to ON dependencies(to_symbol_id);
```

#### files
```sql
CREATE TABLE files (
    path VARCHAR PRIMARY KEY,
    language VARCHAR NOT NULL,
    last_indexed_at TIMESTAMP NOT NULL,
    last_modified_at TIMESTAMP NOT NULL,
    line_count INTEGER,
    symbol_count INTEGER
);
```

#### indexing_metadata
```sql
CREATE TABLE indexing_metadata (
    key VARCHAR PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### LanceDB Schema
```python
{
    "symbol_id": str,        # Foreign key to DuckDB symbols.id
    "vector": List[float],   # 768-dimensional embedding
    "text": str,             # Original text that was embedded
    "metadata": {
        "symbol_name": str,
        "type": str,
        "file": str,
        "language": str
    }
}
```

## Error Handling

### Parse Errors
- Log file path and error details
- Skip file and continue with others
- Store error in `indexing_errors` table for review

### Embedding Errors
- Retry up to 3 times with exponential backoff
- Fall back to empty embedding if all retries fail
- Log warning for manual review

### Storage Errors
- Rollback transaction on failure
- Retry entire batch once
- Raise exception if retry fails (critical error)

## Performance Targets
- Parse rate: >100 files/second (small files)
- Symbol extraction: >1000 symbols/second
- Embedding generation: >50 symbols/second (depends on Ollama)
- Full repository index (10k files): <10 minutes

## Configuration

### Supported Languages
```python
SUPPORTED_LANGUAGES = {
    "scala": {
        "extensions": [".scala"],
        "tree_sitter_grammar": "tree-sitter-scala"
    },
    "java": {
        "extensions": [".java"],
        "tree_sitter_grammar": "tree-sitter-java"
    },
    "python": {
        "extensions": [".py"],
        "tree_sitter_grammar": "tree-sitter-python"
    },
}
```

Planned extensions are also mapped in `ParserFactory` for Kotlin, JavaScript, TypeScript, Go, Bash, and Rust. Indexing should use `ParserFactory.get_implemented_extensions()` so planned languages are not presented as currently indexable.

### Exclusions
```python
EXCLUDED_PATTERNS = [
    "*/node_modules/*",
    "*/target/*",
    "*/build/*",
    "*/.git/*",
    "*/dist/*",
    "*/__pycache__/*",
    "*.min.js",
    "*.bundle.js"
]
```

## API Interface

### IndexingAgent
```python
class IndexingAgent:
    def index_repository(self, repo_path: str) -> IndexingResult:
        """Perform full repository indexing"""

    def index_files(self, file_paths: List[str]) -> IndexingResult:
        """Index specific files (for incremental updates)"""

    def start_watch_mode(self, repo_path: str) -> None:
        """Start filesystem watcher for real-time indexing"""

    def get_indexing_status(self) -> IndexingStatus:
        """Get current indexing progress and statistics"""
```

### IndexingResult
```python
@dataclass
class IndexingResult:
    files_processed: int
    symbols_extracted: int
    dependencies_found: int
    embeddings_generated: int
    errors: List[IndexingError]
    duration_seconds: float
```

## Testing Strategy

### Unit Tests
- Symbol extraction for each language
- Dependency detection accuracy
- Incremental update logic
- Error handling and recovery

### Integration Tests
- Full repository indexing
- Storage consistency
- Embedding generation pipeline
- Watch mode functionality

### Test Data
- Small synthetic repositories for each language
- Known symbol counts and relationships
- Edge cases (empty files, parse errors, large files)

## Acceptance Criteria
- [x] Parse all implemented MVP languages (Scala, Java, Python)
- [ ] TypeScript parser implemented and registered
- [x] Extract symbols with >95% accuracy
- [x] Build dependency graph correctly
- [x] Generate embeddings for all symbols
- [x] Store data in DuckDB and LanceDB
- [x] Support incremental updates (Git Agent)
- [x] Handle errors gracefully
- [x] Meet performance targets
- [x] Pass all unit and integration tests

**Status**: ✅ MVP Complete (June 2026)

## Future Enhancements
- [ ] Support for Go, Rust, Kotlin, C++, C#
- [ ] Parallel processing for large repositories
- [ ] Smart re-indexing (only affected symbols)
- [ ] Symbol resolution across files
- [ ] Type inference for dynamic languages
