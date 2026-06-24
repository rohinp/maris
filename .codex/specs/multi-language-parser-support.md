# Multi-Language Parser Support Specification

## Overview

This specification outlines the implementation plan for adding support for multiple programming languages to MARIS using tree-sitter parsers. The goal is to extend MARIS beyond Python to support Scala, Java, Kotlin, JavaScript, TypeScript, Go, Shell scripts, and Rust.

Last updated: 2026-06-24

Current production parser support is Python, Java, and Scala. Other languages are mapped as planned extensions in `ParserFactory` but do not have registered parser implementations yet.

## Implementation Status

### ✅ Phase 1: Infrastructure (COMPLETED)
- ✅ **Base Parser Class** (`src/maris/indexing/parser.py`): Abstract `TreeSitterParser` class with common functionality
- ✅ **Python Parser** (`src/maris/indexing/python_parser.py`): Full implementation for Python
- ✅ **Tree-sitter Integration**: Core tree-sitter library (v0.21.0+) with language grammar packages listed in `requirements.txt`
- ✅ **Symbol Model**: Language-agnostic `Symbol` and `Dependency` models
- ✅ **Indexing Agent**: LangGraph-based agent that can handle multiple languages
- ✅ **ParserFactory** (`src/maris/indexing/parser_factory.py`): Factory pattern for language-specific parser selection
- ✅ **Language Detection**: Automatic detection based on file extension (13 extensions mapped to 9 languages)
- ✅ **Comprehensive Tests**: 20 tests for ParserFactory with 100% coverage

### ✅ Phase 2: JVM Languages (COMPLETED)
- ✅ **Java Parser** (`src/maris/indexing/java_parser.py`): 545 lines, 20 tests, 94% coverage
  - Extracts: classes, interfaces, enums, methods, constructors, fields
  - Handles: nested classes, generic types, Javadoc comments
  - Dependencies: imports, extends, implements
- ✅ **Scala Parser** (`src/maris/indexing/scala_parser.py`): 571 lines, 21 tests, 91% coverage
  - Extracts: classes, traits, objects, functions, val/var
  - Handles: case classes, companion objects, pattern matching, implicit classes
  - Dependencies: imports, extends, trait mixing (with)

### 📝 Future Phases
- **Kotlin**: Planned (tree-sitter-kotlin installed)
- **JavaScript/TypeScript**: Planned (tree-sitter-javascript, tree-sitter-typescript installed)
- **Go**: Planned (tree-sitter-go installed)
- **Bash**: Planned (tree-sitter-bash installed)
- **Rust**: Planned (tree-sitter-rust installed)

## Target Languages

### Priority 1: JVM Languages
1. **Java** - Enterprise applications, Android
2. **Scala** - Big data, functional programming
3. **Kotlin** - Modern JVM, Android

### Priority 2: Web Languages
4. **JavaScript** - Frontend, Node.js
5. **TypeScript** - Type-safe JavaScript

### Priority 3: Systems Languages
6. **Go** - Cloud-native, microservices
7. **Rust** - Systems programming, performance-critical

### Priority 4: Scripting
8. **Shell** (Bash) - DevOps, automation

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                   IndexingAgent                          │
│              (Language-agnostic orchestrator)            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 ParserFactory                            │
│         (Selects parser based on file extension)        │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│ TreeSitterParser │    │  Language-       │
│   (Base Class)   │◄───│  Specific        │
└──────────────────┘    │  Parsers         │
                        └──────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐    ┌──────────────┐      ┌──────────────┐
│PythonParser  │    │ JavaParser   │  ... │ RustParser   │
└──────────────┘    └──────────────┘      └──────────────┘
```

### Key Design Principles

1. **Inheritance**: All parsers inherit from `TreeSitterParser` base class
2. **Consistency**: All parsers extract the same `Symbol` and `Dependency` models
3. **Extensibility**: Easy to add new languages without modifying existing code
4. **Testability**: Each parser has comprehensive unit tests
5. **Performance**: Parsers use tree-sitter's efficient C-based parsing

## Implementation Plan

### Phase 1: Infrastructure (Foundation)

#### 1.1 Parser Factory

Create `src/maris/indexing/parser_factory.py`:

```python
class ParserFactory:
    """Factory for creating language-specific parsers."""

    _parsers = {
        '.py': 'PythonParser',
        '.java': 'JavaParser',
        '.scala': 'ScalaParser',
        '.kt': 'KotlinParser',
        '.js': 'JavaScriptParser',
        '.ts': 'TypeScriptParser',
        '.go': 'GoParser',
        '.sh': 'ShellParser',
        '.rs': 'RustParser',
    }

    @classmethod
    def get_parser(cls, file_path: str) -> Optional[TreeSitterParser]:
        """Get appropriate parser for file."""
        pass

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get list of supported file extensions."""
        pass
```

#### 1.2 Update Requirements

Add tree-sitter language bindings to `requirements.txt`:

```
# Language parsers
tree-sitter-python>=0.21.0
tree-sitter-java>=0.21.0
tree-sitter-scala>=0.21.0
tree-sitter-kotlin>=0.1.0
tree-sitter-javascript>=0.21.0
tree-sitter-typescript>=0.21.0
tree-sitter-go>=0.21.0
tree-sitter-bash>=0.21.0
tree-sitter-rust>=0.21.0
```

#### 1.3 Language Detection Enhancement

Update `IndexingAgent._detect_language()` to use ParserFactory.

### Phase 2: Parser Implementations

Each parser follows this template structure:

#### 2.1 Java Parser

**Key Nodes to Extract:**
- `class_declaration` → CLASS
- `interface_declaration` → INTERFACE
- `method_declaration` → METHOD
- `field_declaration` → FIELD
- `constructor_declaration` → METHOD
- `import_declaration` → Dependencies

**Challenges:**
- Package declarations
- Nested classes
- Generic types
- Annotations

#### 2.2 Scala Parser

**Key Nodes to Extract:**
- `class_definition` → CLASS
- `trait_definition` → TRAIT
- `object_definition` → MODULE
- `function_definition` → FUNCTION
- `val_definition` / `var_definition` → FIELD
- `import_declaration` → Dependencies

**Challenges:**
- Traits and objects
- Pattern matching
- Implicit parameters
- Type parameters

#### 2.3 Kotlin Parser

**Key Nodes to Extract:**
- `class_declaration` → CLASS
- `interface_declaration` → INTERFACE
- `object_declaration` → MODULE
- `function_declaration` → FUNCTION
- `property_declaration` → FIELD
- `import_header` → Dependencies

**Challenges:**
- Data classes
- Extension functions
- Companion objects
- Nullable types

#### 2.4 JavaScript Parser

**Key Nodes to Extract:**
- `class_declaration` → CLASS
- `function_declaration` → FUNCTION
- `arrow_function` → FUNCTION
- `method_definition` → METHOD
- `variable_declaration` → VARIABLE
- `import_statement` / `require` → Dependencies

**Challenges:**
- Multiple function syntaxes
- Dynamic imports
- CommonJS vs ES6 modules
- Prototype-based inheritance

#### 2.5 TypeScript Parser

**Key Nodes to Extract:**
- Same as JavaScript, plus:
- `interface_declaration` → INTERFACE
- `type_alias_declaration` → TYPE
- `enum_declaration` → CONSTANT

**Challenges:**
- Type annotations
- Generics
- Decorators
- Namespaces

#### 2.6 Go Parser

**Key Nodes to Extract:**
- `type_declaration` (struct) → CLASS
- `type_declaration` (interface) → INTERFACE
- `function_declaration` → FUNCTION
- `method_declaration` → METHOD
- `const_declaration` → CONSTANT
- `var_declaration` → VARIABLE
- `import_declaration` → Dependencies

**Challenges:**
- Package structure
- Receiver methods
- Goroutines
- Interfaces (implicit implementation)

#### 2.7 Shell Parser

**Key Nodes to Extract:**
- `function_definition` → FUNCTION
- `variable_assignment` → VARIABLE
- `command` (sourcing) → Dependencies

**Challenges:**
- Dynamic variable expansion
- Command substitution
- Limited structure
- Multiple shell dialects

#### 2.8 Rust Parser

**Key Nodes to Extract:**
- `struct_item` → CLASS
- `trait_item` → TRAIT
- `impl_item` → Implementation block
- `function_item` → FUNCTION
- `const_item` → CONSTANT
- `use_declaration` → Dependencies

**Challenges:**
- Ownership and lifetimes
- Macros
- Trait implementations
- Module system

### Phase 3: Testing Strategy

#### 3.1 Test Structure

For each language, create comprehensive tests in `tests/test_<language>_parser.py` with fixtures in `tests/fixtures/<language>/`.

#### 3.2 Test Coverage Requirements

Each parser test suite must include:

1. **Symbol Extraction Tests** (minimum 10 tests)
   - Classes/Structs
   - Interfaces/Traits
   - Functions/Methods
   - Fields/Properties
   - Constants
   - Nested structures
   - Edge cases

2. **Dependency Extraction Tests** (minimum 5 tests)
   - Import statements
   - Function calls
   - Inheritance
   - Interface implementation
   - Cross-file references

3. **Integration Tests** (minimum 3 tests)
   - Full file parsing
   - Multi-file project
   - Error handling

4. **Performance Tests** (minimum 1 test)
   - Large file parsing (>1000 lines)

### Phase 4: CLI Integration

Update `src/maris/cli/main.py` to support multi-language indexing with language filtering and statistics.

### Phase 5: Documentation

#### 5.1 Update Documentation

1. **README.md**: Add supported languages section
2. **GETTING_STARTED.md**: Add multi-language examples
3. **ARCHITECTURE.md**: Document parser architecture
4. **New: LANGUAGE_SUPPORT.md**: Detailed language support matrix

#### 5.2 Language Support Matrix

| Language   | Status | Classes | Functions | Interfaces | Dependencies | Notes |
|------------|--------|---------|-----------|------------|--------------|-------|
| Python     | ✅ Full | ✅ | ✅ | ❌ | ✅ | Complete |
| Java       | ✅ Implemented | ✅ | ✅ | ✅ | ✅ | Parser and tests implemented |
| Scala      | ✅ Implemented | ✅ | ✅ | ❌ | ✅ | Traits/objects supported |
| Kotlin     | 📝 Planned | - | - | - | - | Not started |
| JavaScript | 📝 Planned | - | - | - | - | Not started |
| TypeScript | 📝 Planned | - | - | - | - | Not started |
| Go         | 📝 Planned | - | - | - | - | Not started |
| Shell      | 📝 Planned | - | - | - | - | Not started |
| Rust       | 📝 Planned | - | - | - | - | Not started |

### Phase 6: Performance Optimization

Implement parallel parsing and caching for large repositories.

## Implementation Timeline

### Week 1-2: Infrastructure
- [x] Create ParserFactory
- [x] Update requirements.txt
- [x] Update IndexingAgent for multi-language support
- [x] Create test infrastructure

### Week 3-4: JVM Languages
- [x] Implement JavaParser
- [x] Implement ScalaParser
- [ ] Implement KotlinParser
- [x] Write comprehensive tests for Java and Scala

### Week 5-6: Web Languages
- [ ] Implement JavaScriptParser
- [ ] Implement TypeScriptParser
- [ ] Write comprehensive tests

### Week 7-8: Systems Languages
- [ ] Implement GoParser
- [ ] Implement RustParser
- [ ] Implement ShellParser
- [ ] Write comprehensive tests

### Week 9-10: Integration & Polish
- [ ] CLI integration
- [ ] Documentation
- [ ] Performance optimization
- [ ] End-to-end testing

## Success Criteria

### Functional Requirements
- [x] Python, Java, and Scala parsers are implemented and registered
- [ ] All 9 planned languages supported
- [ ] Symbol extraction works for all planned languages
- [ ] Dependency extraction works for all planned languages
- [x] CLI indexes files for implemented parser extensions
- [x] Parser tests pass with >80% coverage for implemented parsers

### Performance Requirements
- [ ] Parse 1000 files in <60 seconds
- [ ] Memory usage <2GB for large repositories
- [x] Incremental indexing works through Git Agent

### Quality Requirements
- [ ] Comprehensive documentation for all planned languages
- [x] Clear behavior for unsupported/planned parser extensions through `get_implemented_extensions()`
- [x] Backward compatibility maintained for Python parser API
- [x] No breaking changes to existing API

## Risks and Mitigations

### Risk 1: Tree-sitter Grammar Availability
**Risk**: Some language grammars may not be mature or well-maintained.
**Mitigation**: Evaluate grammar quality before implementation, have fallback options.

### Risk 2: Language-Specific Complexity
**Risk**: Some languages have complex features that are hard to parse.
**Mitigation**: Start with basic symbol extraction, iteratively add support for complex features.

### Risk 3: Performance Impact
**Risk**: Parsing multiple languages may slow down indexing.
**Mitigation**: Implement parallel parsing, add caching layer, profile and optimize.

### Risk 4: Maintenance Burden
**Risk**: Supporting 9 languages increases maintenance complexity.
**Mitigation**: Comprehensive test coverage, clear documentation, modular design.

## Future Enhancements

### Phase 7: Additional Languages
- C/C++, C#, Ruby, PHP, Swift, Dart

### Phase 8: Advanced Features
- Cross-language dependency tracking
- Language-specific code metrics
- Syntax highlighting in documentation
- Language-aware search

### Phase 9: AI Enhancements
- LLM-based symbol summarization per language
- Language-specific code explanations
- Cross-language code translation suggestions

## References

### Tree-sitter Resources
- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Tree-sitter Language Grammars](https://github.com/tree-sitter)
- [Tree-sitter Python Bindings](https://github.com/tree-sitter/py-tree-sitter)

### Language-Specific Resources
- [Java Language Specification](https://docs.oracle.com/javase/specs/)
- [Scala Language Specification](https://scala-lang.org/files/archive/spec/2.13/)
- [Kotlin Language Reference](https://kotlinlang.org/docs/reference/)
- [JavaScript MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [Go Language Specification](https://go.dev/ref/spec)
- [Rust Reference](https://doc.rust-lang.org/reference/)
- [Bash Reference Manual](https://www.gnu.org/software/bash/manual/)

---

**Status**: Active - Python, Java, and Scala implemented; remaining languages planned
**Created**: 2026-06-23
**Last Updated**: 2026-06-24
**Author**: Bob (AI Assistant)
**Related**: `.codex/specs/indexing-agent.md`, `src/maris/indexing/parser.py`
