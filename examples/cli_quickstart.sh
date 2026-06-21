#!/bin/bash
# MARIS CLI Quick Start Example
# This script demonstrates basic CLI usage

set -e

echo "🚀 MARIS CLI Quick Start"
echo "========================"
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "❌ Error: Ollama is not running"
    echo "   Please start Ollama first: ollama serve"
    exit 1
fi

echo "✅ Ollama is running"
echo ""

# Check if models are available
echo "📦 Checking required models..."

if ! ollama list | grep -q "nomic-embed-text"; then
    echo "⬇️  Pulling nomic-embed-text model..."
    ollama pull nomic-embed-text
else
    echo "✅ nomic-embed-text model available"
fi

if ! ollama list | grep -q "qwen2.5:7b"; then
    echo "⬇️  Pulling qwen2.5:7b model..."
    ollama pull qwen2.5:7b
else
    echo "✅ qwen2.5:7b model available"
fi

echo ""
echo "📊 Step 1: Index the MARIS repository"
echo "======================================"
maris index src/ --recursive

echo ""
echo "📈 Step 2: View repository statistics"
echo "======================================"
maris stats

echo ""
echo "🔍 Step 3: Search for symbols"
echo "=============================="
echo "Searching for 'PythonParser'..."
maris search "PythonParser" --max-results 5

echo ""
echo "💡 Step 4: Explain a symbol"
echo "==========================="
echo "Explaining 'PythonParser'..."
maris explain PythonParser

echo ""
echo "❓ Step 5: Ask a question"
echo "========================="
echo "Asking: 'How does symbol extraction work?'"
maris ask "How does symbol extraction work?" --max-symbols 5

echo ""
echo "📝 Step 6: Generate documentation"
echo "=================================="
echo "Generating documentation for src/maris/core/models.py..."
maris document src/maris/core/models.py --output /tmp/maris_models_doc.md
echo "✅ Documentation saved to /tmp/maris_models_doc.md"
cat /tmp/maris_models_doc.md | head -n 20
echo "..."

echo ""
echo "✨ Quick start complete!"
echo ""
echo "Try these commands next:"
echo "  maris interactive          # Start interactive Q&A session"
echo "  maris search 'your query'  # Search for symbols"
echo "  maris ask 'your question'  # Ask about the codebase"
echo ""
echo "For more information, see: docs/CLI_GUIDE.md"

# Made with Bob
