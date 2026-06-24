# Getting Started with MARIS

## Overview

MARIS (Multi-Agent Repository Intelligence System) is a local-first repository intelligence platform that helps developers understand, navigate, and analyze source code without sending data to external services.

## Prerequisites

- Python 3.11 or higher
- Ollama installed and running locally
- Git (for repository analysis)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/maris.git
cd maris
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 4. Install Ollama Models

MARIS requires local LLM models via Ollama:

```bash
# Install recommended embedding model
ollama pull nomic-embed-text

# Install LLM for reasoning (choose one)
ollama pull qwen2.5:8b      # MVP - faster, lower resource
ollama pull gemma2:12b      # MVP - better quality
ollama pull qwen2.5:32b     # Recommended - best balance
```

## Quick Start

### ⚠️ Important: Index First

**MARIS requires explicit indexing before you can search, ask questions, or generate documentation.** MARIS does not auto-index repositories.

### 1. Initialize MARIS for a Repository

```python
from maris.storage.metadata_store import DuckDBMetadataStore
from maris.storage.vector_store import LanceDBVectorStore
from maris.agents.indexing_agent import IndexingAgent

# Initialize storage
metadata_store = DuckDBMetadataStore("./data/maris.duckdb")
metadata_store.initialize()

vector_store = LanceDBVectorStore("./data/lancedb")
vector_store.initialize()

# Create indexing agent
agent = IndexingAgent(
    metadata_store=metadata_store,
    vector_store=vector_store,
    repo_path="/path/to/your/repository"
)

# STEP 1: Index the repository (required first step)
result = agent.index_repository()
print(f"Indexed {result.files_processed} files")
print(f"Extracted {result.symbols_extracted} symbols")
```

### 2. Query Repository Information

**After indexing**, you can query the repository:

```python
# Get repository statistics
stats = agent.get_indexing_status()
print(f"Total symbols: {stats['total_symbols']}")
print(f"Languages: {stats['languages']}")

# Find symbols
symbols = metadata_store.find_symbols_by_name("MyClass")
for symbol in symbols:
    print(f"{symbol.name} in {symbol.file_path}:{symbol.start_line}")
```

### 3. CLI Quick Start

```bash
# Step 1: Index your repository (required)
maris index src/ --recursive

# Step 2: Verify indexing
maris stats

# Step 3: Use other commands
maris search "MyClass"
maris ask "How does the parser work?"
maris explain IndexingAgent
```

## Project Structure

```
maris/
├── src/maris/
│   ├── agents/          # Specialized agents
│   │   └── indexing_agent.py
│   ├── core/            # Domain models
│   │   └── models.py
│   ├── knowledge/       # Repository Knowledge Layer
│   │   └── service.py
│   ├── storage/         # Storage adapters
│   │   ├── metadata_store.py
│   │   └── vector_store.py
│   └── __init__.py
├── tests/               # Test suite
├── docs/                # Documentation
├── .codex/              # Project specifications
│   ├── project-profile.md
│   └── specs/
└── pyproject.toml
```

## Configuration

### Supported Languages (MVP)

- Scala (`.scala`)
- Java (`.java`)
- Python (`.py`)
- TypeScript (`.ts`, `.tsx`)

### Excluded Patterns

The following directories are automatically excluded from indexing:

- `node_modules/`
- `target/`
- `build/`
- `.git/`
- `dist/`
- `__pycache__/`
- `*.min.js`
- `*.bundle.js`

## Next Steps

1. **Read the Architecture**: See [`README.md`](../README.md) for system architecture
2. **Review Specifications**: Check [`.codex/specs/`](../.codex/specs/) for detailed specs
3. **Run Tests**: Execute `pytest` to verify installation
4. **Explore Examples**: See [`examples/`](../examples/) for usage patterns

## Troubleshooting

### Ollama Connection Issues

If you see connection errors:

```bash
# Check if Ollama is running
ollama list

# Start Ollama service if needed
ollama serve
```

### Database Initialization Errors

If database initialization fails:

```bash
# Remove existing databases
rm -rf ./data/

# Reinitialize
python -c "from maris.storage.metadata_store import DuckDBMetadataStore; \
           store = DuckDBMetadataStore('./data/maris.duckdb'); \
           store.initialize()"
```

### Import Errors

If you see import errors:

```bash
# Ensure package is installed in development mode
pip install -e .

# Verify installation
python -c "import maris; print(maris.__version__)"
```

## Performance Tips

1. **Incremental Indexing**: Use `index_files()` for changed files only
2. **Batch Operations**: Insert symbols and dependencies in batches
3. **Resource Allocation**: Larger Ollama models require more RAM
4. **Storage Location**: Use SSD for database files for better performance

## Getting Help

- **Documentation**: See [`docs/`](.) directory
- **Specifications**: Check [`.codex/specs/`](../.codex/specs/)
- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Join GitHub Discussions for questions

## Development Setup

For contributing to MARIS:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run type checking
mypy src/maris

# Format code
black src/maris tests
ruff check src/maris tests
```

## What's Next?

After getting started, explore:

1. **Documentation Agent**: Generate repository documentation
2. **Q&A Agent**: Ask questions about your codebase
3. **Impact Analysis**: Understand change impacts
4. **Git Archaeology**: Track code evolution

See the [Roadmap](../README.md#future-roadmap) for upcoming features.