"""Core domain models for MARIS."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SymbolType(Enum):
    """Types of code symbols that can be extracted."""

    PACKAGE = "package"
    MODULE = "module"
    CLASS = "class"
    TRAIT = "trait"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    FIELD = "field"
    VARIABLE = "variable"
    CONSTANT = "constant"


@dataclass
class Symbol:
    """
    Represents a code symbol (class, function, method, etc.) in the repository.

    Attributes:
        id: Unique identifier for the symbol
        name: Symbol name (e.g., "GraphRunner.retryExecuteNode")
        type: Type of symbol (class, function, method, etc.)
        file_path: Relative path from repository root
        language: Programming language (scala, java, python, typescript)
        start_line: Starting line number in the file
        end_line: Ending line number in the file
        signature: Function/method signature if applicable
        docstring: Documentation string if present
        parent_id: ID of parent symbol (e.g., class for a method)
        metadata: Additional language-specific data
    """

    id: str
    name: str
    type: SymbolType
    file_path: str
    language: str
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate symbol data after initialization."""
        if self.start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {self.start_line}")
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )

    @property
    def line_count(self) -> int:
        """Calculate the number of lines in this symbol."""
        return self.end_line - self.start_line + 1

    @property
    def qualified_name(self) -> str:
        """Get the fully qualified name of the symbol."""
        return self.name

    def to_dict(self) -> Dict[str, Any]:
        """Convert symbol to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "file_path": self.file_path,
            "language": self.language,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
            "docstring": self.docstring,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }


@dataclass
class Commit:
    """
    Represents a git commit with associated metadata.

    Attributes:
        hash: Commit SHA hash
        author: Commit author name
        timestamp: Commit timestamp
        message: Commit message
        files_changed: List of file paths changed in this commit
        symbols_changed: List of symbol IDs changed in this commit
    """

    hash: str
    author: str
    timestamp: datetime
    message: str
    files_changed: List[str] = field(default_factory=list)
    symbols_changed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert commit to dictionary representation."""
        return {
            "hash": self.hash,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "files_changed": self.files_changed,
            "symbols_changed": self.symbols_changed,
        }


@dataclass
class RetrievalContext:
    """
    Context retrieved for answering questions or generating documentation.

    Attributes:
        primary_symbols: Most relevant symbols for the query
        expanded_symbols: Additional symbols from dependency expansion
        related_files: Related file paths
        metadata: Additional context information
    """

    primary_symbols: List[Symbol] = field(default_factory=list)
    expanded_symbols: List[Symbol] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def all_symbols(self) -> List[Symbol]:
        """Get all symbols (primary + expanded)."""
        return self.primary_symbols + self.expanded_symbols

    @property
    def symbol_count(self) -> int:
        """Get total number of symbols in context."""
        return len(self.all_symbols)

    def to_llm_context(self, include_expanded: bool = True) -> str:
        """
        Format context for LLM consumption.

        Args:
            include_expanded: Whether to include expanded symbols

        Returns:
            Formatted string suitable for LLM input
        """
        lines = ["# Repository Context\n"]

        if self.primary_symbols:
            lines.append("## Primary Symbols\n")
            for symbol in self.primary_symbols:
                lines.append(f"### {symbol.name} ({symbol.type.value})")
                lines.append(f"File: {symbol.file_path}:{symbol.start_line}-{symbol.end_line}")
                if symbol.signature:
                    lines.append(f"Signature: {symbol.signature}")
                if symbol.docstring:
                    lines.append(f"Documentation: {symbol.docstring}")
                lines.append("")

        if include_expanded and self.expanded_symbols:
            lines.append("## Related Symbols\n")
            for symbol in self.expanded_symbols:
                lines.append(f"- {symbol.name} ({symbol.type.value}) in {symbol.file_path}")

        if self.related_files:
            lines.append("\n## Related Files\n")
            for file_path in self.related_files:
                lines.append(f"- {file_path}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary representation."""
        return {
            "primary_symbols": [s.to_dict() for s in self.primary_symbols],
            "expanded_symbols": [s.to_dict() for s in self.expanded_symbols],
            "related_files": self.related_files,
            "metadata": self.metadata,
        }


@dataclass
class Dependency:
    """
    Represents a dependency relationship between symbols.

    Attributes:
        id: Unique identifier for the dependency
        from_symbol_id: Source symbol ID
        to_symbol_id: Target symbol ID
        relationship_type: Type of relationship (calls, imports, extends, implements)
    """

    id: str
    from_symbol_id: str
    to_symbol_id: str
    relationship_type: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert dependency to dictionary representation."""
        return {
            "id": self.id,
            "from_symbol_id": self.from_symbol_id,
            "to_symbol_id": self.to_symbol_id,
            "relationship_type": self.relationship_type,
        }


@dataclass
class IndexingResult:
    """
    Result of an indexing operation.

    Attributes:
        files_processed: Number of files processed
        symbols_extracted: Number of symbols extracted
        dependencies_found: Number of dependencies found
        embeddings_generated: Number of embeddings generated
        errors: List of errors encountered
        duration_seconds: Time taken for indexing
    """

    files_processed: int = 0
    symbols_extracted: int = 0
    dependencies_found: int = 0
    embeddings_generated: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate (files without errors / total files)."""
        if self.files_processed == 0:
            return 0.0
        return (self.files_processed - len(self.errors)) / self.files_processed

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "files_processed": self.files_processed,
            "symbols_extracted": self.symbols_extracted,
            "dependencies_found": self.dependencies_found,
            "embeddings_generated": self.embeddings_generated,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "success_rate": self.success_rate,
        }


# Made with Bob
