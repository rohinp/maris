"""Indexing Agent - LangGraph-based implementation for converting source code into structured knowledge."""

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph

from maris.core.models import IndexingResult, Symbol, SymbolType
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService
from maris.indexing.parser_factory import ParserFactory
from maris.storage.metadata_store import MetadataStore
from maris.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class IndexingAgent:
    """
    LangGraph-based Repository Indexing Agent.

    Uses a workflow with explicit state management:
    1. scan_files: Find source files to index
    2. parse_files: Parse files and extract symbols
    3. store_symbols: Store symbols in metadata store
    4. generate_embeddings: Create embeddings for symbols
    5. store_embeddings: Store embeddings in vector store
    6. assess_result: Calculate statistics and success rate

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
        embedding_service: Optional[OllamaEmbeddingService] = None,
    ):
        """
        Initialize the indexing agent.

        Args:
            metadata_store: Store for symbols, dependencies, and metadata
            vector_store: Store for embeddings and semantic search
            repo_path: Path to the repository root
            embedding_service: Optional embedding service (creates default if not provided)
        """
        self.metadata_store = metadata_store
        self.vector_store = vector_store
        self.repo_path = Path(repo_path)
        self.embedding_service = embedding_service or OllamaEmbeddingService()

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

        # Exclusion patterns - common directories and files to skip
        self.excluded_patterns = [
            # Version control
            "*/.git/*",
            "*/.svn/*",
            "*/.hg/*",
            # Python
            "*/__pycache__/*",
            "*/.venv/*",
            "*/venv/*",
            "*/env/*",
            "*/.env",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            "*/.pytest_cache/*",
            "*/.mypy_cache/*",
            "*/.tox/*",
            "*/.nox/*",
            "*/.ruff_cache/*",
            "*/.eggs/*",
            "*/site-packages/*",
            "*/dist-packages/*",
            # Node.js / JavaScript
            "*/node_modules/*",
            "*/bower_components/*",
            "*.min.js",
            "*.bundle.js",
            "*/.npm/*",
            "*/.yarn/*",
            # Java / JVM
            "*/target/*",
            "*/build/*",
            "*/.gradle/*",
            "*/.m2/*",
            "*.class",
            # Build outputs
            "*/dist/*",
            "*/out/*",
            "*/bin/*",
            "*/.next/*",
            "*/.nuxt/*",
            "*/htmlcov/*",
            "*/coverage/*",
            # IDE / Editor
            "*/.idea/*",
            "*/.vscode/*",
            "*/.vs/*",
            "*.swp",
            "*.swo",
            "*~",
            # OS
            "*/.DS_Store",
            "*/Thumbs.db",
            # Logs and temp files
            "*.log",
            "*/logs/*",
            "*/tmp/*",
            "*/temp/*",
            # Dependencies and vendor
            "*/vendor/*",
            "*/vendors/*",
            # Documentation builds
            "*/_build/*",
            "*/docs/_build/*",
            # MARIS local storage
            "*/.maris/*",
        ]

        # Build the LangGraph workflow
        self.graph = self._build_graph()

        logger.info(f"Initialized IndexingAgent with LangGraph for repo: {repo_path}")

    def _build_graph(self) -> Any:
        """Build the LangGraph workflow for indexing."""

        # Use dict directly as state schema (LangGraph supports this)
        workflow = StateGraph(dict)

        # Add nodes
        workflow.add_node("scan_files", self._scan_files)
        workflow.add_node("parse_files", self._parse_files)
        workflow.add_node("store_symbols", self._store_symbols)
        workflow.add_node("generate_embeddings", self._generate_embeddings)
        workflow.add_node("store_embeddings", self._store_embeddings)
        workflow.add_node("assess_result", self._assess_result)

        # Define edges
        workflow.set_entry_point("scan_files")
        workflow.add_edge("scan_files", "parse_files")
        workflow.add_edge("parse_files", "store_symbols")
        workflow.add_edge("store_symbols", "generate_embeddings")
        workflow.add_edge("generate_embeddings", "store_embeddings")
        workflow.add_edge("store_embeddings", "assess_result")
        workflow.add_edge("assess_result", END)

        return workflow.compile()

    def _scan_files(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Scan repository for source files to index.

        Args:
            state: Current workflow state

        Returns:
            Updated state with file paths to index
        """
        try:
            logger.info("Scanning repository for source files")

            # Check if specific files were provided
            if state.get("file_paths"):
                # Incremental indexing mode
                files_to_index = state["file_paths"]
                logger.info(f"Incremental mode: indexing {len(files_to_index)} specific files")
            else:
                # Full repository scan
                files_to_index = self._find_source_files()
                logger.info(f"Full scan: found {len(files_to_index)} source files")

            state["files_to_index"] = files_to_index
            state["total_files"] = len(files_to_index)

        except Exception as e:
            logger.error(f"Error scanning files: {e}")
            state["error"] = f"Failed to scan files: {str(e)}"
            state["files_to_index"] = []
            state["total_files"] = 0

        return state

    def _parse_files(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Parse files and extract symbols.

        Args:
            state: Current workflow state

        Returns:
            Updated state with extracted symbols
        """
        if state.get("error"):
            return state

        try:
            logger.info("Parsing files and extracting symbols")

            files_to_index = state.get("files_to_index", [])
            all_symbols = []
            parse_errors = []

            for file_path in files_to_index:
                try:
                    # Detect language
                    language = self._detect_language(file_path)
                    if not language:
                        parse_errors.append(f"{file_path}: Unknown language")
                        logger.warning(f"Unknown language for {file_path}")
                        logger.debug(f"File extension: {Path(file_path).suffix}")
                        continue

                    logger.debug(f"Detected language '{language}' for {file_path}")

                    # Read file content - handle both absolute and relative paths
                    path_obj = Path(file_path)
                    if path_obj.is_absolute():
                        full_path = path_obj
                    else:
                        full_path = self.repo_path / file_path

                    logger.debug(f"Reading file: {full_path}")

                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract symbols
                    symbols = self._extract_symbols_simple(str(file_path), content, language)
                    all_symbols.extend(symbols)

                    logger.debug(f"Extracted {len(symbols)} symbols from {file_path}")

                    # Store file metadata for later
                    line_count = len(content.splitlines())
                    if "file_metadata" not in state:
                        state["file_metadata"] = {}
                    state["file_metadata"][str(file_path)] = {
                        "language": language,
                        "line_count": line_count,
                        "symbol_count": len(symbols),
                    }

                except Exception as e:
                    parse_errors.append(f"{file_path}: {str(e)}")
                    logger.error(f"Error parsing {file_path}: {e}", exc_info=True)

            state["extracted_symbols"] = all_symbols
            state["parse_errors"] = parse_errors

            logger.info(f"Extracted {len(all_symbols)} symbols from {len(files_to_index)} files")

        except Exception as e:
            logger.error(f"Error in parse_files node: {e}")
            state["error"] = f"Failed to parse files: {str(e)}"
            state["extracted_symbols"] = []
            state["parse_errors"] = []

        return state

    def _store_symbols(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Store extracted symbols in metadata store.

        Args:
            state: Current workflow state

        Returns:
            Updated state with storage confirmation
        """
        if state.get("error"):
            return state

        try:
            logger.info("Storing symbols in metadata store")

            symbols = state.get("extracted_symbols", [])

            if symbols:
                # Store symbols
                self.metadata_store.insert_symbols(symbols)

                # Update file metadata
                file_metadata = state.get("file_metadata", {})
                for file_path, metadata in file_metadata.items():
                    self.metadata_store.upsert_file_metadata(
                        file_path,
                        metadata["language"],
                        metadata["line_count"],
                        metadata["symbol_count"],
                    )

                state["symbols_stored"] = len(symbols)
                logger.info(f"Stored {len(symbols)} symbols")
            else:
                state["symbols_stored"] = 0
                logger.warning("No symbols to store")

        except Exception as e:
            logger.error(f"Error storing symbols: {e}")
            state["error"] = f"Failed to store symbols: {str(e)}"
            state["symbols_stored"] = 0

        return state

    def _generate_embeddings(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Generate embeddings for extracted symbols.

        Args:
            state: Current workflow state

        Returns:
            Updated state with generated embeddings
        """
        if state.get("error"):
            return state

        try:
            symbols = state.get("extracted_symbols", [])

            if symbols:
                logger.info(f"Generating embeddings for {len(symbols)} symbols")

                # Track progress
                state["embedding_progress"] = {"current": 0, "total": len(symbols)}

                def progress_callback(current: int, total: int) -> None:
                    """Update progress in state."""
                    state["embedding_progress"] = {"current": current, "total": total}
                    if current % 100 == 0 or current == total:
                        logger.info(
                            f"Embedding progress: {current}/{total} ({current*100//total}%)"
                        )

                # Generate embeddings with progress tracking
                embeddings = self.embedding_service.embed_symbols(
                    symbols, progress_callback=progress_callback
                )

                state["embeddings"] = embeddings
                state["embeddings_generated"] = len(embeddings)

                logger.info(f"Generated {len(embeddings)} embeddings")
            else:
                state["embeddings"] = []
                state["embeddings_generated"] = 0
                logger.warning("No symbols to embed")

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Don't fail the entire workflow for embedding errors
            state["embeddings"] = []
            state["embeddings_generated"] = 0
            state["embedding_error"] = str(e)

        return state

    def _store_embeddings(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Store embeddings in vector store.

        Args:
            state: Current workflow state

        Returns:
            Updated state with storage confirmation
        """
        if state.get("error"):
            return state

        try:
            logger.info("Storing embeddings in vector store")

            symbols = state.get("extracted_symbols", [])
            embeddings = state.get("embeddings", [])

            if symbols and embeddings and len(symbols) == len(embeddings):
                # Store embeddings — text must match what was passed to the
                # embedding model so that LanceDB's text column stays in sync.
                for symbol, embedding in zip(symbols, embeddings):
                    self.vector_store.insert_embedding(
                        symbol_id=symbol.id,
                        vector=embedding,
                        text=symbol.to_rich_text(),
                        metadata={
                            "symbol_name": symbol.name,
                            "type": symbol.type.value,
                            "file": symbol.file_path,
                            "language": symbol.language,
                        },
                    )

                state["embeddings_stored"] = len(embeddings)
                logger.info(f"Stored {len(embeddings)} embeddings")
            else:
                state["embeddings_stored"] = 0
                if symbols and not embeddings:
                    logger.warning("No embeddings to store")

        except Exception as e:
            logger.error(f"Error storing embeddings: {e}")
            # Don't fail the entire workflow for embedding storage errors
            state["embeddings_stored"] = 0
            state["embedding_storage_error"] = str(e)

        return state

    def _assess_result(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Assess indexing results and calculate statistics.

        Args:
            state: Current workflow state

        Returns:
            Updated state with final statistics
        """
        try:
            logger.info("Assessing indexing results")

            # Calculate statistics
            files_processed = len(state.get("file_metadata", {}))
            symbols_extracted = len(state.get("extracted_symbols", []))
            embeddings_generated = state.get("embeddings_generated", 0)

            # Collect all errors
            errors = []
            if state.get("error"):
                errors.append(state["error"])
            errors.extend(state.get("parse_errors", []))
            if state.get("embedding_error"):
                errors.append(f"Embedding generation: {state['embedding_error']}")
            if state.get("embedding_storage_error"):
                errors.append(f"Embedding storage: {state['embedding_storage_error']}")

            # Calculate success rate
            total_files = state.get("total_files", 0)
            if total_files > 0:
                success_rate = files_processed / total_files
            else:
                success_rate = 0.0

            state["final_stats"] = {
                "files_processed": files_processed,
                "symbols_extracted": symbols_extracted,
                "embeddings_generated": embeddings_generated,
                "errors": errors,
                "success_rate": success_rate,
            }

            logger.info(
                f"Indexing complete: {files_processed} files, "
                f"{symbols_extracted} symbols, {embeddings_generated} embeddings, "
                f"{len(errors)} errors"
            )

        except Exception as e:
            logger.error(f"Error assessing results: {e}")
            state["final_stats"] = {
                "files_processed": 0,
                "symbols_extracted": 0,
                "embeddings_generated": 0,
                "errors": [f"Assessment error: {str(e)}"],
                "success_rate": 0.0,
            }

        return state

    def index_repository(self) -> IndexingResult:
        """
        Perform full repository indexing.

        Returns:
            IndexingResult with statistics and any errors
        """
        start_time = time.time()

        logger.info("Starting full repository indexing")

        # Initialize state
        initial_state: Dict[str, Any] = {
            "file_paths": None,  # None means full scan
            "files_to_index": [],
            "total_files": 0,
            "extracted_symbols": [],
            "file_metadata": {},
            "parse_errors": [],
            "embeddings": [],
            "embeddings_generated": 0,
            "symbols_stored": 0,
            "embeddings_stored": 0,
            "error": None,
        }

        # Run the workflow
        final_state = self.graph.invoke(initial_state)

        # Build result
        if final_state is None:
            final_state = initial_state
        stats = final_state.get("final_stats", {})
        duration = time.time() - start_time

        result = IndexingResult(
            files_processed=stats.get("files_processed", 0),
            symbols_extracted=stats.get("symbols_extracted", 0),
            dependencies_found=0,  # TODO: Add dependency extraction in future
            embeddings_generated=stats.get("embeddings_generated", 0),
            errors=stats.get("errors", []),
            duration_seconds=duration,
        )

        logger.info(f"Repository indexing completed in {duration:.2f}s")
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

        logger.info(f"Starting incremental indexing for {len(file_paths)} files")

        # Clean up existing data for these files
        for file_path in file_paths:
            try:
                # Delete existing symbols and dependencies for this file
                self.metadata_store.delete_dependencies_for_file(file_path)
                symbol_ids = [s.id for s in self.metadata_store.find_symbols_in_file(file_path)]
                if symbol_ids:
                    self.vector_store.delete_embeddings_for_symbols(symbol_ids)
                self.metadata_store.delete_symbols_in_file(file_path)
            except Exception as e:
                logger.error(f"Error cleaning up {file_path}: {e}")

        # Initialize state
        initial_state: Dict[str, Any] = {
            "file_paths": file_paths,  # Specific files for incremental indexing
            "files_to_index": [],
            "total_files": len(file_paths),
            "extracted_symbols": [],
            "file_metadata": {},
            "parse_errors": [],
            "embeddings": [],
            "embeddings_generated": 0,
            "symbols_stored": 0,
            "embeddings_stored": 0,
            "error": None,
        }

        # Run the workflow
        final_state = self.graph.invoke(initial_state)

        # Build result
        if final_state is None:
            final_state = initial_state
        stats = final_state.get("final_stats", {})
        duration = time.time() - start_time

        result = IndexingResult(
            files_processed=stats.get("files_processed", 0),
            symbols_extracted=stats.get("symbols_extracted", 0),
            dependencies_found=0,  # TODO: Add dependency extraction in future
            embeddings_generated=stats.get("embeddings_generated", 0),
            errors=stats.get("errors", []),
            duration_seconds=duration,
        )

        logger.info(f"Incremental indexing completed in {duration:.2f}s")
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

    def collect_source_files(
        self, root_path: Optional[str | Path] = None, recursive: bool = True
    ) -> List[str]:
        """
        Collect indexable files below a file or directory.

        Applies the same implemented-extension and exclusion rules used by indexing,
        and prunes excluded directories before descending into them.

        Args:
            root_path: File or directory to scan. Defaults to repository root.
            recursive: Whether to recurse into subdirectories.

        Returns:
            List of paths relative to the repository root when possible.
        """
        root = Path(root_path) if root_path is not None else self.repo_path
        if not root.is_absolute():
            root = self.repo_path / root

        if root.is_file():
            rel_path = self._relative_to_repo(root)
            if ParserFactory.is_implemented(rel_path) and not self._is_excluded(rel_path):
                return [rel_path]
            return []

        if not root.is_dir():
            return []

        source_files = []

        if recursive:
            for current_root, dirnames, filenames in os.walk(root):
                current_path = Path(current_root)

                dirnames[:] = [
                    dirname
                    for dirname in dirnames
                    if not self._is_excluded(self._relative_to_repo(current_path / dirname))
                ]

                for filename in filenames:
                    file_path = current_path / filename
                    rel_path = self._relative_to_repo(file_path)
                    if ParserFactory.is_implemented(rel_path) and not self._is_excluded(rel_path):
                        source_files.append(rel_path)
        else:
            for file_path in root.iterdir():
                if not file_path.is_file():
                    continue
                rel_path = self._relative_to_repo(file_path)
                if ParserFactory.is_implemented(rel_path) and not self._is_excluded(rel_path):
                    source_files.append(rel_path)

        return sorted(source_files)

    def _find_source_files(self) -> List[str]:
        """
        Find all source files in the repository using ParserFactory.

        Returns:
            List of file paths relative to repository root
        """
        return self.collect_source_files(self.repo_path, recursive=True)

    def _relative_to_repo(self, path: Path) -> str:
        """Return a normalized path relative to the repository root when possible."""
        try:
            return str(path.resolve().relative_to(self.repo_path.resolve())).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def _is_excluded(self, file_path: str) -> bool:
        """
        Check if a file should be excluded from indexing.

        Args:
            file_path: Relative file path

        Returns:
            True if file should be excluded
        """
        from fnmatch import fnmatch
        from pathlib import Path

        # Normalize path separators
        normalized_path = file_path.replace("\\", "/")
        path_parts = Path(normalized_path).parts

        for pattern in self.excluded_patterns:
            # Check full path match
            if fnmatch(normalized_path, pattern):
                return True

            # Check if any directory in the path matches directory patterns
            # This handles cases like .venv/, node_modules/, etc.
            if pattern.endswith("/*"):
                dir_pattern = pattern[:-2]  # Remove /*
                if dir_pattern.startswith("*/"):
                    dir_pattern = dir_pattern[2:]  # Remove */

                # Check if this directory appears anywhere in the path
                if dir_pattern in path_parts:
                    return True

            # Check if filename matches file patterns (like *.pyc, .env)
            # Also handle patterns like */.env which should match .env anywhere
            if not "/" in pattern or pattern.startswith("*/"):
                filename_pattern = pattern[2:] if pattern.startswith("*/") else pattern
                if fnmatch(Path(normalized_path).name, filename_pattern):
                    return True

        return False

    def _detect_language(self, file_path: str) -> Optional[str]:
        """
        Detect programming language from file extension using ParserFactory.

        Args:
            file_path: File path

        Returns:
            Language name or None if not supported
        """
        return ParserFactory.get_language_name(file_path)

    def _extract_symbols_simple(self, file_path: str, content: str, language: str) -> List[Symbol]:
        """
        Extract symbols using Tree-sitter parsers via ParserFactory.

        Args:
            file_path: Relative file path
            content: File content
            language: Programming language (not used, detection is by extension)

        Returns:
            List of extracted symbols
        """
        # Get appropriate parser from factory
        parser = ParserFactory.get_parser(file_path)

        if not parser:
            # Parser not implemented yet, return empty list
            logger.warning(f"No parser available for {file_path}, skipping symbol extraction")
            return []

        try:
            # Parse the file
            tree = parser.parse_file(file_path, content)
            if not tree:
                logger.error(f"Failed to parse {file_path}")
                return []

            # Extract symbols using the parser
            symbols = parser.extract_symbols(tree, file_path, content)
            return symbols

        except Exception as e:
            logger.error(f"Error extracting symbols from {file_path}: {e}")
            return []

    def _extract_symbols_fallback(
        self, file_path: str, content: str, language: str
    ) -> List[Symbol]:
        """
        Fallback symbol extraction using simple pattern matching.

        Used when Tree-sitter parser is not available for a language.

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
                        end_line=i,
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
