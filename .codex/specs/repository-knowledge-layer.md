# Repository Knowledge Layer Specification

Last updated: 2026-06-24

Status: Active

## Purpose
The Repository Knowledge Layer is the central abstraction that all agents use to interact with repository data. It provides a unified interface for symbol lookup, dependency traversal, semantic retrieval, and impact analysis.

## Core Responsibilities
1. Symbol lookup by name, type, or location
2. Dependency graph traversal (callers/callees)
3. Semantic retrieval via embeddings
4. Impact analysis support
5. Commit history lookup
6. Context assembly for LLM reasoning

## Interface Design

### Symbol Operations
```python
def find_symbol(name: str, language: Optional[str] = None) -> List[Symbol]
```
- Find symbols by name across the repository
- Optional language filter for disambiguation
- Returns all matching symbols with metadata

```python
def get_symbol_by_id(symbol_id: str) -> Optional[Symbol]
```
- Retrieve a specific symbol by unique identifier
- Returns None if not found

```python
def find_symbols_in_file(file_path: str) -> List[Symbol]
```
- Get all symbols defined in a specific file
- Ordered by line number

### Dependency Operations
```python
def find_callers(symbol: Symbol) -> List[Symbol]
```
- Find all symbols that call/reference the given symbol
- Traverses the dependency graph backwards

```python
def find_callees(symbol: Symbol) -> List[Symbol]
```
- Find all symbols called/referenced by the given symbol
- Traverses the dependency graph forwards

```python
def get_dependency_chain(from_symbol: Symbol, to_symbol: Symbol) -> List[List[Symbol]]
```
- Find all paths between two symbols
- Returns list of paths (each path is a list of symbols)
- Empty list if no path exists

### Retrieval Operations
```python
def retrieve_context(question: str, max_symbols: int = 10) -> RetrievalContext
```
- Retrieve relevant symbols for a given question
- Combines vector search with symbol expansion
- Returns structured context ready for LLM

```python
def semantic_search(query: str, limit: int = 20) -> List[Tuple[Symbol, float]]
```
- Pure vector similarity search
- Returns symbols with similarity scores
- Used as first stage in retrieval pipeline

### Impact Analysis Operations
```python
def impacted_symbols(symbol: Symbol, depth: int = 3) -> Set[Symbol]
```
- Find all symbols potentially impacted by changes to given symbol
- Traverses callers up to specified depth
- Returns set of unique symbols

```python
def impacted_files(symbol: Symbol) -> Set[str]
```
- Find all files potentially impacted by changes to given symbol
- Aggregates files from impacted_symbols

### History Operations
```python
def get_symbol_history(symbol: Symbol, limit: int = 50) -> List[Commit]
```
- Get commit history for a specific symbol
- Uses git blame and log data
- Returns commits that modified the symbol

```python
def find_symbols_changed_in_commit(commit_hash: str) -> List[Symbol]
```
- Get all symbols modified in a specific commit
- Useful for understanding change scope

## Data Models

### Symbol
```python
@dataclass
class Symbol:
    id: str                    # Unique identifier
    name: str                  # Symbol name
    type: SymbolType          # class, function, method, etc.
    file_path: str            # Relative path from repo root
    language: str             # scala, java, python, typescript
    start_line: int           # Starting line number
    end_line: int             # Ending line number
    signature: Optional[str]  # Function/method signature
    docstring: Optional[str]  # Documentation if present
    parent_id: Optional[str]  # Parent symbol (e.g., class for method)
    metadata: Dict[str, Any]  # Additional language-specific data
```

### SymbolType
```python
class SymbolType(Enum):
    PACKAGE = "package"
    MODULE = "module"
    CLASS = "class"
    TRAIT = "trait"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    FIELD = "field"
    VARIABLE = "variable"
    CONSTANT = "constant"
```

### RetrievalContext
```python
@dataclass
class RetrievalContext:
    primary_symbols: List[Symbol]      # Most relevant symbols
    expanded_symbols: List[Symbol]     # Dependency-expanded symbols
    related_files: List[str]           # Related file paths
    metadata: Dict[str, Any]           # Additional context

    def to_llm_context(self) -> str:
        """Format context for LLM consumption"""
```

### Commit
```python
@dataclass
class Commit:
    hash: str
    author: str
    timestamp: datetime
    message: str
    files_changed: List[str]
    symbols_changed: List[str]  # Symbol IDs
```

## Implementation Requirements

### Storage Backend
- DuckDB for structured queries (symbols, relationships, commits)
- LanceDB for vector similarity search
- Efficient joins between metadata and embeddings

### Caching Strategy
- Cache frequently accessed symbols in memory
- Cache dependency traversal results (TTL-based)
- Invalidate cache on repository updates

### Performance Targets
- Symbol lookup: <10ms
- Dependency traversal (depth 3): <100ms
- Semantic search: <200ms
- Context retrieval: <500ms

### Error Handling
- Return empty results rather than raising exceptions for not-found cases
- Log warnings for performance degradation
- Raise exceptions only for storage/connection failures

## Usage Examples

### Example 1: Q&A Agent
```python
# User asks: "How does GraphRunner retry work?"
context = knowledge.retrieve_context("GraphRunner retry mechanism")
# Returns symbols: GraphRunner.retryExecuteNode, attemptExecuteNode, etc.
# Agent uses context to generate answer
```

### Example 2: Impact Analysis
```python
# Developer modifies Reducer.reduce()
reducer_symbol = knowledge.find_symbol("Reducer.reduce")[0]
impacted = knowledge.impacted_symbols(reducer_symbol, depth=3)
# Returns all symbols that transitively call Reducer.reduce()
```

### Example 3: Documentation Generation
```python
# Generate docs for a package
package_symbols = knowledge.find_symbols_in_file("src/core/package.scala")
for symbol in package_symbols:
    callees = knowledge.find_callees(symbol)
    # Generate documentation with dependency information
```

## Future Enhancements
- [ ] Support for cross-repository symbol resolution
- [ ] Temporal queries (symbol state at specific commit)
- [ ] Similarity-based symbol clustering
- [ ] Automatic relationship inference from usage patterns

## Acceptance Criteria
- [x] All interface methods implemented in `RepositoryKnowledgeImpl`
- [x] Symbol lookup operations implemented
- [x] Dependency traversal operations implemented
- [x] Semantic retrieval operations implemented
- [x] Impact analysis support operations implemented
- [x] Repository stats and indexed-file checks implemented
- [ ] Unit tests for each operation are complete and explicitly mapped to this interface
- [ ] Integration tests with real repository data are complete
- [ ] Performance targets are measured and published
- [ ] Commit history behavior is fully backed by populated metadata in normal indexing flows
- [x] Documentation includes examples

## Current Gaps

- History methods exist on the interface and implementation, but their usefulness depends on commit metadata being populated by indexing workflows.
- Performance targets are specified but not backed by benchmark output in the repository.
- Packaging metadata is not yet the single source of runtime dependencies; use `requirements.txt` for reliable local setup.
