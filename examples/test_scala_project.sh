#!/bin/bash
# Quick test script for MARIS with a Scala project

set -e  # Exit on error

echo "🚀 MARIS Scala Project Testing Script"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in a directory with Scala files
if ! find . -name "*.scala" -type f | head -1 | grep -q .; then
    echo -e "${RED}❌ No Scala files found in current directory${NC}"
    echo "Please navigate to your Scala project directory first"
    exit 1
fi

echo -e "${GREEN}✓ Found Scala files${NC}"
echo ""

# Count Scala files
SCALA_COUNT=$(find . -name "*.scala" -type f | wc -l | tr -d ' ')
echo "📊 Found $SCALA_COUNT Scala files"
echo ""

# Step 1: Check Ollama
echo "Step 1: Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${RED}❌ Ollama is not running${NC}"
    echo "Please start Ollama with: ollama serve"
    exit 1
fi
echo -e "${GREEN}✓ Ollama is running${NC}"
echo ""

# Step 2: Check models
echo "Step 2: Checking required models..."
MODELS=$(curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4)

if echo "$MODELS" | grep -q "nomic-embed-text"; then
    echo -e "${GREEN}✓ nomic-embed-text model available${NC}"
else
    echo -e "${YELLOW}⚠ nomic-embed-text not found${NC}"
    echo "Pulling model... (this may take a few minutes)"
    ollama pull nomic-embed-text
fi

if echo "$MODELS" | grep -q "qwen2.5:7b\|llama3.2:3b"; then
    echo -e "${GREEN}✓ QA model available${NC}"
else
    echo -e "${YELLOW}⚠ QA model not found${NC}"
    echo "Pulling qwen2.5:7b... (this may take a few minutes)"
    ollama pull qwen2.5:7b
fi
echo ""

# Step 3: Clear previous index (optional)
echo "Step 3: Preparing MARIS..."
read -p "Clear previous index? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Clearing previous index..."
    maris clear --yes 2>/dev/null || echo "No previous index to clear"
fi
echo ""

# Step 4: Index the project
echo "Step 4: Indexing Scala project..."
echo "This may take a few minutes depending on project size..."
echo ""

# Use --skip-validation as a global option before the command
if maris --skip-validation index . --recursive; then
    echo ""
    echo -e "${GREEN}✓ Indexing complete!${NC}"
else
    echo -e "${RED}❌ Indexing failed${NC}"
    echo ""
    echo "Debug information:"
    echo "  Current directory: $(pwd)"
    echo "  Scala files found: $SCALA_COUNT"
    echo "  MARIS version: $(maris --version 2>&1 || echo 'unknown')"
    echo ""
    echo "Try running manually:"
    echo "  ${GREEN}maris index . --recursive${NC}"
    exit 1
fi
echo ""

# Step 5: Show statistics
echo "Step 5: Repository Statistics"
echo "=============================="
maris stats
echo ""

# Step 6: Interactive demo
echo "Step 6: Quick Demo"
echo "=================="
echo ""

# Find a Scala file to demonstrate
DEMO_FILE=$(find . -name "*.scala" -type f | head -1)
if [ -n "$DEMO_FILE" ]; then
    echo "📄 Demo file: $DEMO_FILE"
    echo ""

    # Extract class/object name from file
    CLASS_NAME=$(grep -E "^(class|object|trait) " "$DEMO_FILE" | head -1 | awk '{print $2}' | cut -d'(' -f1 | cut -d'[' -f1)

    if [ -n "$CLASS_NAME" ]; then
        echo "🔍 Searching for: $CLASS_NAME"
        maris search "$CLASS_NAME" --max-results 3
        echo ""

        echo "💡 Explaining: $CLASS_NAME"
        maris explain "$CLASS_NAME"
        echo ""
    fi
fi

# Step 7: Suggestions
echo "✨ Next Steps"
echo "============="
echo ""
echo "Try these commands:"
echo ""
echo "  1. Search for symbols:"
echo "     ${GREEN}maris search \"YourClassName\"${NC}"
echo ""
echo "  2. Ask questions:"
echo "     ${GREEN}maris ask \"What is the architecture of this project?\"${NC}"
echo ""
echo "  3. Explain a symbol:"
echo "     ${GREEN}maris explain YourClassName${NC}"
echo ""
echo "  4. Generate documentation:"
echo "     ${GREEN}maris document path/to/File.scala --output docs/File.md${NC}"
echo ""
echo "  5. Interactive mode:"
echo "     ${GREEN}maris interactive${NC}"
echo ""
echo "  6. View statistics:"
echo "     ${GREEN}maris stats${NC}"
echo ""
echo "📚 For more information, see: docs/TESTING_SCALA_PROJECT.md"
echo ""
echo -e "${GREEN}🎉 Setup complete! Happy coding!${NC}"

# Made with Bob
