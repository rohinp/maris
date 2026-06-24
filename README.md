# MARIS

MARIS is a local-first, multi-agent repository intelligence system for understanding source code. It indexes repositories with language-aware parsers, stores repository knowledge locally, and uses local Ollama models for search, Q&A, documentation, and impact analysis.

The goal is to help developers reason about codebases without sending source code to external services. MARIS focuses on repository understanding rather than code generation.

## Current Status

MARIS is an alpha-stage Python package.

Implemented:

- CLI entry point: `maris`
- Local storage with DuckDB metadata and LanceDB vectors
- Ollama-based embeddings and local model validation
- Parser implementations for Python, Java, and Scala
- Repository indexing, semantic search, symbol explanations, Q&A, documentation generation, and repository stats
- Git-based incremental indexing
- Impact analysis commands for impact, edge cases, test coverage, and breaking changes

Planned or incomplete:

- Parser factory lists additional planned languages, but Kotlin, JavaScript, TypeScript, Go, Bash, and Rust parsers are not implemented yet
- Git archaeology and architecture evolution agents are roadmap items
- Some secondary docs may lag the CLI; the root README should be treated as the current quick-start reference
- `AGENT.md` is contributor guidance and product direction, not an executable agent spec

## Requirements

- Python 3.11+
- Ollama running locally
- Required Ollama models:
  - `nomic-embed-text` for embeddings
  - `qwen2.5:7b` by default for Q&A and documentation

Install or start Ollama separately, then pull the default models:

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

## Installation

For local development:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

Alternatively, use the setup script:

```bash
./setup.sh
source venv/bin/activate
```

Verify the CLI:

```bash
maris --help
```

## Quick Start

Run MARIS from the repository you want to analyze. By default, MARIS stores project-specific data in `.maris/` in the current working directory unless `MARIS_DATA_DIR` is set.

```bash
# Index supported source files recursively
maris index src/ --recursive

# Show indexed repository statistics
maris stats

# Search indexed symbols
maris search "RepositoryKnowledge"

# Ask a question grounded in indexed symbols
maris ask "How does indexing work?"

# Explain a symbol
maris explain IndexingAgent

# Generate documentation for one file
maris document src/maris/agents/indexing_agent.py --output docs/indexing_agent.md
```

Incremental indexing uses Git change detection:

```bash
maris index --incremental
```

Impact analysis examples:

```bash
maris impact analyze --symbol "GitAgent.detect_changes"
maris impact edge-cases --file "src/maris/agents/git_agent.py"
maris impact tests --symbol "QAAgent.answer_question"
maris impact breaking-changes --symbol "RepositoryKnowledgeImpl"
```

Interactive Q&A:

```bash
maris interactive
```

## CLI Reference

Global options:

```bash
maris --config-file .env --skip-validation COMMAND
```

Commands:

- `maris index [PATH]`: index a file or directory
- `maris index --incremental`: index files changed since the last indexed commit
- `maris search QUERY`: semantic symbol search
- `maris explain SYMBOL_NAME`: explain a symbol with relevant indexed context
- `maris ask QUESTION`: ask a natural-language repository question
- `maris impact analyze`: analyze callers, callees, affected files, and recommendations
- `maris impact edge-cases`: detect likely edge case risks
- `maris impact tests`: inspect test coverage signals
- `maris impact breaking-changes`: detect potential breaking change risks
- `maris document FILE_PATH`: generate Markdown documentation for a file
- `maris stats`: show indexed symbol counts
- `maris clear`: clear indexed metadata and vectors
- `maris interactive`: start an interactive Q&A session

Use command help for exact options:

```bash
maris COMMAND --help
maris impact COMMAND --help
```

## Configuration

Configuration is loaded in this order:

1. Environment variables with the `MARIS_` prefix
2. `.env` in the current directory
3. `~/.maris/.env`
4. Defaults

Common settings:

```bash
MARIS_DATA_DIR=.maris
MARIS_OLLAMA_HOST=http://localhost:11434
MARIS_EMBEDDING_MODEL=nomic-embed-text
MARIS_EMBEDDING_BATCH_SIZE=32
MARIS_QA_MODEL=qwen2.5:7b
MARIS_QA_TEMPERATURE=0.7
MARIS_QA_MAX_TOKENS=2048
MARIS_DOC_MODEL=qwen2.5:7b
MARIS_DOC_TEMPERATURE=0.3
MARIS_DOC_MAX_TOKENS=4096
MARIS_MAX_SEARCH_RESULTS=20
MARIS_MAX_CONTEXT_SYMBOLS=10
MARIS_ENABLE_CACHING=true
MARIS_PARALLEL_INDEXING=false
MARIS_LOG_LEVEL=INFO
```

For first-time setup, `maris index ... --auto-pull` can pull missing Ollama models automatically. Use `--skip-validation` only when you intentionally want to bypass Ollama and model checks.

## Architecture

MARIS is organized around a shared repository knowledge layer:

```text
Source repository
    -> Indexing Agent
    -> Repository Knowledge Layer
       -> DuckDB metadata store
       -> LanceDB vector store
       -> Ollama embeddings
    -> Specialized agents
       -> Q&A Agent
       -> Documentation Agent
       -> Git Agent
       -> Impact Analysis Agent
```

Core source layout:

```text
src/maris/
  agents/       specialized agents and orchestrator
  cli/          Click-based CLI
  config/       configuration loading
  core/         domain models
  embeddings/   Ollama embedding service
  indexing/     Tree-sitter parsers and parser factory
  knowledge/    repository knowledge service
  storage/      DuckDB and LanceDB adapters
  utils/        shared validation helpers
```

## Development

Run tests:

```bash
pytest
```

Run targeted tests:

```bash
pytest tests/test_python_parser.py
pytest tests/test_orchestrator_agent.py
```

Formatting and linting tools are configured in `pyproject.toml`:

```bash
black src tests
ruff check src tests
```

## Contributor Guidance

`AGENT.md` contains contributor guidance and product direction. The key expectations are:

- Read `.codex/project-profile.md` before changing architecture or design direction
- Read relevant files in `.codex/specs/` before changing behavior
- Preserve the local-first, retrieval-first, symbol-aware design
- Prefer deterministic workflows and specialized agents over broad autonomous loops
- Update specs when behavior, acceptance criteria, API contracts, or domain rules change

Gaps found during review:

- `AGENT.md` refers to a `pragmatic-developer` skill and says the guidance is intended for Claude; that dependency is not represented in this repository and may confuse other agents or contributors
- The root README previously read more like a product vision than a setup and usage guide
- Some docs mention stale or unsupported CLI flags; verify behavior against `src/maris/cli/main.py`
- Runtime dependencies are split unevenly between `requirements.txt` and `pyproject.toml`; use `requirements.txt` for a reliable local setup until package metadata is reconciled
- The roadmap and parser support docs should distinguish implemented languages from planned languages consistently

## Additional Docs

- [Installation Guide](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Git Agent](docs/GIT_AGENT.md)
- [Impact Analysis Agent](docs/IMPACT_ANALYSIS_AGENT.md)
- [Multi-Language Support](docs/MULTI_LANGUAGE_SUPPORT.md)
