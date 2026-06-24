# MARIS Configuration Guide

MARIS supports flexible configuration through environment variables and `.env` files, allowing you to customize models, performance settings, and behavior.

## Configuration Priority

Configuration is loaded in the following order (highest to lowest priority):

1. **Environment variables** (e.g., `export MARIS_QA_MODEL=qwen2.5:14b`)
2. **`.env` file in current directory**
3. **`~/.maris/.env` file in home directory**
4. **Default values**

## Quick Start

1. **Copy the example configuration:**
```bash
cp .env.example .env
```

2. **Edit `.env` to customize:**
```bash
# Use different models for different agents
MARIS_QA_MODEL=qwen2.5:14b
MARIS_DOC_MODEL=qwen2.5:7b
MARIS_EMBEDDING_MODEL=nomic-embed-text
```

3. **Use the CLI:**
```bash
maris index src/ --recursive
```

## Configuration Options

### Storage Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MARIS_DATA_DIR` | `~/.maris` | Directory for storing indexed data |

**Example:**
```bash
MARIS_DATA_DIR=./project-data
```

### Ollama Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MARIS_OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |

**Example:**
```bash
MARIS_OLLAMA_HOST=http://192.168.1.100:11434
```

### Embedding Model Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MARIS_EMBEDDING_MODEL` | `nomic-embed-text` | Model for generating embeddings |
| `MARIS_EMBEDDING_BATCH_SIZE` | `32` | Batch size for embedding generation |

**Recommended Models:**
- `nomic-embed-text` - Fast, good quality (default)
- `mxbai-embed-large` - Higher quality, slower
- `all-minilm` - Lightweight, faster

**⚠️ Important: Context Length for Large Files**

If you encounter errors like "input length exceeds context length", you need to increase the model's context window:

```bash
# Create a Modelfile with increased context
cat > Modelfile << EOF
FROM nomic-embed-text
PARAMETER num_ctx 8192
EOF

# Create the model with increased context
ollama create nomic-embed-text:8k -f Modelfile

# Use in your configuration
MARIS_EMBEDDING_MODEL=nomic-embed-text:8k
```

**Context Length Recommendations:**
- `2048` - Default, works for small files
- `4096` - Good for medium files
- `8192` - **Recommended for most codebases**
- `16384` - For very large files (requires more memory)

**Example:**
```bash
MARIS_EMBEDDING_MODEL=nomic-embed-text:8k
MARIS_EMBEDDING_BATCH_SIZE=64
```

### Q&A Agent Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MARIS_QA_MODEL` | `qwen2.5:7b` | Model for answering questions |
| `MARIS_QA_TEMPERATURE` | `0.7` | Temperature for Q&A (0.0-1.0) |
| `MARIS_QA_MAX_TOKENS` | `2048` | Maximum tokens for responses |

**Recommended Models:**
- `qwen2.5:3b` - Fast, good for simple questions
- `qwen2.5:7b` - Balanced (default)
- `qwen2.5:14b` - Better quality, slower
- `qwen2.5:32b` - Best quality, requires more resources
- `deepseek-coder:6.7b` - Specialized for code

**Example:**
```bash
MARIS_QA_MODEL=qwen2.5:14b
MARIS_QA_TEMPERATURE=0.7
MARIS_QA_MAX_TOKENS=4096
```

### Documentation Agent Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MARIS_DOC_MODEL` | `qwen2.5:7b` | Model for generating documentation |
| `MARIS_DOC_TEMPERATURE` | `0.3` | Temperature for docs (0.0-1.0) |
| `MARIS_DOC_MAX_TOKENS` | `4096` | Maximum tokens for documentation |

**Note:** Documentation uses lower temperature (0.3) for more consistent, factual output.

**Example:**
```bash
MARIS_DOC_MODEL=qwen2.5:7b
MARIS_DOC_TEMPERATURE=0.2
MARIS_DOC_MAX_TOKENS=8192
```

### Retrieval Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MARIS_MAX_SEARCH_RESULTS` | `20` | Maximum results for semantic search |
| `MARIS_MAX_CONTEXT_SYMBOLS` | `10` | Maximum symbols in context |

**Example:**
```bash
MARIS_MAX_SEARCH_RESULTS=50
MARIS_MAX_CONTEXT_SYMBOLS=20
```

### Performance Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MARIS_ENABLE_CACHING` | `true` | Enable caching for embeddings |
| `MARIS_PARALLEL_INDEXING` | `false` | Enable parallel indexing (experimental) |

**Example:**
```bash
MARIS_ENABLE_CACHING=true
MARIS_PARALLEL_INDEXING=true
```

### Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MARIS_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MARIS_LOG_FILE` | None | Optional log file path |

**Example:**
```bash
MARIS_LOG_LEVEL=DEBUG
MARIS_LOG_FILE=/var/log/maris.log
```

## Configuration Profiles

### Profile 1: High Quality (Requires More Resources)

Best for production use with large codebases.

```bash
# .env
MARIS_EMBEDDING_MODEL=mxbai-embed-large
MARIS_QA_MODEL=qwen2.5:32b
MARIS_DOC_MODEL=qwen2.5:14b
MARIS_QA_TEMPERATURE=0.7
MARIS_DOC_TEMPERATURE=0.2
MARIS_MAX_CONTEXT_SYMBOLS=20
```

### Profile 2: Balanced (Default)

Good balance between quality and performance.

```bash
# .env
MARIS_EMBEDDING_MODEL=nomic-embed-text
MARIS_QA_MODEL=qwen2.5:7b
MARIS_DOC_MODEL=qwen2.5:7b
MARIS_QA_TEMPERATURE=0.7
MARIS_DOC_TEMPERATURE=0.3
```

### Profile 3: Fast Development

Optimized for speed during development.

```bash
# .env
MARIS_EMBEDDING_MODEL=nomic-embed-text
MARIS_QA_MODEL=qwen2.5:3b
MARIS_DOC_MODEL=qwen2.5:3b
MARIS_EMBEDDING_BATCH_SIZE=64
MARIS_PARALLEL_INDEXING=true
```

### Profile 4: Code-Specialized

Uses code-specific models for better code understanding.

```bash
# .env
MARIS_EMBEDDING_MODEL=nomic-embed-text
MARIS_QA_MODEL=deepseek-coder:6.7b
MARIS_DOC_MODEL=qwen2.5:7b
MARIS_QA_TEMPERATURE=0.5
```

## Using Different Models for Different Agents

One of MARIS's key features is the ability to use different models for different tasks:

```bash
# Use a larger model for Q&A (better answers)
MARIS_QA_MODEL=qwen2.5:14b

# Use a smaller model for documentation (faster)
MARIS_DOC_MODEL=qwen2.5:7b

# Use specialized embedding model
MARIS_EMBEDDING_MODEL=mxbai-embed-large
```

**Why use different models?**

- **Q&A Agent**: Benefits from larger models for better reasoning
- **Documentation Agent**: Can use smaller models since docs are more structured
- **Embeddings**: Specialized embedding models provide better semantic search

## Environment-Specific Configuration

### Development Environment

```bash
# .env.development
MARIS_DATA_DIR=./dev-data
MARIS_QA_MODEL=qwen2.5:3b
MARIS_DOC_MODEL=qwen2.5:3b
MARIS_LOG_LEVEL=DEBUG
MARIS_PARALLEL_INDEXING=true
```

### Production Environment

```bash
# .env.production
MARIS_DATA_DIR=/var/lib/maris
MARIS_QA_MODEL=qwen2.5:14b
MARIS_DOC_MODEL=qwen2.5:7b
MARIS_LOG_LEVEL=INFO
MARIS_LOG_FILE=/var/log/maris.log
MARIS_ENABLE_CACHING=true
```

### CI/CD Environment

```bash
# .env.ci
MARIS_DATA_DIR=./ci-data
MARIS_QA_MODEL=qwen2.5:3b
MARIS_DOC_MODEL=qwen2.5:3b
MARIS_LOG_LEVEL=WARNING
```

## Using Configuration Files

### Specify Custom Config File

```bash
maris --config-file .env.production index src/ --recursive
```

### Multiple Projects

Each project can have its own configuration:

```bash
# Project A
cd /path/to/project-a
cp .env.example .env
# Edit .env for project A
maris index . --recursive

# Project B
cd /path/to/project-b
cp .env.example .env
# Edit .env for project B
maris index . --recursive
```

### Global Configuration

Create a global configuration in your home directory:

```bash
mkdir -p ~/.maris
cat > ~/.maris/.env << EOF
MARIS_QA_MODEL=qwen2.5:14b
MARIS_DOC_MODEL=qwen2.5:7b
MARIS_EMBEDDING_MODEL=nomic-embed-text
EOF
```

This will be used as the default for all projects unless overridden.

## Programmatic Configuration

You can also load configuration programmatically:

```python
from maris.config import load_config, MarisConfig
from pathlib import Path

# Load from default locations
config = load_config()

# Load from specific file
config = load_config(Path(".env.production"))

# Access configuration
print(f"Q&A Model: {config.qa_model}")
print(f"Doc Model: {config.doc_model}")
print(f"Embedding Model: {config.embedding_model}")

# Use in your code
from maris.agents.qa_agent import QAAgent

qa_agent = QAAgent(
    knowledge_service=knowledge_service,
    model=config.qa_model,
    host=config.ollama_host
)
```

## Troubleshooting

### Configuration Not Loading

1. Check file location:
```bash
ls -la .env
ls -la ~/.maris/.env
```

2. Check environment variables:
```bash
env | grep MARIS_
```

3. Test configuration loading:
```bash
python -c "from maris.config import load_config; c = load_config(); print(c.qa_model)"
```

### Model Not Found

Ensure the model is pulled in Ollama:
```bash
ollama list
ollama pull qwen2.5:7b
```

### Performance Issues

Try these optimizations:
```bash
# Use smaller models
MARIS_QA_MODEL=qwen2.5:3b
MARIS_DOC_MODEL=qwen2.5:3b

# Increase batch size
MARIS_EMBEDDING_BATCH_SIZE=64

# Enable parallel indexing
MARIS_PARALLEL_INDEXING=true
```

## Best Practices

1. **Start with defaults** - Use default configuration first
2. **Profile-based configs** - Create different `.env` files for different environments
3. **Version control** - Add `.env` to `.gitignore`, commit `.env.example`
4. **Document changes** - Comment your `.env` file with reasons for changes
5. **Test configurations** - Test with small datasets before full indexing
6. **Monitor resources** - Larger models require more RAM and CPU

## Examples

### Example 1: Large Codebase

```bash
# .env
MARIS_DATA_DIR=./maris-data
MARIS_QA_MODEL=qwen2.5:14b
MARIS_DOC_MODEL=qwen2.5:7b
MARIS_EMBEDDING_MODEL=mxbai-embed-large
MARIS_MAX_CONTEXT_SYMBOLS=20
MARIS_ENABLE_CACHING=true
```

### Example 2: Quick Prototyping

```bash
# .env
MARIS_QA_MODEL=qwen2.5:3b
MARIS_DOC_MODEL=qwen2.5:3b
MARIS_EMBEDDING_BATCH_SIZE=64
MARIS_PARALLEL_INDEXING=true
```

### Example 3: Remote Ollama

```bash
# .env
MARIS_OLLAMA_HOST=http://gpu-server:11434
MARIS_QA_MODEL=qwen2.5:32b
MARIS_DOC_MODEL=qwen2.5:14b
```

## See Also

- [CLI Guide](CLI_GUIDE.md) - Command-line interface documentation
- [Getting Started](GETTING_STARTED.md) - Setup instructions
- [Architecture](ARCHITECTURE.md) - System design