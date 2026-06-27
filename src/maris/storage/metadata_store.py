"""DuckDB-based metadata store for symbols, dependencies, and commits."""

import json
from abc import ABC, abstractmethod
from typing import List, Optional

import duckdb

from maris.core.models import Commit, Dependency, Symbol


class MetadataStore(ABC):
    """
    Abstract interface for metadata storage.

    Stores structured data about symbols, dependencies, files, and commits
    using DuckDB for efficient querying and relationship traversal.
    """

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the database schema and tables."""
        pass

    # Symbol Operations

    @abstractmethod
    def insert_symbol(self, symbol: Symbol) -> None:
        """
        Insert a symbol into the store.

        Args:
            symbol: Symbol to insert
        """
        pass

    @abstractmethod
    def insert_symbols(self, symbols: List[Symbol]) -> None:
        """
        Insert multiple symbols in a batch operation.

        Args:
            symbols: List of symbols to insert
        """
        pass

    @abstractmethod
    def get_symbol_by_id(self, symbol_id: str) -> Optional[Symbol]:
        """
        Retrieve a symbol by its unique identifier.

        Args:
            symbol_id: Unique symbol identifier

        Returns:
            Symbol if found, None otherwise
        """
        pass

    @abstractmethod
    def find_symbols_by_name(self, name: str, language: Optional[str] = None) -> List[Symbol]:
        """
        Find symbols by name, optionally filtered by language.

        Args:
            name: Symbol name to search for
            language: Optional language filter

        Returns:
            List of matching symbols
        """
        pass

    @abstractmethod
    def find_symbols_in_file(self, file_path: str) -> List[Symbol]:
        """
        Get all symbols in a specific file.

        Args:
            file_path: Relative path from repository root

        Returns:
            List of symbols ordered by line number
        """
        pass

    @abstractmethod
    def delete_symbols_in_file(self, file_path: str) -> int:
        """
        Delete all symbols in a specific file.

        Used during incremental re-indexing.

        Args:
            file_path: Relative path from repository root

        Returns:
            Number of symbols deleted
        """
        pass

    # Dependency Operations

    @abstractmethod
    def insert_dependency(self, dependency: Dependency) -> None:
        """
        Insert a dependency relationship.

        Args:
            dependency: Dependency to insert
        """
        pass

    @abstractmethod
    def insert_dependencies(self, dependencies: List[Dependency]) -> None:
        """
        Insert multiple dependencies in a batch operation.

        Args:
            dependencies: List of dependencies to insert
        """
        pass

    @abstractmethod
    def find_callers(self, symbol_id: str) -> List[str]:
        """
        Find all symbol IDs that call or reference the given symbol.

        Args:
            symbol_id: Target symbol ID

        Returns:
            List of caller symbol IDs
        """
        pass

    @abstractmethod
    def find_callees(self, symbol_id: str) -> List[str]:
        """
        Find all symbol IDs called or referenced by the given symbol.

        Args:
            symbol_id: Source symbol ID

        Returns:
            List of callee symbol IDs
        """
        pass

    @abstractmethod
    def delete_dependencies_for_file(self, file_path: str) -> int:
        """
        Delete all dependencies involving symbols from a specific file.

        Used during incremental re-indexing.

        Args:
            file_path: Relative path from repository root

        Returns:
            Number of dependencies deleted
        """
        pass

    # File Operations

    @abstractmethod
    def upsert_file_metadata(
        self,
        file_path: str,
        language: str,
        line_count: int,
        symbol_count: int,
    ) -> None:
        """
        Insert or update file metadata.

        Args:
            file_path: Relative path from repository root
            language: Programming language
            line_count: Number of lines in file
            symbol_count: Number of symbols extracted
        """
        pass

    @abstractmethod
    def get_file_metadata(self, file_path: str) -> Optional[dict]:
        """
        Get metadata for a specific file.

        Args:
            file_path: Relative path from repository root

        Returns:
            Dictionary with file metadata, or None if not found
        """
        pass

    @abstractmethod
    def is_file_indexed(self, file_path: str) -> bool:
        """
        Check if a file has been indexed.

        Args:
            file_path: Relative path from repository root

        Returns:
            True if file is indexed, False otherwise
        """
        pass

    # Commit Operations

    @abstractmethod
    def insert_commit(self, commit: Commit) -> None:
        """
        Insert a commit record.

        Args:
            commit: Commit to insert
        """
        pass

    @abstractmethod
    def get_commits_for_symbol(self, symbol_id: str, limit: int = 50) -> List[Commit]:
        """
        Get commit history for a specific symbol.

        Args:
            symbol_id: Symbol identifier
            limit: Maximum number of commits to return

        Returns:
            List of commits, most recent first
        """
        pass

    @abstractmethod
    def get_symbols_in_commit(self, commit_hash: str) -> List[str]:
        """
        Get all symbol IDs modified in a specific commit.

        Args:
            commit_hash: Git commit hash

        Returns:
            List of symbol IDs
        """
        pass

    # Statistics and Metadata

    @abstractmethod
    def get_repository_stats(self) -> dict:
        """
        Get statistics about the indexed repository.

        Returns:
            Dictionary with repository statistics
        """
        pass

    @abstractmethod
    def set_metadata(self, key: str, value: str) -> None:
        """
        Set a metadata key-value pair.

        Args:
            key: Metadata key
            value: Metadata value
        """
        pass

    @abstractmethod
    def get_metadata(self, key: str) -> Optional[str]:
        """
        Get a metadata value by key.

        Args:
            key: Metadata key

        Returns:
            Metadata value if found, None otherwise
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        pass


class DuckDBMetadataStore(MetadataStore):
    """DuckDB implementation of the metadata store."""

    def __init__(self, db_path: str):
        """
        Initialize the DuckDB metadata store.

        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = db_path
        self.conn: Optional[duckdb.DuckDBPyConnection] = None

    def initialize(self) -> None:
        """Initialize the database schema and tables."""
        self.conn = duckdb.connect(self.db_path)

        # Create symbols table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS symbols (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                type VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                language VARCHAR NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                signature TEXT,
                docstring TEXT,
                parent_id VARCHAR,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Add metadata column to existing databases that pre-date this schema
        try:
            self.conn.execute("ALTER TABLE symbols ADD COLUMN IF NOT EXISTS metadata JSON")
        except Exception:
            pass  # DuckDB may not support IF NOT EXISTS for ALTER TABLE in older versions

        # Create indexes for symbols
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(type)")

        # Create dependencies table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dependencies (
                id VARCHAR PRIMARY KEY,
                from_symbol_id VARCHAR NOT NULL,
                to_symbol_id VARCHAR NOT NULL,
                relationship_type VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create indexes for dependencies
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dependencies_from ON dependencies(from_symbol_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dependencies_to ON dependencies(to_symbol_id)"
        )

        # Create files table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                path VARCHAR PRIMARY KEY,
                language VARCHAR NOT NULL,
                last_indexed_at TIMESTAMP NOT NULL,
                last_modified_at TIMESTAMP NOT NULL,
                line_count INTEGER,
                symbol_count INTEGER
            )
        """
        )

        # Create indexing_metadata table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS indexing_metadata (
                key VARCHAR PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create commits table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS commits (
                hash VARCHAR PRIMARY KEY,
                author VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                message TEXT NOT NULL
            )
        """
        )

        # Create commit_symbols junction table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS commit_symbols (
                commit_hash VARCHAR NOT NULL,
                symbol_id VARCHAR NOT NULL,
                PRIMARY KEY (commit_hash, symbol_id)
            )
        """
        )

        self.conn.commit()

    def insert_symbol(self, symbol: Symbol) -> None:
        """Insert a symbol into the store."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        self.conn.execute(
            """
            INSERT OR REPLACE INTO symbols
            (id, name, type, file_path, language, start_line, end_line,
             signature, docstring, parent_id, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                symbol.id,
                symbol.name,
                symbol.type.value,
                symbol.file_path,
                symbol.language,
                symbol.start_line,
                symbol.end_line,
                symbol.signature,
                symbol.docstring,
                symbol.parent_id,
                json.dumps(symbol.metadata) if symbol.metadata else None,
            ],
        )
        self.conn.commit()

    def insert_symbols(self, symbols: List[Symbol]) -> None:
        """Insert multiple symbols in a batch operation."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        data = [
            [
                s.id,
                s.name,
                s.type.value,
                s.file_path,
                s.language,
                s.start_line,
                s.end_line,
                s.signature,
                s.docstring,
                s.parent_id,
                json.dumps(s.metadata) if s.metadata else None,
            ]
            for s in symbols
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO symbols
            (id, name, type, file_path, language, start_line, end_line,
             signature, docstring, parent_id, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            data,
        )
        self.conn.commit()

    # Explicit column list used by all symbol SELECT queries.
    # This order must match _row_to_symbol's positional reads.
    # Using named columns instead of SELECT * means column order in the
    # on-disk table (which varies between new and migrated databases)
    # never affects deserialization.
    _SYMBOL_COLUMNS = (
        "id, name, type, file_path, language, start_line, end_line, "
        "signature, docstring, parent_id, metadata"
    )

    def get_symbol_by_id(self, symbol_id: str) -> Optional[Symbol]:
        """Retrieve a symbol by its unique identifier."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        result = self.conn.execute(
            f"SELECT {self._SYMBOL_COLUMNS} FROM symbols WHERE id = ?", [symbol_id]
        ).fetchone()

        if result is None:
            return None

        return self._row_to_symbol(result)

    def find_symbols_by_name(self, name: str, language: Optional[str] = None) -> List[Symbol]:
        """Find symbols by name, optionally filtered by language."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        if language:
            results = self.conn.execute(
                f"SELECT {self._SYMBOL_COLUMNS} FROM symbols WHERE name = ? AND language = ?",
                [name, language],
            ).fetchall()
        else:
            results = self.conn.execute(
                f"SELECT {self._SYMBOL_COLUMNS} FROM symbols WHERE name = ?", [name]
            ).fetchall()

        return [self._row_to_symbol(row) for row in results]

    def find_symbols_in_file(self, file_path: str) -> List[Symbol]:
        """Get all symbols in a specific file."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        results = self.conn.execute(
            f"SELECT {self._SYMBOL_COLUMNS} FROM symbols WHERE file_path = ? ORDER BY start_line",
            [file_path],
        ).fetchall()

        return [self._row_to_symbol(row) for row in results]

    def delete_symbols_in_file(self, file_path: str) -> int:
        """Delete all symbols in a specific file."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        result = self.conn.execute("DELETE FROM symbols WHERE file_path = ?", [file_path])
        self.conn.commit()
        return result.fetchone()[0] if result else 0

    def insert_dependency(self, dependency: Dependency) -> None:
        """Insert a dependency relationship."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        self.conn.execute(
            """
            INSERT OR REPLACE INTO dependencies
            (id, from_symbol_id, to_symbol_id, relationship_type)
            VALUES (?, ?, ?, ?)
            """,
            [
                dependency.id,
                dependency.from_symbol_id,
                dependency.to_symbol_id,
                dependency.relationship_type,
            ],
        )
        self.conn.commit()

    def insert_dependencies(self, dependencies: List[Dependency]) -> None:
        """Insert multiple dependencies in a batch operation."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        data = [[d.id, d.from_symbol_id, d.to_symbol_id, d.relationship_type] for d in dependencies]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO dependencies
            (id, from_symbol_id, to_symbol_id, relationship_type)
            VALUES (?, ?, ?, ?)
            """,
            data,
        )
        self.conn.commit()

    def find_callers(self, symbol_id: str) -> List[str]:
        """Find all symbol IDs that call or reference the given symbol."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        results = self.conn.execute(
            "SELECT from_symbol_id FROM dependencies WHERE to_symbol_id = ?", [symbol_id]
        ).fetchall()

        return [row[0] for row in results]

    def find_callees(self, symbol_id: str) -> List[str]:
        """Find all symbol IDs called or referenced by the given symbol."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        results = self.conn.execute(
            "SELECT to_symbol_id FROM dependencies WHERE from_symbol_id = ?", [symbol_id]
        ).fetchall()

        return [row[0] for row in results]

    def delete_dependencies_for_file(self, file_path: str) -> int:
        """Delete all dependencies involving symbols from a specific file."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        result = self.conn.execute(
            """
            DELETE FROM dependencies
            WHERE from_symbol_id IN (SELECT id FROM symbols WHERE file_path = ?)
               OR to_symbol_id IN (SELECT id FROM symbols WHERE file_path = ?)
            """,
            [file_path, file_path],
        )
        self.conn.commit()
        return result.fetchone()[0] if result else 0

    def upsert_file_metadata(
        self,
        file_path: str,
        language: str,
        line_count: int,
        symbol_count: int,
    ) -> None:
        """Insert or update file metadata."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        self.conn.execute(
            """
            INSERT OR REPLACE INTO files
            (path, language, last_indexed_at, last_modified_at, line_count, symbol_count)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?)
            """,
            [file_path, language, line_count, symbol_count],
        )
        self.conn.commit()

    def get_file_metadata(self, file_path: str) -> Optional[dict]:
        """Get metadata for a specific file."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        result = self.conn.execute("SELECT * FROM files WHERE path = ?", [file_path]).fetchone()

        if result is None:
            return None

        return {
            "path": result[0],
            "language": result[1],
            "last_indexed_at": result[2],
            "last_modified_at": result[3],
            "line_count": result[4],
            "symbol_count": result[5],
        }

    def is_file_indexed(self, file_path: str) -> bool:
        """Check if a file has been indexed."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        result = self.conn.execute(
            "SELECT COUNT(*) FROM files WHERE path = ?", [file_path]
        ).fetchone()

        return result[0] > 0 if result else False

    def insert_commit(self, commit: Commit) -> None:
        """Insert a commit record."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        # Insert commit
        self.conn.execute(
            """
            INSERT OR REPLACE INTO commits (hash, author, timestamp, message)
            VALUES (?, ?, ?, ?)
            """,
            [commit.hash, commit.author, commit.timestamp, commit.message],
        )

        # Insert commit-symbol relationships
        if commit.symbols_changed:
            data = [[commit.hash, symbol_id] for symbol_id in commit.symbols_changed]
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO commit_symbols (commit_hash, symbol_id)
                VALUES (?, ?)
                """,
                data,
            )

        self.conn.commit()

    def get_commits_for_symbol(self, symbol_id: str, limit: int = 50) -> List[Commit]:
        """Get commit history for a specific symbol."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        results = self.conn.execute(
            """
            SELECT c.* FROM commits c
            JOIN commit_symbols cs ON c.hash = cs.commit_hash
            WHERE cs.symbol_id = ?
            ORDER BY c.timestamp DESC
            LIMIT ?
            """,
            [symbol_id, limit],
        ).fetchall()

        commits = []
        for row in results:
            commit = Commit(
                hash=row[0],
                author=row[1],
                timestamp=row[2],
                message=row[3],
            )
            commits.append(commit)

        return commits

    def get_symbols_in_commit(self, commit_hash: str) -> List[str]:
        """Get all symbol IDs modified in a specific commit."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        results = self.conn.execute(
            "SELECT symbol_id FROM commit_symbols WHERE commit_hash = ?", [commit_hash]
        ).fetchall()

        return [row[0] for row in results]

    def get_repository_stats(self) -> dict:
        """Get statistics about the indexed repository."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        total_files = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        total_symbols = self.conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        total_dependencies = self.conn.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0]

        languages = self.conn.execute(
            "SELECT DISTINCT language FROM files ORDER BY language"
        ).fetchall()

        last_indexed = self.conn.execute("SELECT MAX(last_indexed_at) FROM files").fetchone()[0]

        return {
            "total_files": total_files,
            "total_symbols": total_symbols,
            "total_dependencies": total_dependencies,
            "languages": [lang[0] for lang in languages],
            "last_indexed": last_indexed,
        }

    def set_metadata(self, key: str, value: str) -> None:
        """Set a metadata key-value pair."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        self.conn.execute(
            """
            INSERT OR REPLACE INTO indexing_metadata (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            [key, value],
        )
        self.conn.commit()

    def get_metadata(self, key: str) -> Optional[str]:
        """Get a metadata value by key."""
        if self.conn is None:
            raise RuntimeError("Database not initialized")

        result = self.conn.execute(
            "SELECT value FROM indexing_metadata WHERE key = ?", [key]
        ).fetchone()

        return result[0] if result else None

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _row_to_symbol(self, row: tuple) -> Symbol:
        """Convert a database row to a Symbol object.

        Expects exactly the columns listed in ``_SYMBOL_COLUMNS``:
        id[0], name[1], type[2], file_path[3], language[4],
        start_line[5], end_line[6], signature[7], docstring[8],
        parent_id[9], metadata[10].
        """
        from maris.core.models import SymbolType

        # row[10] is always metadata because all callers use _SYMBOL_COLUMNS,
        # not SELECT *.  It is NULL for rows that pre-date the metadata column.
        raw_metadata = row[10]
        metadata: dict = {}
        if raw_metadata is not None:
            try:
                metadata = (
                    json.loads(raw_metadata)
                    if isinstance(raw_metadata, str)
                    else dict(raw_metadata)
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                metadata = {}

        return Symbol(
            id=row[0],
            name=row[1],
            type=SymbolType(row[2]),
            file_path=row[3],
            language=row[4],
            start_line=row[5],
            end_line=row[6],
            signature=row[7],
            docstring=row[8],
            parent_id=row[9],
            metadata=metadata,
        )


# Made with Bob
