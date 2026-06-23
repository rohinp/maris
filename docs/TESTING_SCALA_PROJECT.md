# Testing MARIS with a Local Scala Project

This guide walks you through testing MARIS's multi-language support with your local Scala project.

## Prerequisites

### 1. Install Ollama and Models

```bash
# Install Ollama (if not already installed)
# macOS/Linux:
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve

# In a new terminal, pull required models
ollama pull nomic-embed-text    # For embeddings
ollama pull qwen2.5:7b          # For Q&A (or use llama3.2:3b for lighter option)
```

### 2. Install MARIS

```bash
# Navigate to MARIS directory
cd /Users/rohinpatel/Development/myprojects/maris

# Install in development mode
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
# Check MARIS is installed
maris --help

# Verify tree-sitter Scala is installed
python -c "import tree_sitter_scala; print('Scala parser ready!')"
```

## Step-by-Step Testing Guide

### Step 1: Prepare Your Scala Project

Navigate to your Scala project directory:

```bash
cd /path/to/your/scala/project
```

Example Scala project structure:
```
my-scala-project/
├── src/
│   └── main/
│       └── scala/
│           ├── com/
│           │   └── example/
│           │       ├── Main.scala
│           │       ├── models/
│           │       │   └── User.scala
│           │       └── services/
│           │           └── UserService.scala
│           └── utils/
│               └── Helper.scala
└── build.sbt
```

### Step 2: Configure MARIS (Optional)

Create a `.env` file in your project directory or use the default configuration:

```bash
# Optional: Create custom configuration
cat > .env << 'EOF'
# Ollama Configuration
MARIS_OLLAMA_HOST=http://localhost:11434
MARIS_EMBEDDING_MODEL=nomic-embed-text
MARIS_QA_MODEL=qwen2.5:7b

# Storage Configuration
MARIS_DATA_DIR=.maris

# Embedding Configuration
MARIS_EMBEDDING_BATCH_SIZE=10
EOF
```

### Step 3: Index Your Scala Project

#### Option A: Index Entire Project (Recommended)

```bash
# Index all Scala files recursively
maris index src/ --recursive

# Expected output:
# Validating Ollama setup...
# ✓ Ollama is running
# ✓ Model nomic-embed-text is available
# ✓ Model qwen2.5:7b is available
#
# Indexing 15 file(s)...
# ✓ Indexing complete!
#   Files processed: 15
#   Symbols extracted: 87
#   Embeddings generated: 87
```

#### Option B: Index Specific Directory

```bash
# Index only a specific package
maris index src/main/scala/com/example/services/ --recursive
```

#### Option C: Index Single File

```bash
# Index a single Scala file
maris index src/main/scala/com/example/Main.scala
```

### Step 4: Verify Indexing

Check repository statistics:

```bash
maris stats

# Expected output:
# ┏━━━━━━━━━━━━━━━━━┳━━━━━━━┓
# ┃ Metric          ┃ Count ┃
# ┡━━━━━━━━━━━━━━━━━╇━━━━━━━┩
# │ Total Symbols   │    87 │
# │ Indexed Files   │    15 │
# │   Classes       │    12 │
# │   Traits        │     5 │
# │   Objects       │     8 │
# │   Functions     │    45 │
# │   Vals          │    17 │
# └─────────────────┴───────┘
```

### Step 5: Search for Symbols

Search for specific symbols in your codebase:

```bash
# Search for a class
maris search "UserService"

# Search for a function
maris search "processUser"

# Search with more results
maris search "User" --max-results 20
```

### Step 6: Ask Questions About Your Code

#### General Questions

```bash
# Ask about architecture
maris ask "What is the overall architecture of this project?"

# Ask about specific functionality
maris ask "How does the user authentication work?"

# Ask about dependencies
maris ask "What are the main dependencies between modules?"
```

#### Explain Specific Symbols

```bash
# Explain a class
maris explain UserService

# Explain a trait
maris explain Auditable

# Explain an object
maris explain DatabaseConfig
```

### Step 7: Generate Documentation

#### Document a Single File

```bash
# Generate and display documentation
maris document src/main/scala/com/example/services/UserService.scala

# Save documentation to file
maris document src/main/scala/com/example/services/UserService.scala \
  --output docs/UserService.md
```

#### Document Multiple Files

```bash
# Create docs directory
mkdir -p docs/api

# Document all service files
for file in src/main/scala/com/example/services/*.scala; do
  filename=$(basename "$file" .scala)
  maris document "$file" --output "docs/api/${filename}.md"
done
```

### Step 8: Interactive Q&A Session

Start an interactive session to ask multiple questions:

```bash
maris interactive

# Example session:
# ╭─────────────────────────────────────────────╮
# │ MARIS Interactive Q&A                       │
# │                                             │
# │ Ask questions about your codebase.          │
# │ Type 'exit' or 'quit' to end the session.  │
# ╰─────────────────────────────────────────────╯
#
# Question: What classes are in the models package?
# Answer: The models package contains the following classes:
# - User: Represents a user entity with id, name, and email
# - UserProfile: Contains additional user information
# ...
#
# Question: How is dependency injection handled?
# Answer: ...
#
# Question: exit
# Goodbye!
```

## Testing Specific Scala Features

### Test Case Classes

Create a test file with case classes:

```scala
// test/CaseClassTest.scala
package com.example.test

case class Person(id: Long, name: String, age: Int)
case class Address(street: String, city: String, zipCode: String)
case class Employee(person: Person, address: Address, salary: Double)
```

Index and query:
```bash
maris index test/CaseClassTest.scala
maris search "Person"
maris explain Person
```

### Test Traits and Mixins

```scala
// test/TraitTest.scala
package com.example.test

trait Auditable {
  def createdAt: Long
  def updatedAt: Long
}

trait Versioned {
  def version: Int
}

class Document extends Auditable with Versioned {
  override def createdAt: Long = System.currentTimeMillis()
  override def updatedAt: Long = System.currentTimeMillis()
  override def version: Int = 1
}
```

Index and query:
```bash
maris index test/TraitTest.scala
maris ask "What traits does Document implement?"
```

### Test Companion Objects

```scala
// test/CompanionTest.scala
package com.example.test

case class User(id: Long, name: String)

object User {
  def apply(name: String): User = User(0, name)
  def fromJson(json: String): User = ???
}
```

Index and query:
```bash
maris index test/CompanionTest.scala
maris explain User
maris ask "What factory methods does User have?"
```

## Troubleshooting

### Issue: "No supported files found to index"

**Solution:** Make sure you're in the correct directory and Scala files exist:
```bash
# Check for Scala files
find . -name "*.scala" | head -10

# Try indexing with full path
maris index $(pwd)/src --recursive
```

### Issue: "Ollama is not running"

**Solution:** Start Ollama service:
```bash
# macOS/Linux
ollama serve

# Or check if it's already running
curl http://localhost:11434/api/tags
```

### Issue: "Model not found"

**Solution:** Pull the required models:
```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

### Issue: "Failed to parse file"

**Solution:** Check if the Scala file has syntax errors:
```bash
# Try compiling with scalac
scalac -version
scalac path/to/file.scala
```

### Issue: Low confidence answers

**Solution:** Index more files to provide better context:
```bash
# Index the entire project
maris index . --recursive

# Check statistics
maris stats
```

## Performance Tips

### For Large Projects

1. **Index incrementally:**
   ```bash
   # Index by module
   maris index src/main/scala/com/example/core/ -r
   maris index src/main/scala/com/example/api/ -r
   ```

2. **Use smaller embedding batches:**
   ```bash
   # In .env file
   MARIS_EMBEDDING_BATCH_SIZE=5
   ```

3. **Monitor progress:**
   ```bash
   # Watch the indexing process
   maris index src/ -r 2>&1 | tee indexing.log
   ```

### For Better Q&A Results

1. **Index related files together:**
   ```bash
   # Index all related modules
   maris index src/main/scala/com/example/ -r
   ```

2. **Use specific questions:**
   ```bash
   # Instead of: "How does this work?"
   # Use: "How does UserService authenticate users?"
   ```

3. **Explain symbols before asking:**
   ```bash
   # First understand the symbol
   maris explain UserService

   # Then ask detailed questions
   maris ask "How does UserService handle errors?"
   ```

## Example Workflow

Here's a complete workflow for a new Scala project:

```bash
# 1. Navigate to project
cd ~/projects/my-scala-app

# 2. Start fresh (optional)
maris clear  # Clears previous index

# 3. Index the project
maris index src/ --recursive

# 4. Verify indexing
maris stats

# 5. Explore the codebase
maris search "Service"
maris search "User"

# 6. Understand key components
maris explain UserService
maris explain DatabaseConfig

# 7. Ask architectural questions
maris ask "What is the overall architecture?"
maris ask "How are services organized?"

# 8. Generate documentation
mkdir -p docs/api
maris document src/main/scala/com/example/Main.scala --output docs/api/Main.md

# 9. Interactive exploration
maris interactive
```

## Advanced Usage

### Combining with Git

```bash
# Index only changed files
git diff --name-only --diff-filter=AM | grep '\.scala$' | while read file; do
  maris index "$file"
done
```

### Integration with Build Tools

```bash
# Add to sbt build
# build.sbt
lazy val indexCode = taskKey[Unit]("Index code with MARIS")
indexCode := {
  import scala.sys.process._
  "maris index src/ --recursive" !
}
```

### Scripting

```bash
#!/bin/bash
# index-and-document.sh

echo "Indexing Scala project..."
maris index src/ --recursive

echo "Generating documentation..."
mkdir -p docs/api

find src/main/scala -name "*.scala" | while read file; do
  filename=$(basename "$file" .scala)
  package=$(dirname "$file" | sed 's|src/main/scala/||' | tr '/' '.')
  maris document "$file" --output "docs/api/${package}.${filename}.md"
done

echo "Done! Check docs/api/ for generated documentation."
```

## Next Steps

1. **Explore your codebase:** Use `maris search` and `maris ask` to understand your project
2. **Generate documentation:** Create comprehensive docs with `maris document`
3. **Integrate into workflow:** Add MARIS commands to your development scripts
4. **Try other languages:** MARIS also supports Python and Java files in the same project

## Support

For issues or questions:
- Check logs in `.maris/` directory
- Review documentation in `docs/`
- Run with `--skip-validation` to bypass Ollama checks during testing