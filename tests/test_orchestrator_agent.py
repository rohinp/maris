"""Tests for the Orchestrator Agent."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from maris.agents.documentation_agent import ArchitectureOverview, ModuleDocumentation
from maris.agents.orchestrator_agent import OrchestratorAgent, TaskType
from maris.agents.qa_agent import Answer
from maris.core.models import IndexingResult, Symbol, SymbolType


@pytest.fixture
def mock_knowledge_service():
    """Create a mock knowledge service."""
    service = Mock()
    service.search_symbols.return_value = []
    service.get_symbol_by_id.return_value = None
    service.get_all_symbols.return_value = []
    return service


@pytest.fixture
def mock_metadata_store():
    """Create a mock metadata store."""
    store = Mock()
    store.store_symbol.return_value = None
    store.get_symbol.return_value = None
    store.get_all_symbols.return_value = []
    return store


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = Mock()
    store.store_embedding.return_value = None
    store.search.return_value = []
    return store


@pytest.fixture
def sample_symbol():
    """Create a sample symbol for search results."""
    return Symbol(
        id="test-symbol",
        name="test_function",
        type=SymbolType.FUNCTION,
        file_path="test.py",
        language="python",
        start_line=1,
        end_line=5,
    )


@pytest.fixture
def orchestrator_agent(mock_knowledge_service, mock_metadata_store, mock_vector_store, tmp_path):
    """Create an orchestrator agent for testing."""
    repo_path = str(tmp_path / "test_repo")
    Path(repo_path).mkdir(parents=True, exist_ok=True)

    agent = OrchestratorAgent(
        knowledge_service=mock_knowledge_service,
        metadata_store=mock_metadata_store,
        vector_store=mock_vector_store,
        repo_path=repo_path,
    )
    return agent


class TestOrchestratorAgentInitialization:
    """Test orchestrator agent initialization."""

    def test_initialization(self, orchestrator_agent):
        """Test that orchestrator initializes correctly."""
        assert orchestrator_agent is not None
        assert orchestrator_agent.qa_agent is not None
        assert orchestrator_agent.indexing_agent is not None
        assert orchestrator_agent.documentation_agent is not None
        assert orchestrator_agent.graph is not None

    def test_has_all_specialized_agents(self, orchestrator_agent):
        """Test that orchestrator has all specialized agents."""
        assert hasattr(orchestrator_agent, "qa_agent")
        assert hasattr(orchestrator_agent, "indexing_agent")
        assert hasattr(orchestrator_agent, "documentation_agent")
        assert hasattr(orchestrator_agent, "git_agent")
        assert hasattr(orchestrator_agent, "impact_analysis_agent")


class TestTaskClassification:
    """Test task classification node."""

    def test_classify_question_task(self, orchestrator_agent):
        """Test classification of question tasks."""
        state = {
            "request": "What does the main function do?",
            "task_type": None,
        }
        result = orchestrator_agent._classify_task(state)
        assert result["classified_task"] == TaskType.QUESTION

    def test_classify_index_task(self, orchestrator_agent):
        """Test classification of indexing tasks."""
        state = {
            "request": "Index the repository",
            "task_type": None,
        }
        result = orchestrator_agent._classify_task(state)
        assert result["classified_task"] == TaskType.INDEX

    def test_classify_document_task(self, orchestrator_agent):
        """Test classification of documentation tasks."""
        state = {
            "request": "Generate documentation for the module",
            "task_type": None,
        }
        result = orchestrator_agent._classify_task(state)
        assert result["classified_task"] == TaskType.DOCUMENT

    def test_classify_status_task(self, orchestrator_agent):
        """Test classification of status tasks."""
        state = {
            "request": "Show me the indexing status",
            "task_type": None,
        }
        result = orchestrator_agent._classify_task(state)
        assert result["classified_task"] == TaskType.STATUS

    def test_classify_search_task(self, orchestrator_agent):
        """Test classification of search tasks."""
        state = {
            "request": "Search for RepositoryKnowledge",
            "task_type": None,
        }
        result = orchestrator_agent._classify_task(state)
        assert result["classified_task"] == TaskType.SEARCH

    def test_classify_tests_cover_as_impact_task(self, orchestrator_agent):
        """Test that test coverage wording routes to impact analysis."""
        state = {
            "request": "Which tests cover GitAgent.detect_changes?",
            "task_type": None,
        }
        result = orchestrator_agent._classify_task(state)
        assert result["classified_task"] == TaskType.IMPACT_ANALYSIS

    def test_explicit_task_type(self, orchestrator_agent):
        """Test that explicit task type is used when provided."""
        state = {
            "request": "Some request",
            "task_type": "index",
        }
        result = orchestrator_agent._classify_task(state)
        assert result["classified_task"] == TaskType.INDEX

    def test_default_to_question(self, orchestrator_agent):
        """Test that ambiguous requests default to question."""
        state = {
            "request": "Tell me about the code",
            "task_type": None,
        }
        result = orchestrator_agent._classify_task(state)
        assert result["classified_task"] == TaskType.QUESTION

    def test_classification_error_handling(self, orchestrator_agent):
        """Test error handling in classification."""
        state = {
            "request": "Test request",
            "task_type": "invalid_type",
        }
        result = orchestrator_agent._classify_task(state)
        assert "error" in result
        assert result["classified_task"] == TaskType.UNKNOWN


class TestAgentRouting:
    """Test agent routing node."""

    def test_route_to_qa_agent(self, orchestrator_agent):
        """Test routing to QA agent."""
        state = {
            "classified_task": TaskType.QUESTION,
        }
        result = orchestrator_agent._route_to_agent(state)
        assert result["selected_agent"] == "qa_agent"

    def test_route_to_indexing_agent(self, orchestrator_agent):
        """Test routing to indexing agent."""
        state = {
            "classified_task": TaskType.INDEX,
        }
        result = orchestrator_agent._route_to_agent(state)
        assert result["selected_agent"] == "indexing_agent"

    def test_route_to_documentation_agent(self, orchestrator_agent):
        """Test routing to documentation agent."""
        state = {
            "classified_task": TaskType.DOCUMENT,
        }
        result = orchestrator_agent._route_to_agent(state)
        assert result["selected_agent"] == "documentation_agent"

    def test_route_status_to_indexing_agent(self, orchestrator_agent):
        """Test that status requests route to indexing agent."""
        state = {
            "classified_task": TaskType.STATUS,
        }
        result = orchestrator_agent._route_to_agent(state)
        assert result["selected_agent"] == "indexing_agent"

    def test_route_to_repository_knowledge_for_search(self, orchestrator_agent):
        """Test routing search tasks to repository knowledge."""
        state = {
            "classified_task": TaskType.SEARCH,
        }
        result = orchestrator_agent._route_to_agent(state)
        assert result["selected_agent"] == "repository_knowledge"

    def test_route_clear_index_to_indexing_agent(self, orchestrator_agent):
        """Test routing clear-index tasks through the indexing boundary."""
        state = {
            "classified_task": TaskType.CLEAR_INDEX,
        }
        result = orchestrator_agent._route_to_agent(state)
        assert result["selected_agent"] == "indexing_agent"

    def test_route_unknown_task(self, orchestrator_agent):
        """Test routing of unknown task type."""
        state = {
            "classified_task": TaskType.UNKNOWN,
        }
        result = orchestrator_agent._route_to_agent(state)
        assert "error" in result

    def test_routing_preserves_error(self, orchestrator_agent):
        """Test that routing preserves existing errors."""
        state = {
            "error": "Previous error",
            "classified_task": TaskType.QUESTION,
        }
        result = orchestrator_agent._route_to_agent(state)
        assert result["error"] == "Previous error"


class TestTaskExecution:
    """Test task execution node."""

    def test_execute_qa_task(self, orchestrator_agent):
        """Test execution of QA task."""
        # Mock QA agent
        mock_answer = Answer(
            question="What is this?",
            answer="Test answer",
            relevant_symbols=[],
            confidence="high",
            sources=[],
        )
        orchestrator_agent.qa_agent.answer_question = Mock(return_value=mock_answer)

        state = {
            "selected_agent": "qa_agent",
            "classified_task": TaskType.QUESTION,
            "request": "What is this?",
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == mock_answer
        orchestrator_agent.qa_agent.answer_question.assert_called_once_with(
            "What is this?", max_symbols=10
        )

    def test_execute_qa_task_with_max_symbols(self, orchestrator_agent):
        """Test that max_symbols is passed to QA agent."""
        mock_answer = Answer(
            question="What is this?",
            answer="Test answer",
            relevant_symbols=[],
            confidence="high",
            sources=[],
        )
        orchestrator_agent.qa_agent.answer_question = Mock(return_value=mock_answer)

        state = {
            "selected_agent": "qa_agent",
            "classified_task": TaskType.QUESTION,
            "request": "What is this?",
            "max_symbols": 3,
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        orchestrator_agent.qa_agent.answer_question.assert_called_once_with(
            "What is this?", max_symbols=3
        )

    def test_execute_search_task(self, orchestrator_agent, sample_symbol):
        """Test execution of search task through repository knowledge."""
        search_results = [(sample_symbol, 0.9)]
        orchestrator_agent.knowledge_service.semantic_search = Mock(return_value=search_results)

        state = {
            "selected_agent": "repository_knowledge",
            "classified_task": TaskType.SEARCH,
            "request": "test_function",
            "max_results": 5,
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == search_results
        orchestrator_agent.knowledge_service.semantic_search.assert_called_once_with(
            "test_function", limit=5
        )

    def test_execute_clear_index_task(self, orchestrator_agent):
        """Test execution of clear-index task through orchestrator."""
        clear_result = {"metadata_tables": ["symbols"], "vector_table": "embeddings"}
        orchestrator_agent._clear_indexed_data = Mock(return_value=clear_result)

        state = {
            "selected_agent": "indexing_agent",
            "classified_task": TaskType.CLEAR_INDEX,
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == clear_result
        orchestrator_agent._clear_indexed_data.assert_called_once()

    def test_execute_index_repository_task(self, orchestrator_agent):
        """Test execution of repository indexing task."""
        # Mock indexing agent
        mock_result = IndexingResult(
            files_processed=10,
            symbols_extracted=50,
            embeddings_generated=50,
        )
        orchestrator_agent.indexing_agent.index_repository = Mock(return_value=mock_result)

        state = {
            "selected_agent": "indexing_agent",
            "classified_task": TaskType.INDEX,
            "file_paths": None,
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == mock_result
        orchestrator_agent.indexing_agent.index_repository.assert_called_once()

    def test_execute_index_files_task(self, orchestrator_agent):
        """Test execution of file indexing task."""
        # Mock indexing agent
        mock_result = IndexingResult(
            files_processed=2,
            symbols_extracted=10,
            embeddings_generated=10,
        )
        orchestrator_agent.indexing_agent.index_files = Mock(return_value=mock_result)

        state = {
            "selected_agent": "indexing_agent",
            "classified_task": TaskType.INDEX,
            "file_paths": ["file1.py", "file2.py"],
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == mock_result
        orchestrator_agent.indexing_agent.index_files.assert_called_once_with(
            ["file1.py", "file2.py"]
        )

    def test_execute_status_task(self, orchestrator_agent):
        """Test execution of status task."""
        # Mock indexing agent
        mock_status = {"total_symbols": 100, "total_files": 20}
        orchestrator_agent.indexing_agent.get_indexing_status = Mock(return_value=mock_status)

        state = {
            "selected_agent": "indexing_agent",
            "classified_task": TaskType.STATUS,
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == mock_status
        orchestrator_agent.indexing_agent.get_indexing_status.assert_called_once()

    def test_execute_module_documentation_task(self, orchestrator_agent):
        """Test execution of module documentation task."""
        # Mock documentation agent
        mock_doc = ModuleDocumentation(
            file_path="test.py",
            language="python",
            summary="Test module",
            classes=[],
            functions=[],
            constants=[],
            dependencies=[],
        )
        orchestrator_agent.documentation_agent.generate_module_documentation = Mock(
            return_value=mock_doc
        )

        state = {
            "selected_agent": "documentation_agent",
            "classified_task": TaskType.DOCUMENT,
            "file_path": "test.py",
            "format": "object",
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == mock_doc
        orchestrator_agent.documentation_agent.generate_module_documentation.assert_called_once_with(
            "test.py"
        )

    def test_execute_module_documentation_markdown(self, orchestrator_agent):
        """Test execution of module documentation in markdown format."""
        # Mock documentation agent
        mock_markdown = "# Test Module\n\nTest documentation"
        orchestrator_agent.documentation_agent.generate_markdown_documentation = Mock(
            return_value=mock_markdown
        )

        state = {
            "selected_agent": "documentation_agent",
            "classified_task": TaskType.DOCUMENT,
            "file_path": "test.py",
            "format": "markdown",
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == mock_markdown
        orchestrator_agent.documentation_agent.generate_markdown_documentation.assert_called_once_with(
            "test.py"
        )

    def test_execute_architecture_overview_task(self, orchestrator_agent):
        """Test execution of architecture overview task."""
        # Mock documentation agent
        mock_overview = ArchitectureOverview(
            total_files=10,
            total_symbols=70,
            languages=["python"],
            key_modules=[],
            dependency_graph_summary="Test summary",
        )
        orchestrator_agent.documentation_agent.generate_architecture_overview = Mock(
            return_value=mock_overview
        )

        state = {
            "selected_agent": "documentation_agent",
            "classified_task": TaskType.DOCUMENT,
            "file_path": None,
            "format": "object",
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == mock_overview
        orchestrator_agent.documentation_agent.generate_architecture_overview.assert_called_once()

    def test_execute_architecture_markdown(self, orchestrator_agent):
        """Test execution of architecture overview in markdown format."""
        # Mock documentation agent
        mock_markdown = "# Architecture Overview\n\nTest architecture"
        orchestrator_agent.documentation_agent.generate_architecture_markdown = Mock(
            return_value=mock_markdown
        )

        state = {
            "selected_agent": "documentation_agent",
            "classified_task": TaskType.DOCUMENT,
            "file_path": None,
            "format": "markdown",
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is True
        assert result["execution_result"] == mock_markdown
        orchestrator_agent.documentation_agent.generate_architecture_markdown.assert_called_once()

    def test_execution_error_handling(self, orchestrator_agent):
        """Test error handling during execution."""
        # Mock QA agent to raise exception
        orchestrator_agent.qa_agent.answer_question = Mock(side_effect=Exception("Test error"))

        state = {
            "selected_agent": "qa_agent",
            "classified_task": TaskType.QUESTION,
            "request": "What is this?",
        }
        result = orchestrator_agent._execute_task(state)

        assert result["success"] is False
        assert "error" in result
        assert "Test error" in result["error"]

    def test_execution_preserves_error(self, orchestrator_agent):
        """Test that execution preserves existing errors."""
        state = {
            "error": "Previous error",
            "selected_agent": "qa_agent",
        }
        result = orchestrator_agent._execute_task(state)
        assert result["error"] == "Previous error"


class TestResponseFormatting:
    """Test response formatting node."""

    def test_format_successful_response(self, orchestrator_agent):
        """Test formatting of successful response."""
        state = {
            "classified_task": TaskType.QUESTION,
            "selected_agent": "qa_agent",
            "success": True,
            "execution_result": "Test result",
            "error": None,
            "request": "Test request",
        }
        result = orchestrator_agent._format_response(state)

        assert "orchestrator_result" in result
        orchestrator_result = result["orchestrator_result"]
        assert orchestrator_result.task_type == TaskType.QUESTION
        assert orchestrator_result.success is True
        assert orchestrator_result.result == "Test result"
        assert orchestrator_result.agent_used == "qa_agent"
        assert orchestrator_result.error is None

    def test_format_error_response(self, orchestrator_agent):
        """Test formatting of error response."""
        state = {
            "classified_task": TaskType.INDEX,
            "selected_agent": "indexing_agent",
            "success": False,
            "execution_result": None,
            "error": "Test error",
            "request": "Test request",
        }
        result = orchestrator_agent._format_response(state)

        assert "orchestrator_result" in result
        orchestrator_result = result["orchestrator_result"]
        assert orchestrator_result.success is False
        assert orchestrator_result.error == "Test error"

    def test_format_response_with_metadata(self, orchestrator_agent):
        """Test that response includes metadata."""
        state = {
            "classified_task": TaskType.DOCUMENT,
            "selected_agent": "documentation_agent",
            "success": True,
            "execution_result": "Test doc",
            "error": None,
            "request": "Generate docs",
            "file_path": "test.py",
            "file_paths": None,
        }
        result = orchestrator_agent._format_response(state)

        orchestrator_result = result["orchestrator_result"]
        assert orchestrator_result.metadata is not None
        assert orchestrator_result.metadata["request"] == "Generate docs"
        assert orchestrator_result.metadata["file_path"] == "test.py"

    def test_format_response_error_handling(self, orchestrator_agent):
        """Test error handling in response formatting."""
        # Create state that will cause formatting error
        state = {}
        result = orchestrator_agent._format_response(state)

        assert "orchestrator_result" in result
        orchestrator_result = result["orchestrator_result"]
        assert orchestrator_result.success is False
        # Error may be None if formatting succeeds with defaults
        assert orchestrator_result.task_type == TaskType.UNKNOWN


class TestFullWorkflow:
    """Test full orchestrator workflows."""

    def test_question_workflow(self, orchestrator_agent):
        """Test full workflow for answering questions."""
        # Mock QA agent
        mock_answer = Answer(
            question="What does this code do?",
            answer="Test answer",
            relevant_symbols=[],
            confidence="high",
            sources=[],
        )
        orchestrator_agent.qa_agent.answer_question = Mock(return_value=mock_answer)

        result = orchestrator_agent.execute("What does this code do?")

        assert result is not None
        assert result.task_type == TaskType.QUESTION
        assert result.success is True
        assert result.agent_used == "qa_agent"
        assert result.result == mock_answer

    def test_index_workflow(self, orchestrator_agent):
        """Test full workflow for indexing."""
        # Mock indexing agent
        mock_result = IndexingResult(
            files_processed=10,
            symbols_extracted=50,
            embeddings_generated=50,
        )
        orchestrator_agent.indexing_agent.index_repository = Mock(return_value=mock_result)

        result = orchestrator_agent.execute("Index the repository", task_type="index")

        assert result is not None
        assert result.task_type == TaskType.INDEX
        assert result.success is True
        assert result.agent_used == "indexing_agent"
        assert result.result == mock_result

    def test_documentation_workflow(self, orchestrator_agent):
        """Test full workflow for documentation generation."""
        # Mock documentation agent
        mock_doc = ModuleDocumentation(
            file_path="test.py",
            language="python",
            summary="Test module",
            classes=[],
            functions=[],
            constants=[],
            dependencies=[],
        )
        orchestrator_agent.documentation_agent.generate_module_documentation = Mock(
            return_value=mock_doc
        )

        result = orchestrator_agent.execute(
            "Generate documentation",
            task_type="document",
            file_path="test.py",
        )

        assert result is not None
        assert result.task_type == TaskType.DOCUMENT
        assert result.success is True
        assert result.agent_used == "documentation_agent"
        assert result.result == mock_doc

    def test_status_workflow(self, orchestrator_agent):
        """Test full workflow for status check."""
        # Mock indexing agent
        mock_status = {"total_symbols": 100}
        orchestrator_agent.indexing_agent.get_indexing_status = Mock(return_value=mock_status)

        result = orchestrator_agent.execute("Show status", task_type="status")

        assert result is not None
        assert result.task_type == TaskType.STATUS
        assert result.success is True
        assert result.agent_used == "indexing_agent"
        assert result.result == mock_status


class TestConvenienceMethods:
    """Test convenience methods."""

    def test_ask_question(self, orchestrator_agent):
        """Test ask_question convenience method."""
        mock_answer = Answer(
            question="What is this?",
            answer="Test answer",
            relevant_symbols=[],
            confidence="high",
            sources=[],
        )
        orchestrator_agent.qa_agent.answer_question = Mock(return_value=mock_answer)

        result = orchestrator_agent.ask_question("What is this?")

        assert result == mock_answer

    def test_ask_question_error(self, orchestrator_agent):
        """Test ask_question error handling."""
        orchestrator_agent.qa_agent.answer_question = Mock(side_effect=Exception("Test error"))

        with pytest.raises(Exception) as exc_info:
            orchestrator_agent.ask_question("What is this?")
        assert "Failed to answer question" in str(exc_info.value)

    def test_index_repository(self, orchestrator_agent):
        """Test index_repository convenience method."""
        mock_result = IndexingResult(
            files_processed=10,
            symbols_extracted=50,
            embeddings_generated=50,
        )
        orchestrator_agent.indexing_agent.index_repository = Mock(return_value=mock_result)

        result = orchestrator_agent.index_repository()

        assert result == mock_result

    def test_index_repository_error(self, orchestrator_agent):
        """Test index_repository error handling."""
        orchestrator_agent.indexing_agent.index_repository = Mock(
            side_effect=Exception("Test error")
        )

        with pytest.raises(Exception) as exc_info:
            orchestrator_agent.index_repository()
        assert "Failed to index repository" in str(exc_info.value)

    def test_index_files(self, orchestrator_agent):
        """Test index_files convenience method."""
        mock_result = IndexingResult(
            files_processed=2,
            symbols_extracted=10,
            embeddings_generated=10,
        )
        orchestrator_agent.indexing_agent.index_files = Mock(return_value=mock_result)

        result = orchestrator_agent.index_files(["file1.py", "file2.py"])

        assert result == mock_result

    def test_index_files_error(self, orchestrator_agent):
        """Test index_files error handling."""
        orchestrator_agent.indexing_agent.index_files = Mock(side_effect=Exception("Test error"))

        with pytest.raises(Exception) as exc_info:
            orchestrator_agent.index_files(["file1.py"])
        assert "Failed to index files" in str(exc_info.value)

    def test_generate_documentation(self, orchestrator_agent):
        """Test generate_documentation convenience method."""
        mock_doc = ModuleDocumentation(
            file_path="test.py",
            language="python",
            summary="Test module",
            classes=[],
            functions=[],
            constants=[],
            dependencies=[],
        )
        orchestrator_agent.documentation_agent.generate_module_documentation = Mock(
            return_value=mock_doc
        )

        result = orchestrator_agent.generate_documentation("test.py")

        assert result == mock_doc

    def test_generate_documentation_markdown(self, orchestrator_agent):
        """Test generate_documentation with markdown format."""
        mock_markdown = "# Test\n\nTest doc"
        orchestrator_agent.documentation_agent.generate_markdown_documentation = Mock(
            return_value=mock_markdown
        )

        result = orchestrator_agent.generate_documentation("test.py", format="markdown")

        assert result == mock_markdown

    def test_generate_documentation_error(self, orchestrator_agent):
        """Test generate_documentation error handling."""
        orchestrator_agent.documentation_agent.generate_module_documentation = Mock(
            side_effect=Exception("Test error")
        )

        with pytest.raises(Exception) as exc_info:
            orchestrator_agent.generate_documentation("test.py")
        assert "Failed to generate documentation" in str(exc_info.value)

    def test_get_status(self, orchestrator_agent):
        """Test get_status convenience method."""
        mock_status = {"total_symbols": 100}
        orchestrator_agent.indexing_agent.get_indexing_status = Mock(return_value=mock_status)

        result = orchestrator_agent.get_status()

        assert result == mock_status

    def test_get_status_error(self, orchestrator_agent):
        """Test get_status error handling."""
        orchestrator_agent.indexing_agent.get_indexing_status = Mock(
            side_effect=Exception("Test error")
        )

        with pytest.raises(Exception) as exc_info:
            orchestrator_agent.get_status()
        assert "Failed to get status" in str(exc_info.value)


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_request(self, orchestrator_agent):
        """Test handling of empty request."""
        result = orchestrator_agent.execute("")
        assert result is not None
        # Should default to question type
        assert result.task_type == TaskType.QUESTION

    def test_none_graph_result(self, orchestrator_agent):
        """Test handling when graph returns None."""
        # Mock graph to return None
        orchestrator_agent.graph.invoke = Mock(return_value=None)

        result = orchestrator_agent.execute("Test request")

        assert result is not None
        assert result.success is False
        assert result.error == "Workflow returned None"

    def test_multiple_task_keywords(self, orchestrator_agent):
        """Test request with multiple task type keywords."""
        # Should prioritize based on keyword order in classification logic
        result = orchestrator_agent.execute("Index and document the repository")
        assert result is not None
        # "index" appears first in the check order
        assert result.task_type == TaskType.INDEX


# Made with Bob
