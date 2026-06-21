"""Repository Knowledge Service - central interface for repository intelligence."""

from abc import ABC, abstractmethod
from typing import List, Optional, Set, Tuple

from maris.core.models import Commit, RetrievalContext, Symbol


class RepositoryKnowledgeService(ABC):
    """
    Abstract interface for the Repository Knowledge Layer.

    This is the central abstraction that all agents use to interact with
    repository data. It provides unified access to symbols, dependencies,
    semantic search, and commit history.
    """

    # Symbol Operations

    @abstractmethod
    def find_symbol(self, name: str, language: Optional[str] = None) -> List[Symbol]:
        """
        Find symbols by name across the repository.

        Args:
            name: Symbol name to search for
            language: Optional language filter for disambiguation

        Returns:
            List of matching symbols with metadata
        """
        pass

    @abstractmethod
    def get_symbol_by_id(self, symbol_id: str) -> Optional[Symbol]:
        """
        Retrieve a specific symbol by unique identifier.

        Args:
            symbol_id: Unique symbol identifier

        Returns:
            Symbol if found, None otherwise
        """
        pass

    @abstractmethod
    def find_symbols_in_file(self, file_path: str) -> List[Symbol]:
        """
        Get all symbols defined in a specific file.

        Args:
            file_path: Relative path from repository root

        Returns:
            List of symbols ordered by line number
        """
        pass

    # Dependency Operations

    @abstractmethod
    def find_callers(self, symbol: Symbol) -> List[Symbol]:
        """
        Find all symbols that call or reference the given symbol.

        Traverses the dependency graph backwards to find incoming references.

        Args:
            symbol: Symbol to find callers for

        Returns:
            List of symbols that reference the given symbol
        """
        pass

    @abstractmethod
    def find_callees(self, symbol: Symbol) -> List[Symbol]:
        """
        Find all symbols called or referenced by the given symbol.

        Traverses the dependency graph forwards to find outgoing references.

        Args:
            symbol: Symbol to find callees for

        Returns:
            List of symbols referenced by the given symbol
        """
        pass

    @abstractmethod
    def get_dependency_chain(self, from_symbol: Symbol, to_symbol: Symbol) -> List[List[Symbol]]:
        """
        Find all paths between two symbols in the dependency graph.

        Args:
            from_symbol: Starting symbol
            to_symbol: Target symbol

        Returns:
            List of paths, where each path is a list of symbols.
            Empty list if no path exists.
        """
        pass

    # Retrieval Operations

    @abstractmethod
    def retrieve_context(self, question: str, max_symbols: int = 10) -> RetrievalContext:
        """
        Retrieve relevant context for a given question.

        Combines vector search with symbol expansion to build comprehensive
        context for LLM reasoning.

        Args:
            question: Natural language question
            max_symbols: Maximum number of primary symbols to retrieve

        Returns:
            Structured context ready for LLM consumption
        """
        pass

    @abstractmethod
    def semantic_search(self, query: str, limit: int = 20) -> List[Tuple[Symbol, float]]:
        """
        Perform pure vector similarity search.

        This is typically used as the first stage in the retrieval pipeline,
        followed by symbol expansion and dependency traversal.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of (symbol, similarity_score) tuples, ordered by relevance
        """
        pass

    # Impact Analysis Operations

    @abstractmethod
    def impacted_symbols(self, symbol: Symbol, depth: int = 3) -> Set[Symbol]:
        """
        Find all symbols potentially impacted by changes to the given symbol.

        Traverses callers up to the specified depth to identify all symbols
        that may be affected by modifications.

        Args:
            symbol: Symbol being modified
            depth: Maximum traversal depth

        Returns:
            Set of unique symbols that may be impacted
        """
        pass

    @abstractmethod
    def impacted_files(self, symbol: Symbol) -> Set[str]:
        """
        Find all files potentially impacted by changes to the given symbol.

        Args:
            symbol: Symbol being modified

        Returns:
            Set of file paths that may be impacted
        """
        pass

    # History Operations

    @abstractmethod
    def get_symbol_history(self, symbol: Symbol, limit: int = 50) -> List[Commit]:
        """
        Get commit history for a specific symbol.

        Uses git blame and log data to track symbol evolution.

        Args:
            symbol: Symbol to get history for
            limit: Maximum number of commits to return

        Returns:
            List of commits that modified the symbol, most recent first
        """
        pass

    @abstractmethod
    def find_symbols_changed_in_commit(self, commit_hash: str) -> List[Symbol]:
        """
        Get all symbols modified in a specific commit.

        Useful for understanding the scope of changes in a commit.

        Args:
            commit_hash: Git commit hash

        Returns:
            List of symbols modified in the commit
        """
        pass

    # Repository Operations

    @abstractmethod
    def get_repository_stats(self) -> dict:
        """
        Get statistics about the indexed repository.

        Returns:
            Dictionary containing:
                - total_files: Number of indexed files
                - total_symbols: Number of extracted symbols
                - total_dependencies: Number of dependency relationships
                - languages: List of detected languages
                - last_indexed: Timestamp of last indexing operation
        """
        pass

    @abstractmethod
    def is_indexed(self, file_path: str) -> bool:
        """
        Check if a file has been indexed.

        Args:
            file_path: Relative path from repository root

        Returns:
            True if file is indexed, False otherwise
        """
        pass


# Made with Bob
