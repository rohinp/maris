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


@dataclass
class GitChangeSet:
    """
    Represents changes detected in a Git repository since last indexing.

    Attributes:
        last_commit: Hash of the last indexed commit (None if first time)
        current_commit: Hash of the current HEAD commit
        added_files: List of newly added files
        modified_files: List of modified files
        deleted_files: List of deleted files
        renamed_files: List of (old_path, new_path) tuples for renamed files
        is_clean: True if working directory is clean (no uncommitted changes)
        total_changes: Total number of changed files
    """

    last_commit: Optional[str]
    current_commit: str
    added_files: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    renamed_files: List[tuple[str, str]] = field(default_factory=list)
    is_clean: bool = True

    @property
    def total_changes(self) -> int:
        """Get total number of changed files."""
        return (
            len(self.added_files)
            + len(self.modified_files)
            + len(self.deleted_files)
            + len(self.renamed_files)
        )

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return self.total_changes > 0

    @property
    def files_to_reindex(self) -> List[str]:
        """Get list of files that need to be re-indexed (added + modified + renamed destinations)."""
        files = self.added_files + self.modified_files
        files.extend([new_path for _, new_path in self.renamed_files])
        return files

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "last_commit": self.last_commit,
            "current_commit": self.current_commit,
            "added_files": self.added_files,
            "modified_files": self.modified_files,
            "deleted_files": self.deleted_files,
            "renamed_files": self.renamed_files,
            "is_clean": self.is_clean,
            "total_changes": self.total_changes,
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


@dataclass
class EdgeCase:
    """
    Represents a detected edge case in code.

    Attributes:
        type: Type of edge case (null_check, boundary, error_path, etc.)
        description: Human-readable description
        location: File:line where detected
        is_handled: Whether it's currently handled
        suggestion: How to handle it
        severity: Severity level (high, medium, low)
    """

    type: str
    description: str
    location: str
    is_handled: bool
    suggestion: Optional[str] = None
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        """Convert edge case to dictionary representation."""
        return {
            "type": self.type,
            "description": self.description,
            "location": self.location,
            "is_handled": self.is_handled,
            "suggestion": self.suggestion,
            "severity": self.severity,
        }


@dataclass
class ImpactAnalysisResult:
    """
    Result of impact analysis.

    Attributes:
        target_symbol: Symbol being analyzed
        direct_callers: Symbols that directly call the target
        indirect_callers: Symbols that indirectly call the target
        affected_files: Files that may be affected
        affected_tests: Test symbols that cover the target
        edge_cases: Detected edge cases
        breaking_changes: Potential breaking changes
        recommendations: Actionable recommendations
        confidence: Confidence level (high, medium, low)
    """

    target_symbol: Symbol
    direct_callers: List[Symbol] = field(default_factory=list)
    indirect_callers: List[Symbol] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    affected_tests: List[Symbol] = field(default_factory=list)
    edge_cases: List[EdgeCase] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: str = "medium"

    @property
    def total_impact(self) -> int:
        """Get total number of impacted symbols."""
        return len(self.direct_callers) + len(self.indirect_callers)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "target_symbol": self.target_symbol.to_dict(),
            "direct_callers": [s.to_dict() for s in self.direct_callers],
            "indirect_callers": [s.to_dict() for s in self.indirect_callers],
            "affected_files": self.affected_files,
            "affected_tests": [s.to_dict() for s in self.affected_tests],
            "edge_cases": [e.to_dict() for e in self.edge_cases],
            "breaking_changes": self.breaking_changes,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
        }


# Made with Bob
