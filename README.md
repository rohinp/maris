# Local Multi-Agent Repository Intelligence System

## Vision

Build a fully local, privacy-first repository intelligence platform that helps developers understand, navigate, document, analyze, and reason about source code.

The goal is **not** to compete with cloud coding assistants such as Claude Code, Cursor, GitHub Copilot, or OpenAI Codex.

The system will:

* Run locally
* Use local LLMs
* Never require source code to leave the machine
* Focus on understanding rather than code generation
* Be language-aware through AST parsing
* Maintain a continuously updated repository knowledge graph
* Support multiple specialized agents

The primary objective is to become a "repository expert" capable of answering questions, generating documentation, explaining architecture, performing impact analysis, and understanding code evolution over time.

---

# Core Principles

## 1. Retrieval First

The quality of answers depends on retrieval quality.

The system should prioritize:

* AST-aware indexing
* Symbol-aware retrieval
* Dependency-aware retrieval

over generic vector similarity search.

---

## 2. Code is a Graph

A repository is not a collection of files.

A repository is a graph of:

* Packages
* Modules
* Classes
* Traits
* Interfaces
* Functions
* Methods
* Dependencies
* Imports
* Call relationships

The system should maintain this graph as a first-class entity.

---

## 3. Local First

All processing should happen locally:

* Parsing
* Embedding generation
* Retrieval
* Reasoning

No external APIs are required.

---

## 4. Specialized Agents

Each agent should have a single responsibility.

Avoid creating one large autonomous agent.

Instead create multiple focused agents sharing a common knowledge layer.

---

# High-Level Architecture

```text
Repository

    │

    ▼

Indexing Agent

    │

    ▼

Repository Knowledge Layer

    ├── Symbol Store
    ├── Dependency Graph
    ├── Vector Store
    ├── Commit History
    └── Metadata

    │

    ▼

Agents

    ├── Documentation Agent
    ├── Q&A Agent
    ├── Impact Analysis Agent
    ├── Git Archaeology Agent
    └── Future Agents
```

---

# Technology Choices

## Parsing

Use Tree-sitter.

Reason:

* Mature ecosystem
* Multi-language support
* Incremental parsing
* Existing grammars

Supported languages for MVP:

* Scala
* Java
* Python
* TypeScript

Future:

* Go
* Rust
* Kotlin
* C++
* C#

---

## Local LLM Runtime

Use Ollama.

Candidate models:

### MVP

* Qwen3 8B
* Gemma 3 12B

### Recommended

* Qwen3 32B

### Future

* Qwen3 72B
* DeepSeek R1 Distill

---

## Embeddings

Candidate models:

* nomic-embed-text
* bge-large
* gte-large

Embeddings should only assist retrieval.

They must not become the primary retrieval mechanism.

---

## Agent Orchestration

Use LangGraph.

Reason:

* Explicit workflows
* State management
* Tool orchestration
* Easy future expansion

Avoid autonomous agent loops.

Prefer deterministic workflows.

---

## Storage

### Metadata Store

DuckDB

Stores:

* symbols
* files
* relationships
* commits
* documentation

---

### Vector Store

LanceDB

Stores:

* embeddings
* semantic search index

Alternative:

* Qdrant

---

### Future Graph Database

Optional.

Candidates:

* KuzuDB
* Neo4j

Do not introduce graph databases during MVP.

---

# Repository Knowledge Layer

This is the most important component.

All agents interact through this layer.

Responsibilities:

* Symbol lookup
* Dependency traversal
* Semantic retrieval
* Impact analysis support
* Commit history lookup

Example interface:

```scala
trait RepositoryKnowledgeService {

  def findSymbol(name: String)

  def findCallers(symbol: Symbol)

  def findCallees(symbol: Symbol)

  def retrieveContext(question: String)

  def impactedSymbols(symbol: Symbol)

}
```

This layer becomes the foundation of the entire platform.

---

# MVP

## Agent 1: Repository Indexing Agent

### Responsibilities

Convert source code into structured knowledge.

### Workflow

Repository

↓

Tree-sitter AST

↓

Symbol Extraction

↓

Dependency Extraction

↓

Embedding Generation

↓

Storage

### Extracted Metadata

For every symbol:

```json
{
  "symbol": "GraphRunner.retryExecuteNode",
  "type": "method",
  "file": "GraphRunner.scala",
  "language": "scala",
  "calls": [
    "attemptExecuteNode"
  ]
}
```

### Incremental Updates

✅ **Implemented via Git Agent**

The system now includes a Git Agent that:

* Detects changes via `git diff`
* Tracks the last indexed commit
* Re-indexes only changed files
* Supports incremental indexing via CLI: `maris index --incremental`

This dramatically improves indexing performance for large repositories.

See [Git Agent Documentation](docs/GIT_AGENT.md) for details.

---

## Agent 2: Documentation Agent

### Responsibilities

Generate repository documentation.

### Output

* Architecture overview
* Component documentation
* Module descriptions
* Dependency diagrams
* Data flow descriptions

### Important Rule

Never generate documentation directly from raw files.

Always use indexed symbols and repository graph data.

---

## Agent 3: Repository Q&A Agent

### Responsibilities

Answer questions about code.

Examples:

* Explain GraphRunner
* How does retry work?
* Where is reducer used?
* What happens when training starts?

### Workflow

Question

↓

Retrieve Symbols

↓

Expand Dependencies

↓

Build Context

↓

LLM Reasoning

↓

Answer

### Goal

Context should consist of relevant symbols.

Not arbitrary chunks.

---

# Future Roadmap

## Agent 4: Impact Analysis Agent

Purpose:

Determine what may be affected by a code change.

Example:

Developer modifies:

```scala
Reducer.reduce()
```

Agent performs:

* caller traversal
* callee traversal
* dependency analysis
* test discovery

Output:

* impacted modules
* potentially affected tests
* possible edge cases

---

## Agent 4: Git Agent

✅ **Implemented** (June 2026)

Purpose:

Track repository changes and enable incremental indexing.

Capabilities:

* Detect changes since last indexing
* Categorize changes (added/modified/deleted/renamed)
* Enable efficient incremental re-indexing
* Track commit history

See [Git Agent Documentation](docs/GIT_AGENT.md) for details.

---

## Agent 5: Impact Analysis Agent

📋 **Planned** - Post-MVP Enhancement

Purpose:

Analyze the impact of code changes and help developers understand what will be affected by modifications.

Capabilities:

* Dependency analysis (what depends on this?)
* Test discovery (what tests cover this?)
* Edge case detection (what should I handle?)
* Breaking change detection (what will break?)
* Pattern analysis (similar implementations)

Integration:

* Orchestrator automatically routes impact-related questions
* Explicit CLI: `maris impact analyze --symbol "SymbolName"`
* Implicit via ask: `maris ask "What will be affected if I change X?"`

See [Impact Analysis Agent Specification](.codex/specs/impact-analysis-agent.md) for details.

---

## Agent 6: Git Archaeology Agent

Purpose:

Understand historical code evolution.

Questions:

* When was this bug introduced?
* Who changed this logic?
* Why was this method added?

Data Sources:

* git log
* git blame
* commit metadata

Capabilities:

* commit timeline generation
* code evolution summaries
* regression identification

---

## Agent 6: Test Suggestion Agent

Purpose:

Suggest tests based on modifications.

Inputs:

* changed symbols
* dependency graph
* historical bugs

Outputs:

* missing tests
* edge cases
* regression scenarios

---

## Agent 7: Architecture Evolution Agent

Purpose:

Track architecture changes over time.

Capabilities:

* detect coupling growth
* detect module boundaries
* identify hotspots
* detect architectural drift

---

# Retrieval Strategy

## Do Not

Generic chunking:

```text
1000 token chunks
```

This loses structure.

---

## Preferred

AST-based symbol chunking.

Example:

```text
Package

  ├── Class

        ├── Method

        ├── Method

        └── Method
```

Each symbol becomes a retrievable unit.

---

## Retrieval Pipeline

Question

↓

Vector Search

↓

Symbol Expansion

↓

Dependency Expansion

↓

Context Assembly

↓

Reasoning

This combines semantic search with graph traversal.

---

# Non Goals

The system is NOT intended to:

* Generate PRs
* Automatically modify code
* Replace developers
* Act autonomously
* Execute arbitrary repository changes

The system is designed to help developers understand software.

---

# Success Criteria

MVP is successful when:

1. ✅ Repository indexing works incrementally (Git Agent)
2. ✅ Symbols can be queried accurately
3. ✅ Documentation can be generated automatically
4. ✅ Q&A answers are grounded in repository knowledge
5. ✅ Entire workflow runs locally
6. ✅ No external API dependencies are required

**MVP Complete!** All success criteria have been met.

---

# Long-Term Goal

Become a local repository intelligence platform capable of understanding large codebases as well as experienced maintainers, while remaining privacy-first, language-aware, and fully developer-controlled.

