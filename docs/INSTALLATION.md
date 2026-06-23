# MARIS Installation Guide

This guide covers installing MARIS globally on your machine for easy access from any directory.

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Ollama (for embeddings and Q&A)

## Installation Methods

### Method 1: Install in Development Mode (Recommended for Testing)

This method installs MARIS globally while keeping it editable, so any changes you make are immediately available.

```bash
# Navigate to MARIS directory
cd /Users/rohinpatel/Development/myprojects/maris

# Install in development/editable mode
pip install -e .

# Verify installation
maris --version
maris --help
```

**Benefits:**
- ✅ `maris` command available globally
- ✅ Changes to code are immediately reflected
- ✅ Easy to update and test
- ✅ Can uninstall easily

### Method 2: Install as Regular Package

This method installs MARIS as a regular package (not editable).

```bash
# Navigate to MARIS directory
cd /Users/rohinpatel/Development/myprojects/maris

# Install normally
pip install .

# Verify installation
maris --version
maris --help
```

### Method 3: Install from Source with Dependencies

If you need to ensure all dependencies are installed:

```bash
cd /Users/rohinpatel/Development/myprojects/maris

# Install dependencies first
pip install -r requirements.txt

# Then install MARIS in development mode
pip install -e .
```

## Verification

After installation, verify MARIS is working:

```bash
# Check version
maris --version

# Check help
maris --help

# Check if command is found
which maris

# Test with a simple command
maris stats
```

## Troubleshooting

### Issue: `maris: command not found`

**Solution 1: Check pip installation location**
```bash
# Find where pip installs scripts
python -m site --user-base

# Add to PATH if needed (add to ~/.bashrc or ~/.zshrc)
export PATH="$PATH:$(python -m site --user-base)/bin"
```

**Solution 2: Use Python module directly**
```bash
# Instead of: maris index .
# Use: python -m maris.cli.main index .
```

**Solution 3: Reinstall with --user flag**
```bash
pip install --user -e /Users/rohinpatel/Development/myprojects/maris
```

### Issue: `ModuleNotFoundError`

**Solution: Install dependencies**
```bash
cd /Users/rohinpatel/Development/myprojects/maris
pip install -r requirements.txt
```

### Issue: Permission denied

**Solution: Use --user flag**
```bash
pip install --user -e /Users/rohinpatel/Development/myprojects/maris
```

### Issue: Multiple Python versions

**Solution: Use specific Python version**
```bash
# Use Python 3.9+
python3.9 -m pip install -e /Users/rohinpatel/Development/myprojects/maris

# Or use your conda environment
conda activate base
pip install -e /Users/rohinpatel/Development/myprojects/maris
```

## Uninstallation

To uninstall MARIS:

```bash
pip uninstall maris
```

## Updating MARIS

Since you installed in development mode (`-e`), any changes to the code are automatically available. No need to reinstall!

If you installed without `-e`, reinstall to get updates:

```bash
cd /Users/rohinpatel/Development/myprojects/maris
pip install --upgrade .
```

## Using MARIS

Once installed, you can use `maris` from any directory:

```bash
# Navigate to your project
cd /path/to/your/scala/project

# Use MARIS commands
maris index . --recursive
maris stats
maris search "ClassName"
maris ask "What is the architecture?"
```

## Environment Setup

### Optional: Create a dedicated environment

```bash
# Create virtual environment
python -m venv maris-env

# Activate it
source maris-env/bin/activate  # On macOS/Linux
# or
maris-env\Scripts\activate  # On Windows

# Install MARIS
cd /Users/rohinpatel/Development/myprojects/maris
pip install -e .
```

### Optional: Use conda environment

```bash
# Create conda environment
conda create -n maris python=3.9

# Activate it
conda activate maris

# Install MARIS
cd /Users/rohinpatel/Development/myprojects/maris
pip install -e .
```

## Configuration

### Global Configuration

Create a global config file:

```bash
# Create config directory
mkdir -p ~/.maris

# Create config file
cat > ~/.maris/.env << 'EOF'
# Ollama Configuration
MARIS_OLLAMA_HOST=http://localhost:11434
MARIS_EMBEDDING_MODEL=nomic-embed-text
MARIS_QA_MODEL=qwen2.5:7b
MARIS_DOC_MODEL=qwen2.5:7b

# Storage Configuration
MARIS_DATA_DIR=.maris

# Embedding Configuration
MARIS_EMBEDDING_BATCH_SIZE=10
EOF
```

### Project-Specific Configuration

Create a `.env` file in your project directory:

```bash
cd /path/to/your/project

cat > .env << 'EOF'
# Project-specific MARIS configuration
MARIS_DATA_DIR=.maris
MARIS_EMBEDDING_BATCH_SIZE=5
EOF
```

## Quick Start After Installation

```bash
# 1. Start Ollama
ollama serve

# 2. Pull required models (in another terminal)
ollama pull nomic-embed-text
ollama pull qwen2.5:7b

# 3. Navigate to your project
cd /path/to/your/project

# 4. Index your project
maris index . --recursive

# 5. Explore
maris stats
maris search "YourClass"
maris ask "What does this project do?"
```

## Testing the Installation

Run the test script to verify everything works:

```bash
# Navigate to your Scala project
cd /path/to/your/scala/project

# Run the test script
bash /Users/rohinpatel/Development/myprojects/maris/examples/test_scala_project.sh
```

## Next Steps

1. **Read the documentation:**
   - `docs/GETTING_STARTED.md` - Basic usage
   - `docs/CLI_GUIDE.md` - CLI commands
   - `docs/TESTING_SCALA_PROJECT.md` - Scala-specific guide

2. **Try the examples:**
   ```bash
   cd /Users/rohinpatel/Development/myprojects/maris/examples
   python basic_indexing.py
   python ask_questions.py
   ```

3. **Index your project:**
   ```bash
   cd /path/to/your/project
   maris index . --recursive
   ```

## Support

If you encounter issues:

1. Check the logs: `.maris/maris.log`
2. Run with debug output: `maris --skip-validation index . -r 2>&1 | tee debug.log`
3. Verify Ollama is running: `curl http://localhost:11434/api/tags`
4. Check Python version: `python --version` (should be 3.9+)
5. Verify installation: `pip show maris`

## Summary

**Recommended installation:**
```bash
cd /Users/rohinpatel/Development/myprojects/maris
pip install -e .
maris --version
```

This installs MARIS globally in development mode, making the `maris` command available from any directory while keeping the code editable for testing and development.