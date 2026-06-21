"""Indexing Agent - converts source code into structured knowledge."""

import hashlib
import time
from pathlib import Path
from typing import List, Optional

from maris.core.models import IndexingResult, Symbol, SymbolType
from maris.storage.metadata_store import MetadataStore
from maris.storage.vector_store import VectorStore


class IndexingAgent:
    """
    Repository Indexing Agent.

    Responsible for:
    - Parsing source files using Tree-sitter
    - Extracting symbols (classes, functions, methods, etc.)
    - Building dependency relationships
    - Generating embeddings for semantic search
    - Storing structured data in the knowledge layer
    """

    def __init__(
        self,
        metadata_store: MetadataStore,
        vector_store: VectorStore,
        repo_path: str,
    ):
        """
        Initialize the indexing agent.

        Args:
            metadata_store: Store for symbols, dependencies, and metadata
            vector_store: Store for embeddings and semantic search
            repo_path: Path to the repository root
        """
        self.metadata_store = metadata_store
        self.vector_store = vector_store
        self.repo_path = Path(repo_path)

        # Language configuration
        self.supported_languages = {
            "scala": {
                "extensions": [".scala"],
                "tree_sitter_grammar": "tree-sitter-scala",
            },
            "java": {
                "extensions": [".java"],
                "tree_sitter_grammar": "tree-sitter-java",
            },
            "python": {
                "extensions": [".py"],
                "tree_sitter_grammar": "tree-sitter-python",
            },
            "typescript": {
                "extensions": [".ts", ".tsx"],
                "tree_sitter_grammar": "tree-sitter-typescript",
            },
        }

        # Exclusion patterns
        self.excluded_patterns = [
            "*/node_modules/*",
            "*/target/*",
            "*/build/*",
            "*/.git/*",
            "*/dist/*",
            "*/__pycache__/*",
            "*.min.js",
            "*.bundle.js",
        ]

    def index_repository(self) -> IndexingResult:
        """
        Perform full repository indexing.

        Returns:
            IndexingResult with statistics and any errors
        """
        start_time = time.time()
        result = IndexingResult()

        # Find all source files
        files_to_index = self._find_source_files()

        # Index each file
        for file_path in files_to_index:
            try:
                self._index_file(file_path, result)
            except Exception as e:
                result.errors.append(f"{file_path}: {str(e)}")

        result.duration_seconds = time.time() - start_time
        return result

    def index_files(self, file_paths: List[str]) -> IndexingResult:
        """
        Index specific files (for incremental updates).

        Args:
            file_paths: List of file paths relative to repository root

        Returns:
            IndexingResult with statistics and any errors
        """
        start_time = time.time()
        result = IndexingResult()

        for file_path in file_paths:
            try:
                # Delete existing symbols and dependencies for this file
                self.metadata_store.delete_dependencies_for_file(file_path)
                symbol_ids = [s.id for s in self.metadata_store.find_symbols_in_file(file_path)]
                if symbol_ids:
                    self.vector_store.delete_embeddings_for_symbols(symbol_ids)
                self.metadata_store.delete_symbols_in_file(file_path)

                # Re-index the file
                self._index_file(file_path, result)
            except Exception as e:
                result.errors.append(f"{file_path}: {str(e)}")

        result.duration_seconds = time.time() - start_time
        return result

    def get_indexing_status(self) -> dict:
        """
        Get current indexing progress and statistics.

        Returns:
            Dictionary with indexing status information
        """
        stats = self.metadata_store.get_repository_stats()
        embedding_count = self.vector_store.get_embedding_count()

        return {
            "repository_path": str(self.repo_path),
            "total_files": stats["total_files"],
            "total_symbols": stats["total_symbols"],
            "total_dependencies": stats["total_dependencies"],
            "total_embeddings": embedding_count,
            "languages": stats["languages"],
            "last_indexed": stats["last_indexed"],
        }

    def _find_source_files(self) -> List[str]:
        """
        Find all source files in the repository.

        Returns:
            List of file paths relative to repository root
        """
        source_files = []

        for lang_config in self.supported_languages.values():
            for ext in lang_config["extensions"]:
                for file_path in self.repo_path.rglob(f"*{ext}"):
                    rel_path = str(file_path.relative_to(self.repo_path))

                    # Check exclusion patterns
                    if not self._is_excluded(rel_path):
                        source_files.append(rel_path)

        return source_files

    def _is_excluded(self, file_path: str) -> bool:
        """
        Check if a file should be excluded from indexing.

        Args:
            file_path: Relative file path

        Returns:
            True if file should be excluded
        """
        from fnmatch import fnmatch

        for pattern in self.excluded_patterns:
            if fnmatch(file_path, pattern):
                return True
        return False

    def _index_file(self, file_path: str, result: IndexingResult) -> None:
        """
        Index a single file.

        Args:
            file_path: Relative path from repository root
            result: IndexingResult to update with statistics
        """
        # Detect language
        language = self._detect_language(file_path)
        if not language:
            result.errors.append(f"{file_path}: Unknown language")
            return

        # Read file content
        full_path = self.repo_path / file_path
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            result.errors.append(f"{file_path}: Failed to read file - {str(e)}")
            return

        # For MVP, create a simple symbol extraction
        # In production, this would use Tree-sitter parsing
        symbols = self._extract_symbols_simple(file_path, content, language)

        if symbols:
            # Store symbols
            self.metadata_store.insert_symbols(symbols)
            result.symbols_extracted += len(symbols)

            # Update file metadata
            line_count = len(content.splitlines())
            self.metadata_store.upsert_file_metadata(file_path, language, line_count, len(symbols))

        result.files_processed += 1

    def _detect_language(self, file_path: str) -> Optional[str]:
        """
        Detect programming language from file extension.

        Args:
            file_path: File path

        Returns:
            Language name or None if not supported
        """
        ext = Path(file_path).suffix

        for lang, config in self.supported_languages.items():
            if ext in config["extensions"]:
                return lang

        return None

    def _extract_symbols_simple(self, file_path: str, content: str, language: str) -> List[Symbol]:
        """
        Simple symbol extraction (placeholder for Tree-sitter implementation).

        This is a simplified version for MVP. In production, this would use
        Tree-sitter to parse the AST and extract symbols accurately.

        Args:
            file_path: Relative file path
            content: File content
            language: Programming language

        Returns:
            List of extracted symbols
        """
        symbols = []
        lines = content.splitlines()

        # Simple pattern matching for demonstration
        # In production, use Tree-sitter AST parsing
        for i, line in enumerate(lines, start=1):
            line_stripped = line.strip()

            # Python class detection
            if language == "python" and line_stripped.startswith("class "):
                class_name = line_stripped.split("class ")[1].split("(")[0].split(":")[0].strip()
                symbol_id = self._generate_symbol_id(file_path, class_name, i)
                symbols.append(
                    Symbol(
                        id=symbol_id,
                        name=class_name,
                        type=SymbolType.CLASS,
                        file_path=file_path,
                        language=language,
                        start_line=i,
                        end_line=i,  # Simplified - would need AST for accurate end line
                    )
                )

            # Python function detection
            elif language == "python" and line_stripped.startswith("def "):
                func_name = line_stripped.split("def ")[1].split("(")[0].strip()
                symbol_id = self._generate_symbol_id(file_path, func_name, i)
                symbols.append(
                    Symbol(
                        id=symbol_id,
                        name=func_name,
                        type=SymbolType.FUNCTION,
                        file_path=file_path,
                        language=language,
                        start_line=i,
                        end_line=i,
                        signature=line_stripped,
                    )
                )

            # Java/Scala class detection
            elif language in ["java", "scala"] and " class " in line_stripped:
                parts = line_stripped.split(" class ")
                if len(parts) > 1:
                    class_name = parts[1].split()[0].split("{")[0].strip()
                    symbol_id = self._generate_symbol_id(file_path, class_name, i)
                    symbols.append(
                        Symbol(
                            id=symbol_id,
                            name=class_name,
                            type=SymbolType.CLASS,
                            file_path=file_path,
                            language=language,
                            start_line=i,
                            end_line=i,
                        )
                    )

            # TypeScript class detection
            elif language == "typescript" and line_stripped.startswith("class "):
                class_name = line_stripped.split("class ")[1].split()[0].split("{")[0].strip()
                symbol_id = self._generate_symbol_id(file_path, class_name, i)
                symbols.append(
                    Symbol(
                        id=symbol_id,
                        name=class_name,
                        type=SymbolType.CLASS,
                        file_path=file_path,
                        language=language,
                        start_line=i,
                        end_line=i,
                    )
                )

        return symbols

    def _generate_symbol_id(self, file_path: str, symbol_name: str, line: int) -> str:
        """
        Generate a unique symbol identifier.

        Args:
            file_path: File path
            symbol_name: Symbol name
            line: Line number

        Returns:
            Unique symbol ID
        """
        content = f"{file_path}:{symbol_name}:{line}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# Made with Bob
