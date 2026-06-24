# MARIS CLI Guide

The MARIS CLI provides a command-line interface for all repository intelligence features.

## Installation

After installing MARIS, the `maris` command will be available:

```bash
pip install -e .
```

## ⚠️ Important: Index Before Using

**Most MARIS commands require you to index your repository first.** Commands like `search`, `ask`, `explain`, and `document` all depend on the indexed knowledge base. MARIS does not auto-index.

**Quick start workflow:**
```bash
# 1. Index your repository (required first step)
maris index src/ --recursive

# 2. Verify indexing
maris stats

# 3. Now use other commands
maris ask "How does this work?"
```

## Global Options

All commands support these global options:

```bash
--data-dir PATH          # Directory for MARIS data storage (default: ~/.maris)
--ollama-url URL         # Ollama API base URL (default: http://localhost:11434)
--embedding-model MODEL  # Ollama embedding model (default: nomic-embed-text)
--llm-model MODEL        # Ollama LLM model for reasoning (default: qwen2.5:7b)
```

Example:
```bash
maris --data-dir ./my-data --llm-model qwen2.5:14b index src/
```

## Commands

### `maris index`

Index a file or directory to build the repository knowledge base.

**Usage:**
```bash
maris index PATH [OPTIONS]
```

**Options:**
- `-r, --recursive`: Index directory recursively

**Examples:**
```bash
# Index a single file
maris index src/main.py

# Index a directory recursively
maris index src/ --recursive

# Index with custom data directory
maris --data-dir ./project-data index src/ -r
```

**What it does:**
1. Parses Python files using Tree-sitter
2. Extracts symbols (classes, functions, methods, constants)
3. Extracts dependencies (imports, calls, inheritance)
4. Generates embeddings for semantic search
5. Stores everything in the local knowledge base

---

### `maris search`

Search for symbols in the indexed repository using semantic search.

**Prerequisites:** ⚠️ **Requires prior indexing** with `maris index`.

**Usage:**
```bash
maris search QUERY [OPTIONS]
```

**Options:**
- `-n, --max-results INTEGER`: Maximum number of results (default: 10)

**Examples:**
```bash
# Search for a symbol
maris search "GraphRunner"

# Search with more results
maris search "retry" --max-results 20

# Search for concepts
maris search "error handling"
```

**Output:**
Displays a table with:
- Symbol name
- Symbol type (class, function, method, etc.)
- File path
- Similarity score

---

### `maris explain`

Get a detailed explanation of a specific symbol.

**Prerequisites:** ⚠️ **Requires prior indexing** with `maris index`.

**Usage:**
```bash
maris explain SYMBOL_NAME
```

**Examples:**
```bash
# Explain a class
maris explain GraphRunner

# Explain a function
maris explain retryExecuteNode

# Explain a method
maris explain PythonParser.extract_symbols
```

**Output:**
- Detailed explanation of what the symbol does
- How it works
- Related symbols
- Confidence level (high/medium/low)

---

### `maris ask`

Ask natural language questions about your codebase.

**Prerequisites:** ⚠️ **You must index your repository first** using `maris index`. If the repository is not indexed, you will get poor or empty answers.

**Usage:**
```bash
maris ask QUESTION [OPTIONS]
```

**Options:**
- `-n, --max-symbols INTEGER`: Maximum symbols to retrieve (default: 10)

**Examples:**
```bash
# Ask about functionality
maris ask "How does the parser work?"

# Ask about architecture
maris ask "What is the purpose of the indexing agent?"

# Ask about relationships
maris ask "Where is the RepositoryKnowledgeService used?"

# Ask with more context
maris ask "How does error handling work?" --max-symbols 20
```

**Output:**
- Natural language answer
- Relevant symbols referenced
- Confidence level
- Source files

**Troubleshooting:**
- If you get "no relevant context found" or low confidence answers, make sure you've indexed your repository
- Use `maris stats` to verify indexing status

---

### `maris document`

Generate documentation for a file.

**Usage:**
```bash
maris document FILE_PATH [OPTIONS]
```

**Options:**
- `-o, --output PATH`: Output file path (if not specified, prints to stdout)

**Examples:**
```bash
# Generate and display documentation
maris document src/main.py

# Save documentation to file
maris document src/main.py --output docs/main.md

# Generate docs for multiple files
for file in src/*.py; do
    maris document "$file" --output "docs/$(basename $file .py).md"
done
```

**Output:**
Markdown documentation including:
- Module overview
- Classes with methods
- Functions
- Constants
- Dependencies

---

### `maris stats`

Show repository statistics.

**Usage:**
```bash
maris stats
```

**Examples:**
```bash
maris stats
```

**Output:**
- Total symbols indexed
- Number of indexed files
- Breakdown by symbol type (classes, functions, methods, etc.)

---

### `maris interactive`

Start an interactive Q&A session.

**Usage:**
```bash
maris interactive
```

**Examples:**
```bash
maris interactive
```

**Features:**
- Ask multiple questions in sequence
- Get immediate answers
- See confidence levels
- Type `exit`, `quit`, or `q` to end session
- Press Ctrl+C to exit

**Example session:**
```
Question: How does the parser work?
Answer: The parser uses Tree-sitter to parse Python source code...
Confidence: high

Question: Where is Symbol used?
Answer: The Symbol class is used throughout the codebase...
Confidence: high

Question: exit
Goodbye!
```

---

### `maris clear`

Clear all indexed data.

**Usage:**
```bash
maris clear
```

**Examples:**
```bash
maris clear
```

**Warning:** This will delete all indexed symbols, dependencies, and embeddings. You will be prompted for confirmation.

---

## Workflows

### Initial Setup

1. **Install Ollama models:**
```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

2. **Index your repository:**
```bash
maris index . --recursive
```

3. **Verify indexing:**
```bash
maris stats
```

### Daily Usage

**Quick symbol lookup:**
```bash
maris search "MyClass"
```

**Understand code:**
```bash
maris explain MyClass
maris ask "How does MyClass work?"
```

**Generate documentation:**
```bash
maris document src/important.py --output docs/important.md
```

**Interactive exploration:**
```bash
maris interactive
```

### Re-indexing

After making changes to your code:

```bash
# Re-index changed files
maris index src/modified_file.py

# Or re-index entire directory
maris index src/ --recursive
```

To start fresh:
```bash
maris clear
maris index . --recursive
```

---

## Configuration

### Data Directory

By default, MARIS stores data in `~/.maris/`. You can change this:

```bash
# Use project-specific data directory
maris --data-dir ./.maris index src/ -r

# Use environment variable
export MARIS_DATA_DIR=./project-data
maris index src/ -r
```

### Ollama Configuration

If Ollama is running on a different host:

```bash
maris --ollama-url http://192.168.1.100:11434 index src/ -r
```

### Model Selection

Use different models for better performance or accuracy:

```bash
# Use larger embedding model
maris --embedding-model mxbai-embed-large index src/ -r

# Use larger LLM for better answers
maris --llm-model qwen2.5:32b ask "Complex question?"
```

---

## Troubleshooting

### "Model not found" error

Pull the required Ollama models:
```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

### "No results found" when searching or asking

**This is the most common issue.** Make sure you've indexed your repository first:
```bash
maris stats  # Check if anything is indexed
maris index . --recursive  # Index if needed
```

MARIS does not auto-index. You must explicitly run `maris index` before using search, ask, explain, or document commands.

### Slow indexing

- Indexing large repositories takes time
- Embedding generation is the slowest part
- Consider using a faster embedding model
- Use `--recursive` only when needed

### Low confidence answers

- Index more of your codebase
- Use `--max-symbols` to retrieve more context
- Try rephrasing your question
- Use `explain` for specific symbols instead of `ask`

---

## Tips

1. **Start small**: Index a single directory first to test
2. **Use search before ask**: Search is faster for finding specific symbols
3. **Interactive mode**: Great for exploring unfamiliar codebases
4. **Generate docs**: Create documentation as you index
5. **Regular re-indexing**: Re-index after significant changes

---

## Examples

### Onboarding to a new codebase

```bash
# 1. Index the repository
maris index . --recursive

# 2. Get overview
maris stats

# 3. Start exploring
maris interactive

# In interactive mode:
# - "What is the main entry point?"
# - "How is configuration handled?"
# - "Where are the tests?"
```

### Code review workflow

```bash
# 1. Understand changed files
maris explain ChangedClass

# 2. Find usage
maris search "ChangedClass"

# 3. Ask about impact
maris ask "What depends on ChangedClass?"
```

### Documentation generation

```bash
# Generate docs for all Python files
find src -name "*.py" -exec sh -c '
    maris document "$1" --output "docs/$(basename $1 .py).md"
' _ {} \;
```

---

## Performance

- **Indexing**: ~100-500 files/minute (depends on file size and model)
- **Search**: <1 second for most queries
- **Q&A**: 2-10 seconds (depends on LLM model and context size)
- **Storage**: ~1-5 MB per 1000 symbols

---

## Privacy

All data stays local:
- ✅ Source code never leaves your machine
- ✅ Embeddings generated locally via Ollama
- ✅ LLM reasoning happens locally
- ✅ No external API calls
- ✅ No telemetry or tracking

---

## Next Steps

- See [GETTING_STARTED.md](GETTING_STARTED.md) for setup instructions
- See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- See [MVP_COMPLETE.md](MVP_COMPLETE.md) for feature details