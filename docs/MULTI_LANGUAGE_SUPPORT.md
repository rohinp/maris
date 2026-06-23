# Multi-Language Parser Support

## Overview

MARIS now supports parsing and indexing multiple programming languages using tree-sitter parsers. This document describes the implementation, supported languages, and how to extend support to additional languages.

## Supported Languages

### ✅ Fully Implemented

| Language | Parser | Extensions | Test Coverage | Status |
|----------|--------|------------|---------------|--------|
| Python | `PythonParser` | `.py` | High | Production |
| Java | `JavaParser` | `.java` | 94% | Production |
| Scala | `ScalaParser` | `.scala` | 91% | Production |

### 📝 Planned (Infrastructure Ready)

| Language | Extensions | Tree-sitter Grammar | Status |
|----------|------------|---------------------|--------|
| Kotlin | `.kt`, `.kts` | ✅ Installed | Planned |
| JavaScript | `.js`, `.jsx` | ✅ Installed | Planned |
| TypeScript | `.ts`, `.tsx` | ✅ Installed | Planned |
| Go | `.go` | ✅ Installed | Planned |
| Bash | `.sh`, `.bash` | ✅ Installed | Planned |
| Rust | `.rs` | ✅ Installed | Planned |

## Architecture

### ParserFactory Pattern

The `ParserFactory` class provides centralized parser management:

```python
from maris.indexing import ParserFactory

# Get parser for a file
parser = ParserFactory.get_parser("Main.java")  # Returns JavaParser instance
parser = ParserFactory.get_parser("App.scala")  # Returns ScalaParser instance
parser = ParserFactory.get_parser("main.py")    # Returns PythonParser instance

# Check language support
ParserFactory.is_supported("main.kt")      # True (planned)
ParserFactory.is_implemented("main.kt")    # False (not yet implemented)

# Get language name
ParserFactory.get_language_name("App.scala")  # "scala"

# Get all supported extensions
extensions = ParserFactory.get_supported_extensions()
# ['.py', '.java', '.scala', '.kt', '.kts', '.js', '.jsx', '.ts', '.tsx', '.go', '.sh', '.bash', '.rs']

# Get implementation status
status = ParserFactory.get_parser_status()
# {
#   'python': {'implemented': True, 'extensions': ['.py'], 'parser_class': 'PythonParser'},
#   'java': {'implemented': True, 'extensions': ['.java'], 'parser_class': 'JavaParser'},
#   'scala': {'implemented': True, 'extensions': ['.scala'], 'parser_class': 'ScalaParser'},
#   'kotlin': {'implemented': False, 'extensions': ['.kt', '.kts'], 'parser_class': None},
#   ...
# }
```

### Parser Hierarchy

```
TreeSitterParser (Abstract Base Class)
├── PythonParser
├── JavaParser
├── ScalaParser
└── [Future parsers...]
```

All parsers inherit from `TreeSitterParser` and implement:
- `_setup_parser()`: Initialize tree-sitter grammar
- `_extract_symbols()`: Extract code symbols (classes, functions, etc.)
- `_extract_dependencies()`: Extract imports and relationships

## Language-Specific Features

### Python Parser

**Extracts:**
- Classes, functions, methods
- Async functions
- Decorators
- Docstrings

**Dependencies:**
- Import statements
- Class inheritance

### Java Parser

**Extracts:**
- Classes, interfaces, enums
- Methods, constructors, fields
- Nested classes
- Generic types
- Javadoc comments

**Dependencies:**
- Import statements
- Class inheritance (`extends`)
- Interface implementation (`implements`)

**Example:**
```java
package com.example;

import java.util.List;

/**
 * User management service
 */
public class UserService extends BaseService implements Auditable {
    private final UserRepository repository;

    public UserService(UserRepository repository) {
        this.repository = repository;
    }

    public List<User> findAll() {
        return repository.findAll();
    }
}
```

Extracts:
- Class: `UserService` with Javadoc
- Field: `repository`
- Constructor: `UserService(UserRepository)`
- Method: `findAll()`
- Dependencies: `BaseService` (extends), `Auditable` (implements), imports

### Scala Parser

**Extracts:**
- Classes, traits, objects
- Case classes
- Companion objects
- Functions, vals, vars
- Pattern matching
- Implicit classes
- Scaladoc comments

**Dependencies:**
- Import statements
- Class inheritance (`extends`)
- Trait mixing (`with`)

**Example:**
```scala
package com.example

import scala.collection.mutable.ListBuffer

/**
 * User management service
 */
class UserService(repository: UserRepository) extends BaseService with Auditable {
  def findAll(): List[User] = {
    repository.findAll()
  }
}

object UserService {
  def apply(repository: UserRepository): UserService =
    new UserService(repository)
}

case class User(id: Long, name: String, email: String)
```

Extracts:
- Class: `UserService` with Scaladoc
- Method: `findAll()`
- Object: `UserService` (companion)
- Function: `apply` in companion object
- Case class: `User` with fields
- Dependencies: `BaseService` (extends), `Auditable` (with), imports

## Integration with IndexingAgent

The `IndexingAgent` automatically uses `ParserFactory` to select the appropriate parser:

```python
from maris.agents import IndexingAgent

agent = IndexingAgent(
    metadata_store=metadata_store,
    vector_store=vector_store,
    embeddings_service=embeddings_service
)

# Index a repository with mixed languages
result = agent.index_repository("/path/to/repo")
# Automatically detects and parses .py, .java, .scala files

# Index specific files
result = agent.index_files([
    "src/main/java/Main.java",
    "src/main/scala/App.scala",
    "src/utils.py"
])
```

## Testing

### Test Coverage

All parsers have comprehensive test suites:

```bash
# Test all parsers
pytest tests/test_parser_factory.py tests/test_java_parser.py tests/test_scala_parser.py -v

# Test specific parser
pytest tests/test_java_parser.py -v
pytest tests/test_scala_parser.py -v

# With coverage
pytest tests/test_java_parser.py --cov=src/maris/indexing/java_parser --cov-report=html
```

### Test Structure

Each parser test suite includes:
1. **Initialization tests**: Parser setup and configuration
2. **Symbol extraction tests**: Classes, methods, fields, etc.
3. **Dependency extraction tests**: Imports, inheritance, interfaces
4. **Edge case tests**: Nested structures, generics, empty files
5. **Integration tests**: Real-world code examples

## Adding a New Language

To add support for a new language:

### 1. Install Tree-sitter Grammar

```bash
pip install tree-sitter-<language>
```

### 2. Create Parser Class

Create `src/maris/indexing/<language>_parser.py`:

```python
from tree_sitter import Language
from maris.indexing.parser import TreeSitterParser
from maris.core.models import Symbol, Dependency

class KotlinParser(TreeSitterParser):
    """Parser for Kotlin source files."""

    def __init__(self):
        super().__init__(language="kotlin")

    def _setup_parser(self) -> None:
        """Initialize Kotlin tree-sitter parser."""
        import tree_sitter_kotlin

        KOTLIN_LANGUAGE = Language(tree_sitter_kotlin.language())
        self.parser.set_language(KOTLIN_LANGUAGE)

    def _extract_symbols(self, tree, source_code: str, file_path: str) -> list[Symbol]:
        """Extract symbols from Kotlin AST."""
        # Implementation here
        pass

    def _extract_dependencies(self, tree, source_code: str, file_path: str) -> list[Dependency]:
        """Extract dependencies from Kotlin AST."""
        # Implementation here
        pass
```

### 3. Register Parser

Update `src/maris/indexing/parser_factory.py`:

```python
from maris.indexing.kotlin_parser import KotlinParser

# In ParserFactory class initialization
ParserFactory.register_parser("KotlinParser", KotlinParser)
```

### 4. Update Exports

Update `src/maris/indexing/__init__.py`:

```python
from maris.indexing.kotlin_parser import KotlinParser

__all__ = [
    # ... existing exports
    "KotlinParser",
]
```

### 5. Create Tests

Create `tests/test_kotlin_parser.py` following the pattern of existing parser tests.

### 6. Run Tests

```bash
pytest tests/test_kotlin_parser.py -v --cov=src/maris/indexing/kotlin_parser
```

## Tree-sitter Query Examples

### Finding Classes

```python
class_query = language.query("""
    (class_declaration
        name: (identifier) @class_name
        body: (class_body) @class_body
    ) @class
""")

matches = class_query.matches(tree.root_node)
```

### Finding Methods

```python
method_query = language.query("""
    (method_declaration
        name: (identifier) @method_name
        parameters: (formal_parameters) @params
        body: (block)? @body
    ) @method
""")
```

### Finding Imports

```python
import_query = language.query("""
    (import_declaration
        (scoped_identifier) @import_path
    ) @import
""")
```

## Known Limitations

### Java Parser
- Interface implementation extraction depends on tree-sitter grammar structure
- Some complex generic type parameters may not be fully captured

### Scala Parser
- Abstract method declarations without implementations may not be captured by tree-sitter grammar
- Some advanced Scala features (macros, type lambdas) may have limited support

### General
- All parsers use placeholder IDs (`external:ClassName`) for unresolved external dependencies
- Documentation extraction quality depends on tree-sitter grammar support for doc comments

## Performance Considerations

- Tree-sitter parsers are fast and memory-efficient
- Parsing is done incrementally during indexing
- Large files (>10,000 lines) may take a few seconds to parse
- Parallel processing is used for multiple files

## Future Enhancements

1. **Additional Languages**: Kotlin, JavaScript, TypeScript, Go, Bash, Rust
2. **Enhanced Symbol Extraction**: More detailed type information, annotations
3. **Cross-language References**: Track dependencies across language boundaries
4. **Language-specific Queries**: Optimize queries for each language's idioms
5. **Incremental Parsing**: Update only changed portions of files

## References

- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Tree-sitter Python Bindings](https://github.com/tree-sitter/py-tree-sitter)
- [MARIS Architecture](./ARCHITECTURE.md)
- [Multi-Language Parser Specification](.codex/specs/multi-language-parser-support.md)