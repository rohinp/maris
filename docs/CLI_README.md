# MARIS CLI

A powerful command-line interface for local repository intelligence.

## Quick Start

```bash
# Install MARIS
pip install -e .

# Install Ollama models
ollama pull nomic-embed-text
ollama pull qwen2.5:7b

# Index your repository
maris index . --recursive

# Start exploring
maris interactive
```

## Features

### 🔍 **Search** - Find symbols instantly
```bash
maris search "MyClass"
```

### 💡 **Explain** - Understand code deeply
```bash
maris explain MyClass
```

### ❓ **Ask** - Natural language Q&A
```bash
maris ask "How does authentication work?"
```

### 📝 **Document** - Auto-generate docs
```bash
maris document src/main.py --output docs/main.md
```

### 💬 **Interactive** - Explore interactively
```bash
maris interactive
```

### 📊 **Stats** - Repository insights
```bash
maris stats
```

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `index` | Index files/directories | `maris index src/ -r` |
| `search` | Semantic symbol search | `maris search "Parser"` |
| `explain` | Explain a symbol | `maris explain PythonParser` |
| `ask` | Ask questions | `maris ask "How does X work?"` |
| `document` | Generate documentation | `maris document file.py` |
| `stats` | Show statistics | `maris stats` |
| `interactive` | Interactive Q&A | `maris interactive` |
| `clear` | Clear indexed data | `maris clear` |

## Global Options

```bash
--config-file PATH       # Path to .env configuration file
--skip-validation        # Skip Ollama and model validation checks
```

**Note:** Configuration is primarily done through environment variables or `.env` files. See [Configuration Guide](CONFIGURATION.md) for details on `MARIS_DATA_DIR`, `MARIS_OLLAMA_HOST`, `MARIS_EMBEDDING_MODEL`, `MARIS_QA_MODEL`, etc.

## Examples

### Onboard to a new codebase
```bash
# Index the repository
maris index . --recursive

# Get overview
maris stats

# Start exploring
maris interactive
```

### Code review workflow
```bash
# Understand changes
maris explain ChangedClass

# Find usage
maris search "ChangedClass"

# Assess impact
maris ask "What depends on ChangedClass?"
```

### Generate documentation
```bash
# Single file
maris document src/main.py --output docs/main.md

# All files
find src -name "*.py" -exec sh -c '
    maris document "$1" --output "docs/$(basename $1 .py).md"
' _ {} \;
```

## Privacy First

✅ All processing happens locally
✅ No external API calls
✅ Source code never leaves your machine
✅ Complete control over your data

## Performance

- **Indexing**: ~100-500 files/minute
- **Search**: <1 second
- **Q&A**: 2-10 seconds
- **Storage**: ~1-5 MB per 1000 symbols

## Documentation

- [Complete CLI Guide](CLI_GUIDE.md) - Detailed command reference
- [Getting Started](GETTING_STARTED.md) - Setup instructions
- [Architecture](ARCHITECTURE.md) - System design

## Requirements

- Python 3.11+
- Ollama with models:
  - `nomic-embed-text` (embeddings)
  - `qwen2.5:7b` (reasoning)

## Installation

```bash
# Clone repository
git clone https://github.com/yourusername/maris.git
cd maris

# Install dependencies
pip install -e .

# Install Ollama models
ollama pull nomic-embed-text
ollama pull qwen2.5:7b

# Verify installation
maris --help
```

## Troubleshooting

**"Model not found"**
```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

**"No results found"**
```bash
maris stats  # Check if indexed
maris index . --recursive  # Index if needed
```

**Slow performance**
```bash
# Use faster models
maris --llm-model qwen2.5:3b ask "question"
```

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.