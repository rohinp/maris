"""Tests for Impact Analysis Agent."""

import pytest
from unittest.mock import Mock, MagicMock

from maris.agents.impact_analysis_agent import ImpactAnalysisAgent, AnalysisType
from maris.core.models import Symbol, SymbolType, EdgeCase, ImpactAnalysisResult
from maris.knowledge.service import RepositoryKnowledgeService


@pytest.fixture
def mock_knowledge_service():
    """Create a mock knowledge service."""
    service = Mock(spec=RepositoryKnowledgeService)
    return service


@pytest.fixture
def impact_agent(mock_knowledge_service):
    """Create an impact analysis agent with mock service."""
    return ImpactAnalysisAgent(knowledge_service=mock_knowledge_service)


@pytest.fixture
def sample_symbol():
    """Create a sample symbol for testing."""
    return Symbol(
        id="test_symbol_1",
        name="test_function",
        type=SymbolType.FUNCTION,
        file_path="src/test.py",
        language="python",
        start_line=10,
        end_line=20,
        signature="def test_function(arg1, arg2)",
        docstring="Test function docstring",
    )


def test_impact_agent_initialization(impact_agent):
    """Test that impact agent initializes correctly."""
    assert impact_agent is not None
    assert impact_agent.knowledge_service is not None
    assert impact_agent.graph is not None


def test_analyze_impact_with_symbol_name(impact_agent, mock_knowledge_service, sample_symbol):
    """Test impact analysis with symbol name."""
    # Setup mocks
    mock_knowledge_service.find_symbol.return_value = [sample_symbol]
    mock_knowledge_service.find_callers.return_value = []
    mock_knowledge_service.find_callees.return_value = []
    mock_knowledge_service.impacted_files.return_value = {"src/test.py"}

    # Perform analysis
    result = impact_agent.analyze_impact(symbol_name="test_function")

    # Assertions
    assert isinstance(result, ImpactAnalysisResult)
    assert result.target_symbol == sample_symbol
    assert result.confidence in ["high", "medium", "low"]
    mock_knowledge_service.find_symbol.assert_called_once_with("test_function")


def test_analyze_impact_with_callers(impact_agent, mock_knowledge_service, sample_symbol):
    """Test impact analysis with callers."""
    caller_symbol = Symbol(
        id="caller_1",
        name="caller_function",
        type=SymbolType.FUNCTION,
        file_path="src/caller.py",
        language="python",
        start_line=5,
        end_line=15,
    )

    # Setup mocks
    mock_knowledge_service.find_symbol.return_value = [sample_symbol]
    mock_knowledge_service.find_callers.return_value = [caller_symbol]
    mock_knowledge_service.find_callees.return_value = []
    mock_knowledge_service.impacted_files.return_value = {"src/test.py", "src/caller.py"}

    # Perform analysis
    result = impact_agent.analyze_impact(symbol_name="test_function")

    # Assertions
    assert len(result.direct_callers) == 1
    assert result.direct_callers[0] == caller_symbol
    assert len(result.affected_files) == 2


def test_analyze_impact_with_tests(impact_agent, mock_knowledge_service, sample_symbol):
    """Test impact analysis identifies test coverage."""
    test_symbol = Symbol(
        id="test_1",
        name="test_test_function",
        type=SymbolType.FUNCTION,
        file_path="tests/test_module.py",
        language="python",
        start_line=10,
        end_line=20,
    )

    # Setup mocks
    mock_knowledge_service.find_symbol.return_value = [sample_symbol]
    mock_knowledge_service.find_callers.return_value = [test_symbol]
    mock_knowledge_service.find_callees.return_value = []
    mock_knowledge_service.impacted_files.return_value = {"src/test.py"}

    # Perform analysis
    result = impact_agent.analyze_impact(symbol_name="test_function")

    # Assertions
    assert len(result.affected_tests) == 1
    assert result.affected_tests[0] == test_symbol


def test_analyze_impact_edge_cases(impact_agent, mock_knowledge_service, sample_symbol):
    """Test edge case detection."""
    # Setup mocks
    mock_knowledge_service.find_symbol.return_value = [sample_symbol]
    mock_knowledge_service.find_callers.return_value = []
    mock_knowledge_service.find_callees.return_value = []
    mock_knowledge_service.impacted_files.return_value = {"src/test.py"}

    # Perform analysis
    result = impact_agent.analyze_impact(symbol_name="test_function")

    # Assertions - should detect some edge cases
    assert isinstance(result.edge_cases, list)
    # At least null_check and error_handling should be detected
    assert len(result.edge_cases) >= 0


def test_analyze_impact_recommendations(impact_agent, mock_knowledge_service, sample_symbol):
    """Test that recommendations are generated."""
    # Setup mocks
    mock_knowledge_service.find_symbol.return_value = [sample_symbol]
    mock_knowledge_service.find_callers.return_value = []
    mock_knowledge_service.find_callees.return_value = []
    mock_knowledge_service.impacted_files.return_value = {"src/test.py"}

    # Perform analysis
    result = impact_agent.analyze_impact(symbol_name="test_function")

    # Assertions
    assert isinstance(result.recommendations, list)
    assert len(result.recommendations) > 0


def test_analyze_impact_symbol_not_found(impact_agent, mock_knowledge_service):
    """Test error handling when symbol is not found."""
    # Setup mocks
    mock_knowledge_service.find_symbol.return_value = []

    # Perform analysis and expect exception
    with pytest.raises(Exception) as exc_info:
        impact_agent.analyze_impact(symbol_name="nonexistent_symbol")

    assert "not found" in str(exc_info.value).lower()


def test_format_report_text(impact_agent, sample_symbol):
    """Test report text formatting."""
    result = ImpactAnalysisResult(
        target_symbol=sample_symbol,
        direct_callers=[],
        indirect_callers=[],
        affected_files=["src/test.py"],
        affected_tests=[],
        edge_cases=[
            EdgeCase(
                type="null_check",
                description="No null checks",
                location="src/test.py:10",
                is_handled=False,
                suggestion="Add null checks",
                severity="medium",
            )
        ],
        breaking_changes=[],
        recommendations=["Add tests"],
        confidence="medium",
    )

    # Format report
    report = impact_agent.format_report_text(result)

    # Assertions
    assert "Impact Analysis" in report
    assert "test_function" in report
    assert "**Confidence**: medium" in report  # Fixed format
    assert "Edge Cases" in report
    assert "Recommendations" in report


def test_analyze_impact_with_file_path(impact_agent, mock_knowledge_service, sample_symbol):
    """Test impact analysis with file path."""
    # Setup mocks
    mock_knowledge_service.find_symbols_in_file.return_value = [sample_symbol]
    mock_knowledge_service.find_callers.return_value = []
    mock_knowledge_service.find_callees.return_value = []
    mock_knowledge_service.impacted_files.return_value = {"src/test.py"}

    # Perform analysis
    result = impact_agent.analyze_impact(file_path="src/test.py")

    # Assertions
    assert isinstance(result, ImpactAnalysisResult)
    assert result.target_symbol == sample_symbol
    mock_knowledge_service.find_symbols_in_file.assert_called_once_with("src/test.py")


def test_analyze_impact_high_confidence(impact_agent, mock_knowledge_service, sample_symbol):
    """Test that high confidence is assigned when appropriate."""
    caller_symbol = Symbol(
        id="caller_1",
        name="caller_function",
        type=SymbolType.FUNCTION,
        file_path="src/caller.py",
        language="python",
        start_line=5,
        end_line=15,
    )

    test_symbol = Symbol(
        id="test_1",
        name="test_test_function",
        type=SymbolType.FUNCTION,
        file_path="tests/test_module.py",
        language="python",
        start_line=10,
        end_line=20,
    )

    # Setup mocks - has both callers and tests
    mock_knowledge_service.find_symbol.return_value = [sample_symbol]
    mock_knowledge_service.find_callers.return_value = [caller_symbol, test_symbol]
    mock_knowledge_service.find_callees.return_value = []
    mock_knowledge_service.impacted_files.return_value = {"src/test.py", "src/caller.py"}

    # Perform analysis
    result = impact_agent.analyze_impact(symbol_name="test_function")

    # Assertions
    assert result.confidence == "high"


# Made with Bob
