# MARIS Project Walkthrough

This guide explains the main design of MARIS for a beginner Python developer.
It focuses on four questions:

1. How chunking and embeddings work
2. How agents are implemented with LangGraph
3. How the orchestrator coordinates the agents
4. Why MARIS has multiple agents instead of one large agent

## Mental Model

MARIS turns a local repository into a searchable knowledge base.

At a high level:

```text
CLI command
  -> OrchestratorAgent
  -> Specialized agent
  -> Repository knowledge layer
  -> DuckDB metadata + LanceDB vectors
  -> Result shown by CLI
```

The important idea is that MARIS is local-first. Source code is parsed locally,
embeddings are generated through local Ollama, and repository data is stored
locally under `.maris/` by default.

## 1. Chunking And Embedding Strategy

### MARIS Does Symbol-Level Chunking

Many RAG systems split files into fixed-size text chunks, for example every
500 or 1,000 tokens. MARIS does something more code-aware.

Instead of arbitrary chunks, MARIS parses source files and extracts symbols:

- classes
- functions
- methods
- interfaces
- constants
- modules
- Markdown/config sections where supported by parsers

The core model is `Symbol` in `src/maris/core/models.py`.

```python
@dataclass
class Symbol:
    id: str
    name: str
    type: SymbolType
    file_path: str
    language: str
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

So the "chunk" in MARIS is usually a meaningful code unit, not an arbitrary
piece of text.

### Why Symbol Chunks Instead Of Fixed-Size Text Chunks?

Symbol-level chunking is a good fit for repository intelligence because users
usually ask questions like:

- "How does `IndexingAgent` work?"
- "Where is `detect_changes` used?"
- "What tests cover this method?"
- "What breaks if I change this function?"

Those questions map naturally to symbols and relationships between symbols.

Fixed-size chunks are simpler, but they have drawbacks for code:

- A function can be split across chunks.
- One chunk can contain unrelated parts of multiple functions.
- Search results may point to a vague text area instead of a specific symbol.
- Impact analysis is harder because dependency relationships are not explicit.

MARIS chooses symbol chunks because they preserve code structure.

### Parsing Flow

The indexing flow lives in `src/maris/agents/indexing_agent.py`.

The LangGraph workflow is built in `_build_graph()`:

```python
workflow.add_node("scan_files", self._scan_files)
workflow.add_node("parse_files", self._parse_files)
workflow.add_node("store_symbols", self._store_symbols)
workflow.add_node("generate_embeddings", self._generate_embeddings)
workflow.add_node("store_embeddings", self._store_embeddings)
workflow.add_node("assess_result", self._assess_result)
```

The flow is:

```text
scan_files
  -> parse_files
  -> store_symbols
  -> generate_embeddings
  -> store_embeddings
  -> assess_result
```

`scan_files` finds files that can be indexed. It uses
`collect_source_files()`, which applies parser support rules and excludes
directories like `.venv`, `node_modules`, `target`, `build`, and `.maris`.

`parse_files` reads each source file and calls `_extract_symbols_simple()`.
Despite the method name, it uses `ParserFactory` and Tree-sitter parsers:

```python
parser = ParserFactory.get_parser(file_path)
tree = parser.parse_file(file_path, content)
symbols = parser.extract_symbols(tree, file_path, content)
```

`ParserFactory` lives in `src/maris/indexing/parser_factory.py`. It maps file
extensions to parser classes. For example:

```python
".py": "PythonParser",
".java": "JavaParser",
".ts": "TypeScriptParser",
".md": "MarkdownParser",
```

Each parser inherits from `TreeSitterParser` in `src/maris/indexing/parser.py`.
The base parser defines common helpers for parsing files, reading node text,
getting line numbers, and generating stable symbol IDs.

### What Text Gets Embedded?

Embeddings are generated in `src/maris/embeddings/ollama_embeddings.py`.

For every symbol, MARIS builds a compact text representation:

```text
Symbol: IndexingAgent
Type: class
Language: python
Signature: ...
Documentation: ...
File: src/maris/agents/indexing_agent.py
```

Then it sends that text to Ollama:

```python
response = self.client.embeddings(model=self.model, prompt=text)
return response["embedding"]
```

This means the embedding represents the meaning of a symbol plus useful
metadata, not the full raw file contents.

### Why Embed Symbols Instead Of Entire Files?

Embedding entire files is easy, but it is usually too coarse:

- A file can contain many unrelated classes and functions.
- A search result for a file does not tell you which function was relevant.
- Large files may exceed embedding model context limits.

Embedding every tiny line is also not ideal:

- It creates too many vectors.
- It loses higher-level meaning.
- Search results can become noisy.

Symbol-level embedding is the middle ground:

- smaller than whole files
- more meaningful than arbitrary lines
- easier to connect back to code locations
- better for Q&A, documentation, and impact analysis

### Where Embeddings Are Stored

MARIS stores two kinds of data:

- DuckDB metadata: symbols, files, dependencies, repository stats
- LanceDB vectors: symbol embeddings for semantic search

The vector store is `src/maris/storage/vector_store.py`.

The LanceDB schema stores:

```python
symbol_id
vector
text
symbol_name
type
file
language
```

Search works like this:

1. Embed the user's query.
2. Search LanceDB for similar vectors.
3. Convert matching `symbol_id` values back into `Symbol` records from DuckDB.

That flow is implemented in `RepositoryKnowledgeImpl.semantic_search()` in
`src/maris/knowledge/repository_knowledge_impl.py`.

### Tradeoffs And Current Limitations

This strategy is pragmatic, but it has tradeoffs:

- It depends on parser quality. If a parser misses symbols, those symbols will
  not be searchable.
- It currently embeds symbol metadata and documentation, not necessarily full
  function bodies.
- The LanceDB schema is fixed at 768 dimensions, which matches the default
  `nomic-embed-text` model. Other embedding models may need schema changes if
  their vector size differs.
- Dependency extraction exists in the parser interface, but indexing currently
  reports `dependencies_found=0` in `IndexingResult`. More dependency storage
  work is still expected.

## 2. How Agents Are Implemented With LangGraph

### What Is A LangGraph Agent In This Project?

In MARIS, an agent is a Python class with:

- dependencies passed into `__init__`
- a `_build_graph()` method
- several node methods
- one or more public methods that create initial state and run the graph

Each graph uses a dictionary as state. Think of state as a shared notebook that
each node reads from and writes to.

Example from `IndexingAgent`:

```python
initial_state = {
    "file_paths": None,
    "files_to_index": [],
    "extracted_symbols": [],
    "embeddings": [],
    "error": None,
}

final_state = self.graph.invoke(initial_state)
```

Each node receives `state`, updates it, and returns it:

```python
def _scan_files(self, state: Dict[str, Any]) -> Dict[str, Any]:
    state["files_to_index"] = files_to_index
    state["total_files"] = len(files_to_index)
    return state
```

For a beginner Python developer, the simplest way to read these agents is:

1. Start with `_build_graph()`.
2. List the node names in order.
3. Read each `_node_name()` method.
4. Check the public method that calls `self.graph.invoke(...)`.

### IndexingAgent Walkthrough

File: `src/maris/agents/indexing_agent.py`

Purpose: convert files into indexed repository knowledge.

Workflow:

```text
scan_files
  -> parse_files
  -> store_symbols
  -> generate_embeddings
  -> store_embeddings
  -> assess_result
```

Main public methods:

- `index_repository()` runs a full scan.
- `index_files(file_paths)` indexes specific files.
- `get_indexing_status()` returns repository stats.
- `collect_source_files()` returns files that would be indexed.

Beginner reading path:

1. Read `index_repository()`.
2. See the initial state dictionary.
3. Follow the graph node order from `_build_graph()`.
4. Read `_scan_files()`, `_parse_files()`, and `_generate_embeddings()`.

### QAAgent Walkthrough

File: `src/maris/agents/qa_agent.py`

Purpose: answer natural-language questions about the repository.

Workflow:

```text
retrieve_context
  -> build_prompt
  -> generate_answer
  -> assess_confidence
```

The Q&A agent uses retrieval-augmented generation:

1. `retrieve_context` asks the knowledge service for relevant symbols.
2. `build_prompt` turns those symbols into a prompt.
3. `generate_answer` calls local Ollama chat.
4. `assess_confidence` estimates confidence from retrieved context quality.

The public method is:

```python
answer_question(question, max_symbols=10)
```

This returns an `Answer` object with:

- the answer text
- relevant symbols
- confidence
- source file paths

### DocumentationAgent Walkthrough

File: `src/maris/agents/documentation_agent.py`

Purpose: generate module or architecture documentation from indexed symbols.

Workflow:

```text
retrieve_symbols
  -> categorize_symbols
  -> find_dependencies
  -> generate_summary
  -> format_output
```

This agent is less about LLM reasoning and more about structured formatting.
It reads known symbols from the repository knowledge layer, groups them by
type, finds related files, and outputs a documentation object or Markdown.

### GitAgent Walkthrough

File: `src/maris/agents/git_agent.py`

Purpose: support incremental indexing.

Workflow:

```text
check_git_repo
  -> get_last_commit
  -> get_current_commit
  -> detect_changes
  -> categorize_files
```

This agent does not parse code. It answers a different question:

> Which files changed since the last successful index?

The orchestrator uses this during `maris index --incremental`.

### ImpactAnalysisAgent Walkthrough

File: `src/maris/agents/impact_analysis_agent.py`

Purpose: reason about the likely impact of changing a symbol or file.

Workflow:

```text
classify_analysis_type
  -> retrieve_target_symbol
  -> analyze_dependencies
  -> analyze_test_coverage
  -> detect_edge_cases
  -> generate_recommendations
  -> format_report
```

This agent uses repository relationships to answer questions like:

- who calls this symbol?
- which files may be affected?
- what tests cover it?
- what edge cases should be considered?
- could this be a breaking change?

## 3. How OrchestratorAgent Coordinates Everything

File: `src/maris/agents/orchestrator_agent.py`

The orchestrator is the entry point for repository tasks. It owns the
specialized agents and decides which one should handle a request.

### What The Orchestrator Creates

In `__init__`, it creates:

```python
self.qa_agent = QAAgent(...)
self.indexing_agent = IndexingAgent(...)
self.documentation_agent = DocumentationAgent(...)
self.git_agent = GitAgent(...)
self.impact_analysis_agent = ImpactAnalysisAgent(...)
```

So the orchestrator is not doing every task itself. It coordinates the agents
that know how to do each task.

### Orchestrator Workflow

The orchestrator graph has four nodes:

```text
classify_task
  -> route_to_agent
  -> execute_task
  -> format_response
```

### Step 1: classify_task

`_classify_task()` decides the task type.

If the caller passes an explicit task type, it uses that. For example:

```python
result = self.execute("Index repository", task_type="index")
```

If no explicit type is passed, it uses keyword checks. Examples:

- words like `impact`, `break`, `edge case` map to impact analysis
- words like `search` or `find symbol` map to search
- words like `index`, `scan`, `parse` map to indexing
- question words like `what`, `how`, `why` map to Q&A

### Step 2: route_to_agent

`_route_to_agent()` maps task types to agents:

```python
TaskType.QUESTION -> "qa_agent"
TaskType.SEARCH -> "repository_knowledge"
TaskType.INDEX -> "indexing_agent"
TaskType.INCREMENTAL_INDEX -> "indexing_agent"
TaskType.DOCUMENT -> "documentation_agent"
TaskType.STATUS -> "indexing_agent"
TaskType.CLEAR_INDEX -> "indexing_agent"
TaskType.GIT_CHANGES -> "git_agent"
TaskType.IMPACT_ANALYSIS -> "impact_analysis_agent"
```

Search is routed to `repository_knowledge` because semantic search is a direct
knowledge-layer operation, not a full agent workflow.

### Step 3: execute_task

`_execute_task()` calls the selected agent.

Examples:

For Q&A:

```python
result = self.qa_agent.answer_question(question, max_symbols=...)
```

For search:

```python
result = self.knowledge_service.semantic_search(query, limit=...)
```

For regular indexing:

```python
result = self.indexing_agent.index_files(file_paths)
```

For incremental indexing:

```python
changeset = self.git_agent.detect_changes()
result = self.indexing_agent.index_files(changeset.files_to_reindex)
```

That incremental flow is a good example of orchestration. It requires two
specialized agents:

1. `GitAgent` figures out which files changed.
2. `IndexingAgent` re-indexes those files.

### Step 4: format_response

`_format_response()` wraps everything in an `OrchestratorResult`:

```python
OrchestratorResult(
    task_type=task_type,
    success=success,
    result=result,
    agent_used=selected_agent,
    error=error,
    metadata={...},
)
```

That gives the CLI a consistent response shape no matter which agent actually
did the work.

### Convenience Methods

The orchestrator also exposes easier methods:

```python
ask_question(...)
search_symbols(...)
index_repository()
index_files(...)
collect_indexable_files(...)
generate_documentation(...)
get_status()
clear_index()
detect_git_changes()
incremental_index()
analyze_impact(...)
```

These methods still go through `execute()` for task routing in most cases.
They exist so other code does not need to manually build state dictionaries.

## How The CLI Uses The Orchestrator

File: `src/maris/cli/main.py`

The CLI creates all shared services in `MarisContext.initialize()`:

1. validate Ollama models
2. initialize DuckDB metadata storage
3. initialize LanceDB vector storage
4. initialize `OllamaEmbeddingService`
5. initialize `RepositoryKnowledgeImpl`
6. initialize `OrchestratorAgent`

After that, command handlers call `ctx.orchestrator`.

Examples:

```python
results = ctx.orchestrator.search_symbols(query, max_results)
```

```python
result = ctx.orchestrator.execute(
    request=question,
    task_type="question",
    max_symbols=max_symbols,
)
```

```python
files_to_index = ctx.orchestrator.collect_indexable_files(
    str(path),
    recursive=recursive,
)
```

This is the desired boundary: the CLI should handle user input and output, but
repository work should go through the orchestrator.

## 4. Why Multiple Agents?

MARIS has multiple agents because each task has a different workflow, different
inputs, and different failure modes.

### If MARIS Had One Large Agent

A single large agent would need to know how to:

- parse files
- generate embeddings
- store symbols
- search vectors
- call the LLM
- inspect Git history
- generate documentation
- analyze impact
- format reports

That would make the code harder to understand, test, and change.

### What Each Agent Owns

| Agent | Main responsibility | Does it use LLM? | Main data it touches |
| --- | --- | --- | --- |
| `IndexingAgent` | Parse files, extract symbols, create embeddings | No chat LLM; uses embedding model | Files, symbols, metadata, vectors |
| `QAAgent` | Answer natural-language questions | Yes | Retrieved symbols and Ollama chat |
| `DocumentationAgent` | Generate docs from indexed symbols | Mostly structured formatting | Symbols and dependencies |
| `GitAgent` | Detect changed files for incremental indexing | No | Git repository and `.maris/last_commit` |
| `ImpactAnalysisAgent` | Analyze callers, tests, edge cases, breaking changes | No direct chat LLM in current code | Symbols and dependency relationships |
| `OrchestratorAgent` | Choose and coordinate agents | No direct chat LLM | Task routing and result wrapping |

### How They Behave Differently

The agents behave differently because their graph nodes are different.

For example, `QAAgent` starts with retrieval and ends with LLM answer
generation:

```text
retrieve_context -> build_prompt -> generate_answer -> assess_confidence
```

`GitAgent` starts with Git repository checks and ends with changed file lists:

```text
check_git_repo -> get_last_commit -> get_current_commit -> detect_changes -> categorize_files
```

`IndexingAgent` starts with file scanning and ends with persisted symbols and
embeddings:

```text
scan_files -> parse_files -> store_symbols -> generate_embeddings -> store_embeddings
```

So "agent" does not mean "always call an LLM." In this project, an agent means:

> a focused workflow with clear state, clear steps, and a clear output.

## End-To-End Examples

### Example A: `maris index ./ -r`

```text
CLI index command
  -> ctx.orchestrator.collect_indexable_files(...)
  -> ctx.orchestrator.execute(task_type="index", file_paths=[...])
  -> OrchestratorAgent routes to IndexingAgent
  -> IndexingAgent parses files
  -> IndexingAgent stores symbols in DuckDB
  -> IndexingAgent generates embeddings with Ollama
  -> IndexingAgent stores vectors in LanceDB
  -> CLI prints indexing stats
```

### Example B: `maris ask "How does indexing work?"`

```text
CLI ask command
  -> ctx.orchestrator.execute(task_type="question")
  -> OrchestratorAgent routes to QAAgent
  -> QAAgent asks RepositoryKnowledgeImpl for context
  -> RepositoryKnowledgeImpl embeds the question
  -> LanceDB returns similar symbol IDs
  -> DuckDB loads Symbol records
  -> QAAgent builds a prompt
  -> Ollama chat model generates the answer
  -> CLI prints answer, confidence, and relevant symbols
```

### Example C: `maris index --incremental`

```text
CLI index command with --incremental
  -> ctx.orchestrator.execute(task_type="incremental_index")
  -> OrchestratorAgent asks GitAgent for changed files
  -> GitAgent returns GitChangeSet
  -> OrchestratorAgent passes changed files to IndexingAgent
  -> IndexingAgent deletes stale symbol/vector data for those files
  -> IndexingAgent re-parses and re-embeds changed files
  -> OrchestratorAgent saves current commit after successful indexing
  -> CLI prints incremental indexing stats
```

## Suggested Reading Order

If you are new to Python and LangGraph, read the code in this order:

1. `src/maris/core/models.py`
   Understand `Symbol`, `IndexingResult`, `RetrievalContext`, and `GitChangeSet`.

2. `src/maris/cli/main.py`
   See how the user command creates services and calls the orchestrator.

3. `src/maris/agents/orchestrator_agent.py`
   Follow `execute()`, then `_build_graph()`, then each node in order.

4. `src/maris/agents/indexing_agent.py`
   Follow `index_files()` and the indexing graph.

5. `src/maris/embeddings/ollama_embeddings.py`
   See exactly what text gets embedded.

6. `src/maris/knowledge/repository_knowledge_impl.py`
   See how semantic search and Q&A retrieval use stored embeddings.

7. `src/maris/agents/qa_agent.py`
   Follow how retrieved symbols become an LLM prompt.

8. `src/maris/agents/git_agent.py`
   Understand incremental indexing.

9. `src/maris/agents/documentation_agent.py` and
   `src/maris/agents/impact_analysis_agent.py`
   Read these after the core flow is clear.

## Short Summary

MARIS uses symbol-aware indexing rather than naive file chunking. It extracts
meaningful code units with parsers, embeds those symbols locally with Ollama,
stores metadata in DuckDB, stores vectors in LanceDB, and exposes repository
intelligence through specialized LangGraph agents.

The orchestrator is the supervisor. It receives a task, classifies it, chooses
the right specialized agent, runs it, and returns one consistent result shape
to the CLI.
