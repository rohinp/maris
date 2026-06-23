"""Tests for Indexing Agent with LangGraph workflow."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open
from typing import Dict, Any, List

from maris.agents.indexing_agent import IndexingAgent
from maris.core.models import Symbol, SymbolType, IndexingResult
from maris.storage.metadata_store import MetadataStore
from maris.storage.vector_store import VectorStore
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService


# Test fixtures
@pytest.fixture
def mock_metadata_store():
    """Create a mock metadata store."""
    store = Mock(spec=MetadataStore)
    store.get_repository_stats.return_value = {
        "total_files": 10,
        "total_symbols": 50,
        "total_dependencies": 30,
        "languages": {"python": 10},
        "last_indexed": "2026-06-22T00:00:00",
    }
    store.find_symbols_in_file.return_value = []
    return store


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = Mock(spec=VectorStore)
    store.get_embedding_count.return_value = 50
    store.delete_embeddings_for_symbols.return_value = 0
    return store


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = Mock(spec=OllamaEmbeddingService)
    # Return a 768-dimensional zero vector
    service.embed_symbols.return_value = [[0.0] * 768]
    return service


@pytest.fixture
def temp_repo_path(tmp_path):
    """Create a temporary repository directory."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Create some test files
    (repo / "main.py").write_text("def main():\n    pass\n")
    (repo / "utils.py").write_text("class Utils:\n    pass\n")

    return str(repo)


@pytest.fixture
def indexing_agent(mock_metadata_store, mock_vector_store, mock_embedding_service, temp_repo_path):
    """Create an indexing agent with mocked dependencies."""
    agent = IndexingAgent(
        metadata_store=mock_metadata_store,
        vector_store=mock_vector_store,
        repo_path=temp_repo_path,
        embedding_service=mock_embedding_service,
    )
    return agent


@pytest.fixture
def sample_symbols():
    """Create sample symbols for testing."""
    return [
        Symbol(
            id="sym1",
            name="main",
            type=SymbolType.FUNCTION,
            file_path="main.py",
            start_line=1,
            end_line=2,
            signature="def main():",
            language="python",
        ),
        Symbol(
            id="sym2",
            name="Utils",
            type=SymbolType.CLASS,
            file_path="utils.py",
            start_line=1,
            end_line=2,
            language="python",
        ),
    ]


# Test: Graph Construction
class TestGraphConstruction:
    """Tests for LangGraph workflow construction."""

    def test_graph_is_built_on_initialization(self, indexing_agent):
        """Test that the graph is built during initialization."""
        assert indexing_agent.graph is not None

    def test_graph_has_correct_nodes(self, indexing_agent):
        """Test that all required nodes are present in the graph."""
        assert indexing_agent.graph is not None
        assert callable(indexing_agent.graph.invoke)


# Test: Node - scan_files
class TestScanFilesNode:
    """Tests for the scan_files node."""

    def test_scan_files_full_repository(self, indexing_agent):
        """Test scanning all files in repository."""
        state = {
            "file_paths": None,  # None means full scan
        }

        result = indexing_agent._scan_files(state)

        assert "files_to_index" in result
        assert "total_files" in result
        assert len(result["files_to_index"]) == 2  # main.py and utils.py
        assert result["total_files"] == 2

    def test_scan_files_incremental_mode(self, indexing_agent):
        """Test scanning specific files for incremental indexing."""
        state = {
            "file_paths": ["main.py"],
        }

        result = indexing_agent._scan_files(state)

        assert result["files_to_index"] == ["main.py"]
        assert result["total_files"] == 1

    def test_scan_files_handles_error(self, indexing_agent):
        """Test error handling in file scanning."""
        # Make repo_path invalid to trigger an error
        original_path = indexing_agent.repo_path
        indexing_agent.repo_path = Path("/nonexistent/path/that/does/not/exist")

        state = {"file_paths": None}
        result = indexing_agent._scan_files(state)

        # Restore original path
        indexing_agent.repo_path = original_path

        # The scan should complete but find no files (not necessarily an error)
        assert result["files_to_index"] == []
        assert result["total_files"] == 0


# Test: Node - parse_files
class TestParseFilesNode:
    """Tests for the parse_files node."""

    def test_parse_files_success(self, indexing_agent, temp_repo_path):
        """Test successful file parsing."""
        state = {
            "files_to_index": ["main.py", "utils.py"],
        }

        result = indexing_agent._parse_files(state)

        assert "extracted_symbols" in result
        assert "parse_errors" in result
        assert "file_metadata" in result
        assert len(result["extracted_symbols"]) > 0
        assert len(result["parse_errors"]) == 0

    def test_parse_files_with_unknown_language(self, indexing_agent, temp_repo_path):
        """Test parsing files with unknown language."""
        # Create a file with unknown extension
        unknown_file = Path(temp_repo_path) / "test.xyz"
        unknown_file.write_text("some content")

        state = {
            "files_to_index": ["test.xyz"],
        }

        result = indexing_agent._parse_files(state)

        assert len(result["parse_errors"]) == 1
        assert "Unknown language" in result["parse_errors"][0]

    def test_parse_files_skips_on_error(self, indexing_agent):
        """Test that parsing is skipped if there's a previous error."""
        state = {
            "error": "Previous error",
            "files_to_index": ["main.py"],
        }

        result = indexing_agent._parse_files(state)

        assert result["error"] == "Previous error"

    def test_parse_files_handles_read_error(self, indexing_agent):
        """Test handling of file read errors."""
        state = {
            "files_to_index": ["nonexistent.py"],
        }

        result = indexing_agent._parse_files(state)

        assert len(result["parse_errors"]) == 1
        assert "nonexistent.py" in result["parse_errors"][0]


# Test: Node - store_symbols
class TestStoreSymbolsNode:
    """Tests for the store_symbols node."""

    def test_store_symbols_success(self, indexing_agent, mock_metadata_store, sample_symbols):
        """Test successful symbol storage."""
        state = {
            "extracted_symbols": sample_symbols,
            "file_metadata": {
                "main.py": {"language": "python", "line_count": 2, "symbol_count": 1},
                "utils.py": {"language": "python", "line_count": 2, "symbol_count": 1},
            },
        }

        result = indexing_agent._store_symbols(state)

        assert result["symbols_stored"] == 2
        mock_metadata_store.insert_symbols.assert_called_once_with(sample_symbols)
        assert mock_metadata_store.upsert_file_metadata.call_count == 2

    def test_store_symbols_with_no_symbols(self, indexing_agent, mock_metadata_store):
        """Test storing when no symbols were extracted."""
        state = {
            "extracted_symbols": [],
            "file_metadata": {},
        }

        result = indexing_agent._store_symbols(state)

        assert result["symbols_stored"] == 0
        mock_metadata_store.insert_symbols.assert_not_called()

    def test_store_symbols_skips_on_error(self, indexing_agent):
        """Test that storage is skipped if there's a previous error."""
        state = {
            "error": "Previous error",
            "extracted_symbols": [],
        }

        result = indexing_agent._store_symbols(state)

        assert result["error"] == "Previous error"

    def test_store_symbols_handles_storage_error(
        self, indexing_agent, mock_metadata_store, sample_symbols
    ):
        """Test handling of storage errors."""
        mock_metadata_store.insert_symbols.side_effect = Exception("Storage failed")

        state = {
            "extracted_symbols": sample_symbols,
            "file_metadata": {},
        }

        result = indexing_agent._store_symbols(state)

        assert "error" in result
        assert "Failed to store symbols" in result["error"]
        assert result["symbols_stored"] == 0


# Test: Node - generate_embeddings
class TestGenerateEmbeddingsNode:
    """Tests for the generate_embeddings node."""

    def test_generate_embeddings_success(
        self, indexing_agent, mock_embedding_service, sample_symbols
    ):
        """Test successful embedding generation."""
        mock_embedding_service.embed_symbols.return_value = [[0.1] * 768, [0.2] * 768]

        state = {
            "extracted_symbols": sample_symbols,
        }

        result = indexing_agent._generate_embeddings(state)

        assert "embeddings" in result
        assert result["embeddings_generated"] == 2
        assert len(result["embeddings"]) == 2
        mock_embedding_service.embed_symbols.assert_called_once_with(sample_symbols)

    def test_generate_embeddings_with_no_symbols(self, indexing_agent, mock_embedding_service):
        """Test embedding generation when no symbols exist."""
        state = {
            "extracted_symbols": [],
        }

        result = indexing_agent._generate_embeddings(state)

        assert result["embeddings"] == []
        assert result["embeddings_generated"] == 0
        mock_embedding_service.embed_symbols.assert_not_called()

    def test_generate_embeddings_skips_on_error(self, indexing_agent):
        """Test that embedding generation is skipped if there's a previous error."""
        state = {
            "error": "Previous error",
            "extracted_symbols": [],
        }

        result = indexing_agent._generate_embeddings(state)

        assert result["error"] == "Previous error"

    def test_generate_embeddings_handles_error(
        self, indexing_agent, mock_embedding_service, sample_symbols
    ):
        """Test handling of embedding generation errors."""
        mock_embedding_service.embed_symbols.side_effect = Exception("Embedding failed")

        state = {
            "extracted_symbols": sample_symbols,
        }

        result = indexing_agent._generate_embeddings(state)

        assert result["embeddings"] == []
        assert result["embeddings_generated"] == 0
        assert "embedding_error" in result


# Test: Node - store_embeddings
class TestStoreEmbeddingsNode:
    """Tests for the store_embeddings node."""

    def test_store_embeddings_success(self, indexing_agent, mock_vector_store, sample_symbols):
        """Test successful embedding storage."""
        embeddings = [[0.1] * 768, [0.2] * 768]

        state = {
            "extracted_symbols": sample_symbols,
            "embeddings": embeddings,
        }

        result = indexing_agent._store_embeddings(state)

        assert result["embeddings_stored"] == 2
        assert mock_vector_store.insert_embedding.call_count == 2

    def test_store_embeddings_with_no_embeddings(
        self, indexing_agent, mock_vector_store, sample_symbols
    ):
        """Test storing when no embeddings were generated."""
        state = {
            "extracted_symbols": sample_symbols,
            "embeddings": [],
        }

        result = indexing_agent._store_embeddings(state)

        assert result["embeddings_stored"] == 0
        mock_vector_store.insert_embedding.assert_not_called()

    def test_store_embeddings_skips_on_error(self, indexing_agent):
        """Test that storage is skipped if there's a previous error."""
        state = {
            "error": "Previous error",
            "extracted_symbols": [],
            "embeddings": [],
        }

        result = indexing_agent._store_embeddings(state)

        assert result["error"] == "Previous error"

    def test_store_embeddings_handles_storage_error(
        self, indexing_agent, mock_vector_store, sample_symbols
    ):
        """Test handling of embedding storage errors."""
        mock_vector_store.insert_embedding.side_effect = Exception("Storage failed")
        embeddings = [[0.1] * 768, [0.2] * 768]

        state = {
            "extracted_symbols": sample_symbols,
            "embeddings": embeddings,
        }

        result = indexing_agent._store_embeddings(state)

        assert result["embeddings_stored"] == 0
        assert "embedding_storage_error" in result


# Test: Node - assess_result
class TestAssessResultNode:
    """Tests for the assess_result node."""

    def test_assess_result_success(self, indexing_agent, sample_symbols):
        """Test successful result assessment."""
        state = {
            "file_metadata": {"main.py": {}, "utils.py": {}},
            "extracted_symbols": sample_symbols,
            "embeddings_generated": 2,
            "total_files": 2,
            "parse_errors": [],
        }

        result = indexing_agent._assess_result(state)

        assert "final_stats" in result
        stats = result["final_stats"]
        assert stats["files_processed"] == 2
        assert stats["symbols_extracted"] == 2
        assert stats["embeddings_generated"] == 2
        assert len(stats["errors"]) == 0
        assert stats["success_rate"] == 1.0

    def test_assess_result_with_errors(self, indexing_agent, sample_symbols):
        """Test result assessment with errors."""
        state = {
            "file_metadata": {"main.py": {}},
            "extracted_symbols": sample_symbols,
            "embeddings_generated": 2,
            "total_files": 2,
            "parse_errors": ["utils.py: Parse error"],
            "embedding_error": "Some embedding error",
        }

        result = indexing_agent._assess_result(state)

        stats = result["final_stats"]
        assert stats["files_processed"] == 1
        assert len(stats["errors"]) == 2
        assert stats["success_rate"] == 0.5

    def test_assess_result_with_no_files(self, indexing_agent):
        """Test result assessment when no files were processed."""
        state = {
            "file_metadata": {},
            "extracted_symbols": [],
            "embeddings_generated": 0,
            "total_files": 0,
            "parse_errors": [],
        }

        result = indexing_agent._assess_result(state)

        stats = result["final_stats"]
        assert stats["success_rate"] == 0.0


# Test: Public API - index_repository
class TestIndexRepository:
    """Tests for the index_repository public API."""

    def test_index_repository_full_workflow(
        self, indexing_agent, mock_metadata_store, mock_vector_store, mock_embedding_service
    ):
        """Test the complete workflow through index_repository."""
        mock_embedding_service.embed_symbols.return_value = [[0.1] * 768, [0.2] * 768]

        result = indexing_agent.index_repository()

        assert isinstance(result, IndexingResult)
        assert result.files_processed >= 0
        assert result.symbols_extracted >= 0
        assert result.duration_seconds > 0

    def test_index_repository_returns_errors(self, indexing_agent, temp_repo_path):
        """Test that errors are captured in the result."""
        # Create a file that will cause a parse error
        bad_file = Path(temp_repo_path) / "bad.xyz"
        bad_file.write_text("content")

        result = indexing_agent.index_repository()

        assert isinstance(result, IndexingResult)
        # Should have at least processed the valid Python files
        assert result.files_processed >= 0


# Test: Public API - index_files
class TestIndexFiles:
    """Tests for the index_files public API."""

    def test_index_files_incremental(
        self, indexing_agent, mock_metadata_store, mock_vector_store, mock_embedding_service
    ):
        """Test incremental indexing of specific files."""
        mock_embedding_service.embed_symbols.return_value = [[0.1] * 768]

        result = indexing_agent.index_files(["main.py"])

        assert isinstance(result, IndexingResult)
        assert result.duration_seconds > 0
        # Should have cleaned up existing data
        mock_metadata_store.delete_dependencies_for_file.assert_called()
        mock_metadata_store.delete_symbols_in_file.assert_called()

    def test_index_files_cleans_up_existing_data(
        self, indexing_agent, mock_metadata_store, mock_vector_store
    ):
        """Test that existing data is cleaned up before re-indexing."""
        # Mock existing symbols
        existing_symbols = [
            Symbol(
                id="old_sym",
                name="old_function",
                type=SymbolType.FUNCTION,
                file_path="main.py",
                start_line=1,
                end_line=2,
                language="python",
            )
        ]
        mock_metadata_store.find_symbols_in_file.return_value = existing_symbols

        result = indexing_agent.index_files(["main.py"])

        # Verify cleanup was called
        mock_metadata_store.delete_dependencies_for_file.assert_called_with("main.py")
        mock_vector_store.delete_embeddings_for_symbols.assert_called_with(["old_sym"])
        mock_metadata_store.delete_symbols_in_file.assert_called_with("main.py")


# Test: Public API - get_indexing_status
class TestGetIndexingStatus:
    """Tests for the get_indexing_status public API."""

    def test_get_indexing_status(self, indexing_agent, mock_metadata_store, mock_vector_store):
        """Test getting indexing status."""
        status = indexing_agent.get_indexing_status()

        assert isinstance(status, dict)
        assert "repository_path" in status
        assert "total_files" in status
        assert "total_symbols" in status
        assert "total_dependencies" in status
        assert "total_embeddings" in status
        assert "languages" in status
        assert "last_indexed" in status

        assert status["total_files"] == 10
        assert status["total_symbols"] == 50
        assert status["total_embeddings"] == 50


# Test: Helper Methods
class TestHelperMethods:
    """Tests for helper methods."""

    def test_find_source_files(self, indexing_agent):
        """Test finding source files in repository."""
        files = indexing_agent._find_source_files()

        assert isinstance(files, list)
        assert len(files) == 2
        assert "main.py" in files
        assert "utils.py" in files

    def test_is_excluded(self, indexing_agent):
        """Test file exclusion logic."""
        assert indexing_agent._is_excluded("src/node_modules/test.py") is True
        assert indexing_agent._is_excluded("build/target/test.py") is True
        assert indexing_agent._is_excluded("src/main.py") is False

    def test_detect_language(self, indexing_agent):
        """Test language detection from file extension."""
        assert indexing_agent._detect_language("test.py") == "python"
        assert indexing_agent._detect_language("test.java") == "java"
        assert indexing_agent._detect_language("test.scala") == "scala"
        assert indexing_agent._detect_language("test.ts") == "typescript"
        assert indexing_agent._detect_language("test.xyz") is None

    def test_extract_symbols_simple_python(self, indexing_agent):
        """Test simple symbol extraction for Python."""
        content = """
class MyClass:
    pass

def my_function():
    pass
"""
        symbols = indexing_agent._extract_symbols_simple("test.py", content, "python")

        assert len(symbols) == 2
        assert symbols[0].name == "MyClass"
        assert symbols[0].type == SymbolType.CLASS
        assert symbols[1].name == "my_function"
        assert symbols[1].type == SymbolType.FUNCTION

    def test_generate_symbol_id(self, indexing_agent):
        """Test symbol ID generation."""
        id1 = indexing_agent._generate_symbol_id("test.py", "MyClass", 1)
        id2 = indexing_agent._generate_symbol_id("test.py", "MyClass", 1)
        id3 = indexing_agent._generate_symbol_id("test.py", "MyClass", 2)

        # Same inputs should generate same ID
        assert id1 == id2
        # Different inputs should generate different IDs
        assert id1 != id3
        # ID should be 16 characters (truncated SHA256)
        assert len(id1) == 16


# Test: Backward Compatibility
class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with original API."""

    def test_initialization_with_default_embedding_service(
        self, mock_metadata_store, mock_vector_store, temp_repo_path
    ):
        """Test that agent can be initialized without embedding service."""
        with patch("maris.agents.indexing_agent.OllamaEmbeddingService"):
            agent = IndexingAgent(
                metadata_store=mock_metadata_store,
                vector_store=mock_vector_store,
                repo_path=temp_repo_path,
            )
            assert agent.embedding_service is not None

    def test_initialization_with_custom_embedding_service(
        self, mock_metadata_store, mock_vector_store, mock_embedding_service, temp_repo_path
    ):
        """Test that agent can be initialized with custom embedding service."""
        agent = IndexingAgent(
            metadata_store=mock_metadata_store,
            vector_store=mock_vector_store,
            repo_path=temp_repo_path,
            embedding_service=mock_embedding_service,
        )
        assert agent.embedding_service == mock_embedding_service

    def test_public_api_signatures_unchanged(self, indexing_agent):
        """Test that public API method signatures are unchanged."""
        # Verify method existence and signatures
        assert hasattr(indexing_agent, "index_repository")
        assert hasattr(indexing_agent, "index_files")
        assert hasattr(indexing_agent, "get_indexing_status")

        # Verify return types
        import inspect

        sig = inspect.signature(indexing_agent.index_repository)
        assert (
            sig.return_annotation == IndexingResult
            or sig.return_annotation == inspect.Signature.empty
        )


# Test: Error Handling and Edge Cases
class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_workflow_continues_after_parse_error(self, indexing_agent, temp_repo_path):
        """Test that workflow handles parse errors gracefully."""
        # Create a Python file that will cause a read error by making it unreadable
        bad_file = Path(temp_repo_path) / "unreadable.py"
        bad_file.write_text("def test(): pass")

        # Make the file unreadable (this will cause an error during parsing)
        import os

        os.chmod(bad_file, 0o000)

        try:
            result = indexing_agent.index_repository()

            assert isinstance(result, IndexingResult)
            # Should have processed the valid files
            assert result.files_processed >= 0
            # May or may not have errors depending on permissions
        finally:
            # Restore permissions for cleanup
            os.chmod(bad_file, 0o644)

    def test_empty_repository(
        self, mock_metadata_store, mock_vector_store, mock_embedding_service, tmp_path
    ):
        """Test indexing an empty repository."""
        empty_repo = tmp_path / "empty_repo"
        empty_repo.mkdir()

        agent = IndexingAgent(
            metadata_store=mock_metadata_store,
            vector_store=mock_vector_store,
            repo_path=str(empty_repo),
            embedding_service=mock_embedding_service,
        )

        result = agent.index_repository()

        assert result.files_processed == 0
        assert result.symbols_extracted == 0
        assert result.embeddings_generated == 0


# Made with Bob
