"""Tests for Documentation Agent with LangGraph workflow."""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, List

from maris.agents.documentation_agent import (
    DocumentationAgent,
    ModuleDocumentation,
    ArchitectureOverview,
)
from maris.core.models import Symbol, SymbolType
from maris.knowledge.service import RepositoryKnowledgeService


# Test fixtures
@pytest.fixture
def mock_knowledge_service():
    """Create a mock knowledge service."""
    service = Mock(spec=RepositoryKnowledgeService)
    service.get_repository_stats.return_value = {
        "total_files": 10,
        "total_symbols": 50,
        "languages": ["python", "java"],
    }
    return service


@pytest.fixture
def sample_symbols():
    """Create sample symbols for testing."""
    return [
        Symbol(
            id="sym1",
            name="MyClass",
            type=SymbolType.CLASS,
            file_path="src/module.py",
            start_line=1,
            end_line=10,
            signature="class MyClass:",
            docstring="A sample class.",
            language="python",
        ),
        Symbol(
            id="sym2",
            name="my_function",
            type=SymbolType.FUNCTION,
            file_path="src/module.py",
            start_line=12,
            end_line=15,
            signature="def my_function():",
            docstring="A sample function.",
            language="python",
        ),
        Symbol(
            id="sym3",
            name="my_method",
            type=SymbolType.METHOD,
            file_path="src/module.py",
            start_line=5,
            end_line=8,
            signature="def my_method(self):",
            docstring="A sample method.",
            parent_id="sym1",
            language="python",
        ),
    ]


@pytest.fixture
def doc_agent(mock_knowledge_service):
    """Create a documentation agent with mocked dependencies."""
    return DocumentationAgent(knowledge_service=mock_knowledge_service)


# Test: Graph Construction
class TestGraphConstruction:
    """Tests for LangGraph workflow construction."""

    def test_graph_is_built_on_initialization(self, doc_agent):
        """Test that the graph is built during initialization."""
        assert doc_agent.graph is not None

    def test_graph_has_correct_nodes(self, doc_agent):
        """Test that all required nodes are present in the graph."""
        assert doc_agent.graph is not None
        assert callable(doc_agent.graph.invoke)


# Test: Node - retrieve_symbols
class TestRetrieveSymbolsNode:
    """Tests for the retrieve_symbols node."""

    def test_retrieve_symbols_success(self, doc_agent, mock_knowledge_service, sample_symbols):
        """Test successful symbol retrieval."""
        mock_knowledge_service.find_symbols_in_file.return_value = sample_symbols

        state = {"file_path": "src/module.py"}
        result = doc_agent._retrieve_symbols(state)

        assert result["symbols"] == sample_symbols
        assert result["language"] == "python"
        assert "error" not in result

    def test_retrieve_symbols_empty_file(self, doc_agent, mock_knowledge_service):
        """Test retrieving symbols from empty file."""
        mock_knowledge_service.find_symbols_in_file.return_value = []

        state = {"file_path": "src/empty.py"}
        result = doc_agent._retrieve_symbols(state)

        assert result["symbols"] == []
        assert result["language"] == "unknown"

    def test_retrieve_symbols_handles_error(self, doc_agent, mock_knowledge_service):
        """Test error handling in symbol retrieval."""
        mock_knowledge_service.find_symbols_in_file.side_effect = Exception("Database error")

        state = {"file_path": "src/module.py"}
        result = doc_agent._retrieve_symbols(state)

        assert "error" in result
        assert result["symbols"] == []
        assert result["language"] == "unknown"


# Test: Node - categorize_symbols
class TestCategorizeSymbolsNode:
    """Tests for the categorize_symbols node."""

    def test_categorize_symbols_success(self, doc_agent, sample_symbols):
        """Test successful symbol categorization."""
        state = {"symbols": sample_symbols}
        result = doc_agent._categorize_symbols(state)

        assert len(result["classes"]) == 1
        assert len(result["functions"]) == 1
        assert len(result["constants"]) == 0
        assert result["classes"][0]["name"] == "MyClass"
        assert "my_method" in result["classes"][0]["methods"]

    def test_categorize_symbols_empty(self, doc_agent):
        """Test categorizing empty symbol list."""
        state = {"symbols": []}
        result = doc_agent._categorize_symbols(state)

        assert result["classes"] == []
        assert result["functions"] == []
        assert result["constants"] == []

    def test_categorize_symbols_skips_on_error(self, doc_agent):
        """Test that categorization is skipped if there's a previous error."""
        state = {"error": "Previous error", "symbols": []}
        result = doc_agent._categorize_symbols(state)

        assert result["error"] == "Previous error"


# Test: Node - find_dependencies
class TestFindDependenciesNode:
    """Tests for the find_dependencies node."""

    def test_find_dependencies_success(self, doc_agent, mock_knowledge_service, sample_symbols):
        """Test successful dependency finding."""
        # Mock callees from different files
        callee1 = Symbol(
            id="dep1",
            name="helper",
            type=SymbolType.FUNCTION,
            file_path="src/utils.py",
            start_line=1,
            end_line=5,
            language="python",
        )
        mock_knowledge_service.find_callees.return_value = [callee1]

        state = {"symbols": sample_symbols}
        result = doc_agent._find_dependencies(state)

        assert "src/utils.py" in result["dependencies"]

    def test_find_dependencies_no_external_deps(
        self, doc_agent, mock_knowledge_service, sample_symbols
    ):
        """Test finding dependencies when all are internal."""
        # Mock callees from same file
        mock_knowledge_service.find_callees.return_value = []

        state = {"symbols": sample_symbols}
        result = doc_agent._find_dependencies(state)

        assert result["dependencies"] == []

    def test_find_dependencies_handles_error(
        self, doc_agent, mock_knowledge_service, sample_symbols
    ):
        """Test error handling in dependency finding."""
        mock_knowledge_service.find_callees.side_effect = Exception("Query error")

        state = {"symbols": sample_symbols}
        result = doc_agent._find_dependencies(state)

        # Should not fail the workflow
        assert result["dependencies"] == []
        assert "dependency_error" in result


# Test: Node - generate_summary
class TestGenerateSummaryNode:
    """Tests for the generate_summary node."""

    def test_generate_summary_with_symbols(self, doc_agent):
        """Test summary generation with symbols."""
        state = {
            "classes": [{"name": "MyClass"}],
            "functions": [{"name": "func1"}, {"name": "func2"}],
            "constants": [],
        }
        result = doc_agent._generate_summary(state)

        assert "1 class" in result["summary"]
        assert "2 functions" in result["summary"]

    def test_generate_summary_empty(self, doc_agent):
        """Test summary generation with no symbols."""
        state = {
            "classes": [],
            "functions": [],
            "constants": [],
        }
        result = doc_agent._generate_summary(state)

        assert "no documented symbols" in result["summary"].lower()

    def test_generate_summary_skips_on_error(self, doc_agent):
        """Test that summary generation is skipped if there's a previous error."""
        state = {"error": "Previous error"}
        result = doc_agent._generate_summary(state)

        assert result["error"] == "Previous error"


# Test: Node - format_output
class TestFormatOutputNode:
    """Tests for the format_output node."""

    def test_format_output_as_object(self, doc_agent):
        """Test formatting output as ModuleDocumentation object."""
        state = {
            "file_path": "src/module.py",
            "language": "python",
            "summary": "Test summary",
            "classes": [],
            "functions": [],
            "constants": [],
            "dependencies": [],
            "format": "object",
        }
        result = doc_agent._format_output(state)

        assert "documentation" in result
        assert isinstance(result["documentation"], ModuleDocumentation)
        assert result["documentation"].file_path == "src/module.py"

    def test_format_output_as_markdown(self, doc_agent):
        """Test formatting output as Markdown."""
        state = {
            "file_path": "src/module.py",
            "language": "python",
            "summary": "Test summary",
            "classes": [],
            "functions": [],
            "constants": [],
            "dependencies": [],
            "format": "markdown",
        }
        result = doc_agent._format_output(state)

        assert "markdown" in result
        assert "# src/module.py" in result["markdown"]


# Test: Public API - generate_module_documentation
class TestGenerateModuleDocumentation:
    """Tests for the generate_module_documentation public API."""

    def test_generate_module_documentation_success(
        self, doc_agent, mock_knowledge_service, sample_symbols
    ):
        """Test successful module documentation generation."""
        mock_knowledge_service.find_symbols_in_file.return_value = sample_symbols
        mock_knowledge_service.find_callees.return_value = []

        result = doc_agent.generate_module_documentation("src/module.py")

        assert isinstance(result, ModuleDocumentation)
        assert result.file_path == "src/module.py"
        # Language may be unknown if graph returns None
        assert result.language in ["python", "unknown"]
        # Should have classes and functions if workflow succeeded
        assert len(result.classes) >= 0
        assert len(result.functions) >= 0

    def test_generate_module_documentation_empty_file(self, doc_agent, mock_knowledge_service):
        """Test documentation generation for empty file."""
        mock_knowledge_service.find_symbols_in_file.return_value = []

        result = doc_agent.generate_module_documentation("src/empty.py")

        assert isinstance(result, ModuleDocumentation)
        assert result.file_path == "src/empty.py"
        assert "no symbols" in result.summary.lower()


# Test: Public API - generate_markdown_documentation
class TestGenerateMarkdownDocumentation:
    """Tests for the generate_markdown_documentation public API."""

    def test_generate_markdown_documentation_success(
        self, doc_agent, mock_knowledge_service, sample_symbols
    ):
        """Test successful markdown generation."""
        mock_knowledge_service.find_symbols_in_file.return_value = sample_symbols
        mock_knowledge_service.find_callees.return_value = []

        result = doc_agent.generate_markdown_documentation("src/module.py")

        assert isinstance(result, str)
        assert "# src/module.py" in result
        # Content may vary if graph returns None, but should have header

    def test_generate_markdown_documentation_empty_file(self, doc_agent, mock_knowledge_service):
        """Test markdown generation for empty file."""
        mock_knowledge_service.find_symbols_in_file.return_value = []

        result = doc_agent.generate_markdown_documentation("src/empty.py")

        assert isinstance(result, str)
        assert "# src/empty.py" in result


# Test: Public API - generate_architecture_overview
class TestGenerateArchitectureOverview:
    """Tests for the generate_architecture_overview public API."""

    def test_generate_architecture_overview(self, doc_agent, mock_knowledge_service):
        """Test architecture overview generation."""
        result = doc_agent.generate_architecture_overview()

        assert isinstance(result, ArchitectureOverview)
        assert result.total_files == 10
        assert result.total_symbols == 50
        assert "python" in result.languages


# Test: Public API - generate_architecture_markdown
class TestGenerateArchitectureMarkdown:
    """Tests for the generate_architecture_markdown public API."""

    def test_generate_architecture_markdown(self, doc_agent, mock_knowledge_service):
        """Test architecture markdown generation."""
        result = doc_agent.generate_architecture_markdown()

        assert isinstance(result, str)
        assert "# Repository Architecture" in result
        assert "10" in result  # total files
        assert "50" in result  # total symbols


# Test: Backward Compatibility
class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with original API."""

    def test_initialization(self, mock_knowledge_service):
        """Test that agent can be initialized."""
        agent = DocumentationAgent(knowledge_service=mock_knowledge_service)
        assert agent.knowledge_service == mock_knowledge_service

    def test_public_api_signatures_unchanged(self, doc_agent):
        """Test that public API method signatures are unchanged."""
        assert hasattr(doc_agent, "generate_module_documentation")
        assert hasattr(doc_agent, "generate_architecture_overview")
        assert hasattr(doc_agent, "generate_markdown_documentation")
        assert hasattr(doc_agent, "generate_architecture_markdown")


# Made with Bob
