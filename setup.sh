#!/bin/bash
# Setup script for MARIS development environment

set -e

echo "=== MARIS Setup Script ==="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if Python 3.11+ is available
if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    echo "Error: Python 3.11 or higher is required"
    echo "Current version: $python_version"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Removing..."
    rm -rf venv
fi
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Install development dependencies
echo ""
echo "Installing development dependencies..."
pip install -r requirements-dev.txt

# Install package in editable mode
echo ""
echo "Installing MARIS in editable mode..."
pip install -e .

# Verify installation
echo ""
echo "Verifying installation..."
python -c "import maris; print(f'MARIS version: {maris.__version__}')"

# Check for Ollama
echo ""
echo "Checking for Ollama..."
if command -v ollama &> /dev/null; then
    echo "✓ Ollama is installed"
    echo ""
    echo "Available models:"
    ollama list
    echo ""
    echo "To install required models, run:"
    echo "  ollama pull nomic-embed-text"
    echo "  ollama pull qwen2.5:8b"
else
    echo "⚠ Ollama is not installed"
    echo "Please install Ollama from: https://ollama.ai"
fi

# Create data directory
echo ""
echo "Creating data directory..."
mkdir -p data

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To activate the environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run the basic example:"
echo "  python examples/basic_indexing.py"
echo ""
echo "To run tests:"
echo "  pytest"
echo ""

# Made with Bob
