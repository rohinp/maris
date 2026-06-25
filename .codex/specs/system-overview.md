# System Overview Spec

Last updated: 2026-06-24

Status: Active

## Purpose

MARIS is a local-first repository intelligence platform. It helps developers index, search, document, and reason about source code without sending source files to external services.

Primary users:

- Developers working in local repositories
- Maintainers who need fast repository understanding and impact analysis
- Contributors who need symbol-aware context before changing code

Primary outcomes:

- Build a local repository knowledge layer from source files
- Answer repository questions from indexed symbols and dependencies
- Generate documentation from repository knowledge
- Analyze likely impact, edge cases, test coverage, and breaking changes
- Support incremental indexing from Git changes

## User Flows

| Flow | Actor | Trigger | Outcome | Status |
| --- | --- | --- | --- | --- |
| Full indexing | Developer | `maris index PATH --recursive` | Supported files are parsed, embedded, and stored locally | Implemented |
| Incremental indexing | Developer | `maris index --incremental` | Files changed since last indexed commit are re-indexed | Implemented |
| Symbol search | Developer | `maris search QUERY` | Matching indexed symbols are returned with scores | Implemented |
| Repository Q&A | Developer | `maris ask QUESTION` or `maris interactive` | Answer is generated from retrieved symbol context | Implemented |
| Symbol explanation | Developer | `maris explain SYMBOL` | Explanation and relevant symbols are shown | Implemented |
| File documentation | Developer | `maris document FILE --output PATH` | Markdown documentation is generated for one file | Implemented |
| Impact analysis | Developer | `maris impact ...` | Dependency, edge-case, test, or breaking-change report is generated | Implemented |
| Git archaeology | Developer | Historical question about a symbol | Timeline/evolution answer from Git history | Planned |

## Domain Rules And Edge Cases

| Rule/Edge Case | Expected Behavior | Source | Status |
| --- | --- | --- | --- |
| Local-first processing | Parsing, embeddings, storage, and reasoning use local resources by default | `AGENT.md`, README | Implemented |
| Generic agent guidance | Repository contributor instructions avoid dependencies on unavailable local skills or a specific assistant runtime | `AGENT.md`, README | Implemented |
| Ollama validation | CLI validates configured embedding, Q&A, and documentation models unless `--skip-validation` is used | `src/maris/cli/main.py` | Implemented |
| Project-local storage | CLI defaults to `.maris/` in current directory unless `MARIS_DATA_DIR` is set | `src/maris/cli/main.py` | Implemented |
| Non-incremental index without path | CLI reports an error and suggests `--incremental` | `src/maris/cli/main.py` | Implemented |
| First incremental run | Missing last indexed commit is treated as first-time state; full indexing should be run first | Git spec | Implemented |
| Non-Git repository for incremental indexing | Git change detection fails with user-facing guidance | Git spec | Implemented |
| Planned language extension | Parser factory may list planned extensions that do not have parser implementations | README, parser factory | Known limitation |
| Secondary docs drift | Older docs may mention unsupported CLI flags or stale status | README review | Known limitation |

## API, Contract, And Data Behavior

| Surface | Contract/Data Behavior | Compatibility Notes | Status |
| --- | --- | --- | --- |
| CLI global options | Supports `--config-file` and `--skip-validation` | Other global runtime flags are environment variables, not CLI flags | Implemented |
| CLI orchestration boundary | CLI commands initialize context and delegate repository task execution through `OrchestratorAgent` | Presentation formatting can stay in CLI, but specific agents and storage internals should not be invoked directly from command handlers | Implemented |
| Configuration | Loads `MARIS_*`, current `.env`, `~/.maris/.env`, then defaults | CLI overrides `data_dir` to project-local `.maris` when unset | Implemented |
| ParserFactory | `get_implemented_extensions()` returns only extensions with registered parser classes | Planned extensions can appear in `get_supported_extensions()` | Implemented |
| RepositoryKnowledgeService | Provides symbol lookup, dependency traversal, semantic retrieval, impact, history, and stats methods | History depends on metadata availability | Implemented |
| Storage | DuckDB stores metadata; LanceDB stores vector data | Runtime dependency metadata in `pyproject.toml` is incomplete; use `requirements.txt` for local setup | Implemented with packaging gap |
| OrchestratorAgent | Classifies requests and routes to specialized agents through LangGraph | Routing is keyword-based for implicit requests | Implemented |

## Acceptance Criteria

- [x] Repository indexing works for implemented parser languages
- [x] Incremental indexing works through the Git Agent
- [x] Symbol search and Q&A use local indexed data
- [x] Documentation generation is available from the CLI
- [x] Impact analysis commands are available from the CLI
- [x] CLI task commands route through `OrchestratorAgent`
- [x] Configuration is documented through `MARIS_*` variables
- [x] README reflects current setup, CLI usage, and known gaps
- [ ] Package metadata in `pyproject.toml` fully matches runtime dependencies
- [ ] Secondary docs are reconciled with current CLI behavior
- [ ] Planned parser languages are implemented or clearly separated from supported languages across all docs

## Test Proof

| Behavior | Existing Test | Needed Test | Status |
| --- | --- | --- | --- |
| Parser factory language status | `tests/test_parser_factory.py` | None identified | Covered |
| Python parser | `tests/test_python_parser.py` | None identified | Covered |
| Java parser | `tests/test_java_parser.py` | None identified | Covered |
| Scala parser | `tests/test_scala_parser.py` | None identified | Covered |
| Indexing agent | `tests/test_indexing_agent.py` | End-to-end large repo performance tests | Partially covered |
| Git agent | `tests/test_git_agent.py` | Branch switch and uncommitted change scenarios | Partially covered |
| Q&A agent | `tests/test_qa_agent.py` | More retrieval grounding assertions | Partially covered |
| Documentation agent | `tests/test_documentation_agent.py` | Markdown quality/golden tests | Partially covered |
| Impact analysis agent | `tests/test_impact_analysis_agent.py` | More real-repo regression scenarios | Partially covered |
| CLI docs parity | None | Tests or docs check for CLI option drift | Gap |

## Open Questions

| Question | Impact | Owner/Source |
| --- | --- | --- |
| Should `pyproject.toml` become the single source of package dependencies? | Affects install reliability and publishing | Maintainer |
| Should stale docs be updated now or deprecated in favor of README plus specs? | Affects documentation maintenance cost | Maintainer |
