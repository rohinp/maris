"""LanceDB-based vector store for embeddings and semantic search."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import lancedb
import pyarrow as pa

from maris.core.models import Symbol


class VectorStore(ABC):
    """
    Abstract interface for vector storage and semantic search.

    Stores embeddings for symbols and provides efficient similarity search
    capabilities using LanceDB.
    """

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the vector store and create necessary tables."""
        pass

    @abstractmethod
    def insert_embedding(
        self,
        symbol_id: str,
        vector: List[float],
        text: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        Insert a single embedding.

        Args:
            symbol_id: Unique symbol identifier
            vector: Embedding vector
            text: Original text that was embedded
            metadata: Additional metadata (symbol_name, type, file, language)
        """
        pass

    @abstractmethod
    def insert_embeddings(
        self,
        embeddings: List[Dict[str, Any]],
    ) -> None:
        """
        Insert multiple embeddings in a batch operation.

        Args:
            embeddings: List of embedding dictionaries with keys:
                - symbol_id: str
                - vector: List[float]
                - text: str
                - metadata: Dict[str, Any]
        """
        pass

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        limit: int = 20,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float]]:
        """
        Perform similarity search.

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            filter_metadata: Optional metadata filters

        Returns:
            List of (symbol_id, similarity_score) tuples, ordered by relevance
        """
        pass

    @abstractmethod
    def delete_embeddings_for_symbols(self, symbol_ids: List[str]) -> int:
        """
        Delete embeddings for specific symbols.

        Used during incremental re-indexing.

        Args:
            symbol_ids: List of symbol IDs to delete

        Returns:
            Number of embeddings deleted
        """
        pass

    @abstractmethod
    def get_embedding_count(self) -> int:
        """
        Get total number of embeddings in the store.

        Returns:
            Total embedding count
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the vector store connection."""
        pass


class LanceDBVectorStore(VectorStore):
    """LanceDB implementation of the vector store."""

    def __init__(self, db_path: str, table_name: str = "embeddings"):
        """
        Initialize the LanceDB vector store.

        Args:
            db_path: Path to the LanceDB database directory
            table_name: Name of the table to store embeddings
        """
        self.db_path = db_path
        self.table_name = table_name
        self.db: Optional[lancedb.DBConnection] = None
        self.table: Optional[Any] = None

    def initialize(self) -> None:
        """Initialize the vector store and create necessary tables."""
        self.db = lancedb.connect(self.db_path)

        # Define schema for embeddings table
        schema = pa.schema(
            [
                pa.field("symbol_id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 768)),  # 768-dimensional embeddings
                pa.field("text", pa.string()),
                pa.field("symbol_name", pa.string()),
                pa.field("type", pa.string()),
                pa.field("file", pa.string()),
                pa.field("language", pa.string()),
            ]
        )

        # Create table if it doesn't exist
        try:
            self.table = self.db.open_table(self.table_name)
        except Exception:
            # Table doesn't exist, create it with empty data
            empty_data = pa.Table.from_pydict(
                {
                    "symbol_id": [],
                    "vector": [],
                    "text": [],
                    "symbol_name": [],
                    "type": [],
                    "file": [],
                    "language": [],
                },
                schema=schema,
            )
            self.table = self.db.create_table(self.table_name, empty_data)

    def insert_embedding(
        self,
        symbol_id: str,
        vector: List[float],
        text: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Insert a single embedding."""
        if self.table is None:
            raise RuntimeError("Vector store not initialized")

        data = {
            "symbol_id": [symbol_id],
            "vector": [vector],
            "text": [text],
            "symbol_name": [metadata.get("symbol_name", "")],
            "type": [metadata.get("type", "")],
            "file": [metadata.get("file", "")],
            "language": [metadata.get("language", "")],
        }

        self.table.add(data)

    def insert_embeddings(
        self,
        embeddings: List[Dict[str, Any]],
    ) -> None:
        """Insert multiple embeddings in a batch operation."""
        if self.table is None:
            raise RuntimeError("Vector store not initialized")

        if not embeddings:
            return

        data = {
            "symbol_id": [e["symbol_id"] for e in embeddings],
            "vector": [e["vector"] for e in embeddings],
            "text": [e["text"] for e in embeddings],
            "symbol_name": [e["metadata"].get("symbol_name", "") for e in embeddings],
            "type": [e["metadata"].get("type", "") for e in embeddings],
            "file": [e["metadata"].get("file", "") for e in embeddings],
            "language": [e["metadata"].get("language", "") for e in embeddings],
        }

        self.table.add(data)

    def search(
        self,
        query_vector: List[float],
        limit: int = 20,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float]]:
        """Perform similarity search."""
        if self.table is None:
            raise RuntimeError("Vector store not initialized")

        # Build filter string if metadata filters provided
        filter_str = None
        if filter_metadata:
            filters = []
            for key, value in filter_metadata.items():
                filters.append(f"{key} = '{value}'")
            filter_str = " AND ".join(filters)

        # Perform search
        results = self.table.search(query_vector).limit(limit)

        if filter_str:
            results = results.where(filter_str)

        results = results.to_list()

        # Extract symbol_id and distance (convert to similarity score)
        return [(r["symbol_id"], 1.0 - r["_distance"]) for r in results]

    def delete_embeddings_for_symbols(self, symbol_ids: List[str]) -> int:
        """Delete embeddings for specific symbols."""
        if self.table is None:
            raise RuntimeError("Vector store not initialized")

        if not symbol_ids:
            return 0

        # Build delete filter
        filter_str = " OR ".join([f"symbol_id = '{sid}'" for sid in symbol_ids])

        # Count before deletion
        count_before = len(self.table.to_pandas())

        # Delete matching rows
        self.table.delete(filter_str)

        # Count after deletion
        count_after = len(self.table.to_pandas())

        return count_before - count_after

    def get_embedding_count(self) -> int:
        """Get total number of embeddings in the store."""
        if self.table is None:
            raise RuntimeError("Vector store not initialized")

        return len(self.table.to_pandas())

    def close(self) -> None:
        """Close the vector store connection."""
        # LanceDB doesn't require explicit closing
        self.db = None
        self.table = None


# Made with Bob
