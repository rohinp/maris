"""Concrete implementation of the Repository Knowledge Service."""

import logging
from collections import deque
from typing import List, Optional, Set, Tuple

from maris.core.models import Commit, RetrievalContext, Symbol
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService
from maris.knowledge.service import RepositoryKnowledgeService
from maris.storage.metadata_store import MetadataStore
from maris.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RepositoryKnowledgeImpl(RepositoryKnowledgeService):
    """
    Concrete implementation of the Repository Knowledge Service.

    Integrates metadata store, vector store, and embedding service to provide
    unified access to repository intelligence.
    """

    def __init__(
        self,
        metadata_store: MetadataStore,
        vector_store: VectorStore,
        embedding_service: OllamaEmbeddingService,
    ):
        """
        Initialize the repository knowledge service.

        Args:
            metadata_store: DuckDB metadata store for structured data
            vector_store: LanceDB vector store for embeddings
            embedding_service: Ollama embedding service for generating embeddings
        """
        self.metadata_store = metadata_store
        self.vector_store = vector_store
        self.embedding_service = embedding_service

        logger.info("Initialized RepositoryKnowledgeImpl")

    # Symbol Operations

    def find_symbol(self, name: str, language: Optional[str] = None) -> List[Symbol]:
        """Find symbols by name across the repository."""
        return self.metadata_store.find_symbols_by_name(name, language)

    def get_symbol_by_id(self, symbol_id: str) -> Optional[Symbol]:
        """Retrieve a specific symbol by unique identifier."""
        return self.metadata_store.get_symbol_by_id(symbol_id)

    def find_symbols_in_file(self, file_path: str) -> List[Symbol]:
        """Get all symbols defined in a specific file."""
        return self.metadata_store.find_symbols_in_file(file_path)

    # Dependency Operations

    def find_callers(self, symbol: Symbol) -> List[Symbol]:
        """Find all symbols that call or reference the given symbol."""
        caller_ids = self.metadata_store.find_callers(symbol.id)
        callers = []

        for caller_id in caller_ids:
            caller = self.metadata_store.get_symbol_by_id(caller_id)
            if caller:
                callers.append(caller)

        return callers

    def find_callees(self, symbol: Symbol) -> List[Symbol]:
        """Find all symbols called or referenced by the given symbol."""
        callee_ids = self.metadata_store.find_callees(symbol.id)
        callees = []

        for callee_id in callee_ids:
            callee = self.metadata_store.get_symbol_by_id(callee_id)
            if callee:
                callees.append(callee)

        return callees

    def get_dependency_chain(self, from_symbol: Symbol, to_symbol: Symbol) -> List[List[Symbol]]:
        """
        Find all paths between two symbols in the dependency graph.

        Uses BFS to find shortest paths.
        """
        paths = []
        queue = deque([(from_symbol, [from_symbol])])
        visited = {from_symbol.id}
        max_depth = 10  # Prevent infinite loops

        while queue:
            current, path = queue.popleft()

            if len(path) > max_depth:
                continue

            if current.id == to_symbol.id:
                paths.append(path)
                continue

            # Get callees of current symbol
            callees = self.find_callees(current)

            for callee in callees:
                if callee.id not in visited:
                    visited.add(callee.id)
                    queue.append((callee, path + [callee]))

        return paths

    # Retrieval Operations

    def retrieve_context(self, question: str, max_symbols: int = 10) -> RetrievalContext:
        """
        Retrieve relevant context for a given question.

        Pipeline:
        1. Generate embedding for question
        2. Perform vector search to find relevant symbols
        3. Expand symbols by including callees and callers
        4. Build structured context
        """
        # Generate embedding for the question
        query_embedding = self.embedding_service.generate_embedding(question)

        # Perform vector search
        search_results = self.vector_store.search(query_vector=query_embedding, limit=max_symbols)

        # Retrieve primary symbols
        primary_symbols = []
        for symbol_id, score in search_results:
            symbol = self.metadata_store.get_symbol_by_id(symbol_id)
            if symbol:
                primary_symbols.append(symbol)

        # Expand symbols by including related symbols
        expanded_symbols = []
        related_files = set()

        for symbol in primary_symbols:
            # Add callees (what this symbol calls)
            callees = self.find_callees(symbol)
            expanded_symbols.extend(callees[:3])  # Limit expansion

            # Add callers (what calls this symbol)
            callers = self.find_callers(symbol)
            expanded_symbols.extend(callers[:3])  # Limit expansion

            # Track related files
            related_files.add(symbol.file_path)
            for callee in callees:
                related_files.add(callee.file_path)
            for caller in callers:
                related_files.add(caller.file_path)

        # Remove duplicates while preserving order
        seen = set()
        unique_expanded = []
        for sym in expanded_symbols:
            if sym.id not in seen and sym.id not in {s.id for s in primary_symbols}:
                seen.add(sym.id)
                unique_expanded.append(sym)

        return RetrievalContext(
            primary_symbols=primary_symbols,
            expanded_symbols=unique_expanded,
            related_files=list(related_files),
            metadata={"question": question, "search_results": len(search_results)},
        )

    def semantic_search(self, query: str, limit: int = 20) -> List[Tuple[Symbol, float]]:
        """Perform pure vector similarity search."""
        # Generate embedding for query
        query_embedding = self.embedding_service.generate_embedding(query)

        # Perform vector search
        search_results = self.vector_store.search(query_vector=query_embedding, limit=limit)

        # Retrieve symbols and return with scores
        results = []
        for symbol_id, score in search_results:
            symbol = self.metadata_store.get_symbol_by_id(symbol_id)
            if symbol:
                results.append((symbol, score))

        return results

    # Impact Analysis Operations

    def impacted_symbols(self, symbol: Symbol, depth: int = 3) -> Set[Symbol]:
        """
        Find all symbols potentially impacted by changes to the given symbol.

        Traverses callers recursively up to the specified depth.
        """
        impacted = set()
        queue = deque([(symbol, 0)])
        visited = {symbol.id}

        while queue:
            current, current_depth = queue.popleft()

            if current_depth >= depth:
                continue

            # Find callers of current symbol
            callers = self.find_callers(current)

            for caller in callers:
                if caller.id not in visited:
                    visited.add(caller.id)
                    impacted.add(caller)
                    queue.append((caller, current_depth + 1))

        return impacted

    def impacted_files(self, symbol: Symbol) -> Set[str]:
        """Find all files potentially impacted by changes to the given symbol."""
        impacted_syms = self.impacted_symbols(symbol)
        files = {symbol.file_path}

        for sym in impacted_syms:
            files.add(sym.file_path)

        return files

    # History Operations

    def get_symbol_history(self, symbol: Symbol, limit: int = 50) -> List[Commit]:
        """Get commit history for a specific symbol."""
        return self.metadata_store.get_commits_for_symbol(symbol.id, limit)

    def find_symbols_changed_in_commit(self, commit_hash: str) -> List[Symbol]:
        """Get all symbols modified in a specific commit."""
        symbol_ids = self.metadata_store.get_symbols_in_commit(commit_hash)
        symbols = []

        for symbol_id in symbol_ids:
            symbol = self.metadata_store.get_symbol_by_id(symbol_id)
            if symbol:
                symbols.append(symbol)

        return symbols

    # Repository Operations

    def get_repository_stats(self) -> dict:
        """Get statistics about the indexed repository."""
        return self.metadata_store.get_repository_stats()

    def is_indexed(self, file_path: str) -> bool:
        """Check if a file has been indexed."""
        return self.metadata_store.is_file_indexed(file_path)


# Made with Bob
