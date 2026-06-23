# Project Profile: MARIS (Multi-Agent Repository Intelligence System)

## Project Type
Local-first repository intelligence platform using Python, Tree-sitter, Ollama, and LangGraph.

## Architecture Decisions

### Language & Runtime
- **Primary Language**: Python 3.11+
- **Reason**: Rich ecosystem for LLM tooling, Tree-sitter bindings, and agent frameworks

### Core Technologies

#### Parsing
- **Choice**: Tree-sitter
- **Rationale**: Mature, multi-language, incremental parsing
- **Current Support**: Python (fully implemented)
- **Planned Support**: Java, Scala, Kotlin, JavaScript, TypeScript, Go, Rust, Shell (Bash)
- **Implementation**: Language-specific parsers inherit from `TreeSitterParser` base class

#### LLM Runtime
- **Choice**: Ollama
- **MVP Models**: Qwen3 8B, Gemma 3 12B
- **Recommended**: Qwen3 32B
- **Rationale**: Local-first, privacy-preserving, no external API dependencies

#### Embeddings
- **Choice**: nomic-embed-text (primary), bge-large (alternative)
- **Role**: Assist retrieval, not primary mechanism
- **Rationale**: Embeddings complement symbol-based retrieval

#### Agent Framework
- **Choice**: LangGraph
- **Rationale**: Explicit workflows, state management, deterministic over autonomous
- **Pattern**: Specialized agents sharing common knowledge layer

#### Storage
- **Metadata Store**: DuckDB (symbols, files, relationships, commits, documentation)
- **Vector Store**: LanceDB (embeddings, semantic search)
- **Future**: KuzuDB or Neo4j for graph queries (post-MVP)

### Design Patterns

#### Retrieval Strategy
- **Primary**: AST-based symbol chunking
- **Secondary**: Vector similarity search
- **Pattern**: Symbol expansion → Dependency expansion → Context assembly
- **Anti-pattern**: Generic 1000-token chunking (loses structure)

#### Agent Design
- **Pattern**: Single Responsibility Principle per agent
- **Anti-pattern**: One large autonomous agent
- **Coordination**: Shared Repository Knowledge Layer

#### Incremental Processing
- **Pattern**: Filesystem watcher + git diff for change detection
- **Rule**: Re-index only changed files, never full rebuild

### Code Organization

```
maris/
├── agents/           # Specialized agents
├── core/            # Domain models and interfaces
├── indexing/        # Tree-sitter parsing and extraction
├── knowledge/       # Repository Knowledge Layer
├── storage/         # DuckDB and LanceDB adapters
├── retrieval/       # Retrieval pipeline
└── utils/           # Shared utilities
```

### Naming Conventions
- **Modules**: lowercase_with_underscores
- **Classes**: PascalCase
- **Functions/Methods**: snake_case
- **Constants**: UPPER_CASE
- **Private**: _leading_underscore

### Testing Strategy
- **Framework**: pytest
- **Coverage Target**: >80% for core logic
- **Pattern**: Unit tests for domain logic, integration tests for storage/retrieval
- **Test Data**: Small synthetic repositories for reproducibility

### Documentation Standards
- **Docstrings**: Google style
- **Type Hints**: Required for all public APIs
- **README**: Architecture overview, setup, usage examples
- **Specs**: Behavior specifications in `.codex/specs/`

## MVP Scope

### Phase 1: Foundation
1. Repository Indexing Agent
2. Repository Knowledge Layer interface
3. Storage layer (DuckDB + LanceDB)

### Phase 2: Intelligence
4. Documentation Agent
5. Q&A Agent

### Phase 3: Analysis (Post-MVP)
6. Impact Analysis Agent
7. Git Archaeology Agent

## Non-Goals
- Code generation or modification
- Autonomous PR creation
- Cloud-based processing
- External API dependencies

## Success Criteria
1. Incremental repository indexing works
2. Symbol queries are accurate
3. Documentation generation is automatic
4. Q&A answers are grounded in repository knowledge
5. Entire workflow runs locally
6. Zero external API dependencies

## Open Questions
- [x] Specific Tree-sitter grammar versions to pin → Resolved: Using >=0.21.0 for all grammars (see multi-language-parser-support.md)
- [ ] DuckDB schema design for symbol relationships
- [ ] LanceDB index configuration for optimal retrieval
- [x] LangGraph workflow patterns for agent coordination → Resolved: All agents migrated to LangGraph with explicit state management

## Decision Log
| Date | Decision | Rationale | Scope |
|------|----------|-----------|-------|
| 2026-06-21 | Python 3.11+ as primary language | Rich LLM/ML ecosystem, Tree-sitter bindings | Project-wide |
| 2026-06-21 | DuckDB for metadata, LanceDB for vectors | Embedded, local-first, performant | Storage layer |
| 2026-06-21 | AST-based symbol chunking over generic chunking | Preserves code structure and semantics | Retrieval layer |
| 2026-06-22 | LangGraph migration for all agents | Explicit state management, testable workflows | Agent layer |
| 2026-06-23 | Multi-language parser support via tree-sitter | Leverage existing infrastructure, 9 languages planned | Parsing layer |
| 2026-06-21 | LangGraph for agent orchestration | Explicit workflows over autonomous loops | Agent layer |
| 2026-06-21 | DuckDB for metadata, LanceDB for vectors | Embedded, local-first, performant | Storage layer |
| 2026-06-21 | AST-based symbol chunking over generic chunking | Preserves code structure and semantics | Retrieval layer |
