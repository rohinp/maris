"""Tests for QA Agent with LangGraph workflow."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List

from maris.agents.qa_agent import QAAgent, Answer
from maris.core.models import Symbol, SymbolType, RetrievalContext
from maris.knowledge.service import RepositoryKnowledgeService


# Test fixtures
@pytest.fixture
def mock_knowledge_service():
    """Create a mock knowledge service."""
    service = Mock(spec=RepositoryKnowledgeService)
    return service


@pytest.fixture
def mock_ollama_client():
    """Create a mock Ollama client."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_symbols():
    """Create sample symbols for testing."""
    return [
        Symbol(
            id="sym1",
            name="calculate_sum",
            type=SymbolType.FUNCTION,
            file_path="src/math_utils.py",
            start_line=10,
            end_line=15,
            signature="def calculate_sum(a: int, b: int) -> int",
            docstring="Calculate the sum of two numbers.",
            language="python",
        ),
        Symbol(
            id="sym2",
            name="Calculator",
            type=SymbolType.CLASS,
            file_path="src/calculator.py",
            start_line=5,
            end_line=50,
            signature="class Calculator",
            docstring="A calculator class for basic arithmetic operations.",
            language="python",
        ),
        Symbol(
            id="sym3",
            name="multiply",
            type=SymbolType.FUNCTION,
            file_path="src/math_utils.py",
            start_line=20,
            end_line=25,
            signature="def multiply(x: float, y: float) -> float",
            docstring=None,  # No docstring
            language="python",
        ),
    ]


@pytest.fixture
def sample_retrieval_context(sample_symbols):
    """Create a sample retrieval context."""
    return RetrievalContext(
        primary_symbols=sample_symbols[:2],
        expanded_symbols=[sample_symbols[2]],
        related_files=["src/math_utils.py", "src/calculator.py"],
    )


@pytest.fixture
def qa_agent(mock_knowledge_service, mock_ollama_client):
    """Create a QA agent with mocked dependencies."""
    with patch("maris.agents.qa_agent.ollama.Client", return_value=mock_ollama_client):
        agent = QAAgent(
            knowledge_service=mock_knowledge_service,
            model="qwen2.5:7b",
        )
        agent.client = mock_ollama_client
        return agent


# Test: Graph Construction
class TestGraphConstruction:
    """Tests for LangGraph workflow construction."""

    def test_graph_is_built_on_initialization(self, qa_agent):
        """Test that the graph is built during initialization."""
        assert qa_agent.graph is not None

    def test_graph_has_correct_nodes(self, qa_agent):
        """Test that all required nodes are present in the graph."""
        # The graph should have been compiled
        assert qa_agent.graph is not None
        # We can't easily inspect compiled graph nodes, but we can verify it runs
        assert callable(qa_agent.graph.invoke)


# Test: Node - retrieve_context
class TestRetrieveContextNode:
    """Tests for the retrieve_context node."""

    def test_retrieve_context_success(
        self, qa_agent, mock_knowledge_service, sample_retrieval_context
    ):
        """Test successful context retrieval."""
        mock_knowledge_service.retrieve_context.return_value = sample_retrieval_context

        state = {
            "question": "How does calculate_sum work?",
            "max_symbols": 10,
        }

        result = qa_agent._retrieve_context(state)

        assert result["context"] == sample_retrieval_context
        assert len(result["relevant_symbols"]) == 2
        assert len(result["sources"]) == 2
        assert "error" not in result

    def test_retrieve_context_handles_error(self, qa_agent, mock_knowledge_service):
        """Test error handling in context retrieval."""
        mock_knowledge_service.retrieve_context.side_effect = Exception("Database error")

        state = {
            "question": "Test question",
            "max_symbols": 10,
        }

        result = qa_agent._retrieve_context(state)

        assert "error" in result
        assert "Failed to retrieve context" in result["error"]
        assert result["relevant_symbols"] == []
        assert result["sources"] == []

    def test_retrieve_context_uses_default_max_symbols(
        self, qa_agent, mock_knowledge_service, sample_retrieval_context
    ):
        """Test that default max_symbols is used when not provided."""
        mock_knowledge_service.retrieve_context.return_value = sample_retrieval_context

        state = {"question": "Test question"}

        qa_agent._retrieve_context(state)

        mock_knowledge_service.retrieve_context.assert_called_once_with("Test question", 10)


# Test: Node - build_prompt
class TestBuildPromptNode:
    """Tests for the build_prompt node."""

    def test_build_prompt_success(self, qa_agent, sample_retrieval_context):
        """Test successful prompt building."""
        state = {
            "question": "How does calculate_sum work?",
            "context": sample_retrieval_context,
            "include_dependencies": True,
        }

        result = qa_agent._build_prompt(state)

        assert "prompt" in result
        assert "calculate_sum" in result["prompt"]
        assert "Calculator" in result["prompt"]
        assert "How does calculate_sum work?" in result["prompt"]
        assert "error" not in result

    def test_build_prompt_without_dependencies(self, qa_agent, sample_retrieval_context):
        """Test prompt building without dependencies."""
        state = {
            "question": "Test question",
            "context": sample_retrieval_context,
            "include_dependencies": False,
        }

        result = qa_agent._build_prompt(state)

        assert "prompt" in result
        # Should not include expanded symbols section
        assert "Related Symbols" not in result["prompt"]

    def test_build_prompt_skips_on_error(self, qa_agent):
        """Test that prompt building is skipped if there's an error."""
        state = {
            "question": "Test question",
            "error": "Previous error",
        }

        result = qa_agent._build_prompt(state)

        assert result["error"] == "Previous error"
        assert "prompt" not in result

    def test_build_prompt_handles_missing_context(self, qa_agent):
        """Test error handling when context is missing."""
        state = {
            "question": "Test question",
            "context": None,
        }

        result = qa_agent._build_prompt(state)

        assert "error" in result
        assert "No context available" in result["error"]


# Test: Node - generate_answer
class TestGenerateAnswerNode:
    """Tests for the generate_answer node."""

    def test_generate_answer_success(self, qa_agent, mock_ollama_client):
        """Test successful answer generation."""
        mock_ollama_client.chat.return_value = {
            "message": {"content": "This is the answer to your question."}
        }

        state = {
            "prompt": "Test prompt",
        }

        result = qa_agent._generate_answer(state)

        assert result["answer_text"] == "This is the answer to your question."
        assert "error" not in result
        mock_ollama_client.chat.assert_called_once()

    def test_generate_answer_handles_llm_error(self, qa_agent, mock_ollama_client):
        """Test error handling when LLM fails."""
        mock_ollama_client.chat.side_effect = Exception("LLM connection error")

        state = {
            "prompt": "Test prompt",
        }

        result = qa_agent._generate_answer(state)

        assert "Error generating answer" in result["answer_text"]
        assert "error" in result

    def test_generate_answer_returns_error_on_previous_error(self, qa_agent):
        """Test that answer generation returns error if previous step failed."""
        state = {
            "error": "Previous error occurred",
            "prompt": "Test prompt",
        }

        result = qa_agent._generate_answer(state)

        assert "Error: Previous error occurred" in result["answer_text"]


# Test: Node - assess_confidence
class TestAssessConfidenceNode:
    """Tests for the assess_confidence node."""

    def test_assess_confidence_high(self, qa_agent, sample_symbols):
        """Test high confidence assessment (70%+ documented)."""
        context = RetrievalContext(
            primary_symbols=sample_symbols[:2],  # Both have docstrings
            expanded_symbols=[],
            related_files=[],
        )

        state = {"context": context}

        result = qa_agent._assess_confidence(state)

        assert result["confidence"] == "high"

    def test_assess_confidence_medium(self, qa_agent, sample_symbols):
        """Test medium confidence assessment (30-70% documented)."""
        context = RetrievalContext(
            primary_symbols=[sample_symbols[0], sample_symbols[2]],  # 50% documented
            expanded_symbols=[],
            related_files=[],
        )

        state = {"context": context}

        result = qa_agent._assess_confidence(state)

        assert result["confidence"] == "medium"

    def test_assess_confidence_low(self, qa_agent, sample_symbols):
        """Test low confidence assessment (<30% documented)."""
        context = RetrievalContext(
            primary_symbols=[sample_symbols[2]],  # No docstring
            expanded_symbols=[],
            related_files=[],
        )

        state = {"context": context}

        result = qa_agent._assess_confidence(state)

        assert result["confidence"] == "low"

    def test_assess_confidence_no_context(self, qa_agent):
        """Test low confidence when no context is available."""
        state = {"context": None}

        result = qa_agent._assess_confidence(state)

        assert result["confidence"] == "low"


# Test: Public API - answer_question
class TestAnswerQuestion:
    """Tests for the answer_question public API."""

    def test_answer_question_full_workflow(
        self, qa_agent, mock_knowledge_service, mock_ollama_client, sample_retrieval_context
    ):
        """Test the complete workflow through answer_question."""
        mock_knowledge_service.retrieve_context.return_value = sample_retrieval_context
        mock_ollama_client.chat.return_value = {
            "message": {"content": "The calculate_sum function adds two numbers together."}
        }

        # Mock the graph.invoke to return a proper state dict
        mock_final_state = {
            "question": "How does calculate_sum work?",
            "answer_text": "The calculate_sum function adds two numbers together.",
            "relevant_symbols": sample_retrieval_context.primary_symbols,
            "confidence": "high",
            "sources": list(sample_retrieval_context.related_files),
        }
        qa_agent.graph.invoke = Mock(return_value=mock_final_state)

        answer = qa_agent.answer_question("How does calculate_sum work?", max_symbols=5)

        assert isinstance(answer, Answer)
        assert answer.question == "How does calculate_sum work?"
        assert "calculate_sum" in answer.answer.lower()
        assert len(answer.relevant_symbols) == 2
        assert answer.confidence in ["high", "medium", "low"]
        assert len(answer.sources) == 2

    def test_answer_question_with_custom_parameters(
        self, qa_agent, mock_knowledge_service, mock_ollama_client, sample_retrieval_context
    ):
        """Test answer_question with custom parameters."""
        mock_knowledge_service.retrieve_context.return_value = sample_retrieval_context
        mock_ollama_client.chat.return_value = {"message": {"content": "Test answer"}}

        # Mock the graph.invoke to return a proper state dict
        mock_final_state = {
            "question": "Test question",
            "answer_text": "Test answer",
            "relevant_symbols": sample_retrieval_context.primary_symbols,
            "confidence": "medium",
            "sources": list(sample_retrieval_context.related_files),
        }
        qa_agent.graph.invoke = Mock(return_value=mock_final_state)

        answer = qa_agent.answer_question(
            "Test question",
            max_symbols=15,
            include_dependencies=False,
        )

        assert isinstance(answer, Answer)
        # Verify the graph was called with correct initial state
        qa_agent.graph.invoke.assert_called_once()
        call_args = qa_agent.graph.invoke.call_args[0][0]
        assert call_args["question"] == "Test question"
        assert call_args["max_symbols"] == 15
        assert call_args["include_dependencies"] == False


# Test: Public API - explain_symbol
class TestExplainSymbol:
    """Tests for the explain_symbol public API."""

    def test_explain_symbol_found(
        self, qa_agent, mock_knowledge_service, mock_ollama_client, sample_symbols
    ):
        """Test explaining a symbol that exists."""
        mock_knowledge_service.find_symbol.return_value = [sample_symbols[0]]
        mock_knowledge_service.find_callees.return_value = []
        mock_knowledge_service.find_callers.return_value = []
        mock_ollama_client.chat.return_value = {
            "message": {"content": "This function calculates the sum of two numbers."}
        }

        answer = qa_agent.explain_symbol("calculate_sum")

        assert isinstance(answer, Answer)
        assert "calculate_sum" in answer.question
        assert len(answer.relevant_symbols) == 1
        assert answer.relevant_symbols[0].name == "calculate_sum"
        assert answer.confidence in ["high", "medium"]

    def test_explain_symbol_not_found(self, qa_agent, mock_knowledge_service):
        """Test explaining a symbol that doesn't exist."""
        mock_knowledge_service.find_symbol.return_value = []

        answer = qa_agent.explain_symbol("nonexistent_symbol")

        assert isinstance(answer, Answer)
        assert "not found" in answer.answer.lower()
        assert answer.confidence == "low"
        assert len(answer.relevant_symbols) == 0

    def test_explain_symbol_with_relationships(
        self, qa_agent, mock_knowledge_service, mock_ollama_client, sample_symbols
    ):
        """Test explaining a symbol with callers and callees."""
        mock_knowledge_service.find_symbol.return_value = [sample_symbols[0]]
        mock_knowledge_service.find_callees.return_value = [sample_symbols[2]]
        mock_knowledge_service.find_callers.return_value = [sample_symbols[1]]
        mock_ollama_client.chat.return_value = {"message": {"content": "Detailed explanation"}}

        answer = qa_agent.explain_symbol("calculate_sum")

        assert isinstance(answer, Answer)
        # Verify that relationships were queried
        mock_knowledge_service.find_callees.assert_called_once()
        mock_knowledge_service.find_callers.assert_called_once()


# Test: Public API - find_usage
class TestFindUsage:
    """Tests for the find_usage public API."""

    def test_find_usage_with_callers(self, qa_agent, mock_knowledge_service, sample_symbols):
        """Test finding usage when symbol has callers."""
        mock_knowledge_service.find_symbol.return_value = [sample_symbols[0]]
        mock_knowledge_service.find_callers.return_value = [sample_symbols[1], sample_symbols[2]]

        answer = qa_agent.find_usage("calculate_sum")

        assert isinstance(answer, Answer)
        assert "2 location(s)" in answer.answer
        assert "Calculator" in answer.answer
        assert answer.confidence == "high"
        assert len(answer.relevant_symbols) == 3  # Original + 2 callers

    def test_find_usage_no_callers(self, qa_agent, mock_knowledge_service, sample_symbols):
        """Test finding usage when symbol has no callers."""
        mock_knowledge_service.find_symbol.return_value = [sample_symbols[0]]
        mock_knowledge_service.find_callers.return_value = []

        answer = qa_agent.find_usage("calculate_sum")

        assert isinstance(answer, Answer)
        assert "not called" in answer.answer.lower()
        assert answer.confidence == "high"

    def test_find_usage_symbol_not_found(self, qa_agent, mock_knowledge_service):
        """Test finding usage for non-existent symbol."""
        mock_knowledge_service.find_symbol.return_value = []

        answer = qa_agent.find_usage("nonexistent_symbol")

        assert isinstance(answer, Answer)
        assert "not found" in answer.answer.lower()
        assert answer.confidence == "low"

    def test_find_usage_limits_results(self, qa_agent, mock_knowledge_service, sample_symbols):
        """Test that find_usage limits results to 10 callers."""
        mock_knowledge_service.find_symbol.return_value = [sample_symbols[0]]
        # Create 15 mock callers
        many_callers = [
            Symbol(
                id=f"caller{i}",
                name=f"caller_{i}",
                type=SymbolType.FUNCTION,
                file_path=f"src/file{i}.py",
                start_line=i + 1,  # start_line must be >= 1
                end_line=i + 6,
                language="python",
            )
            for i in range(15)
        ]
        mock_knowledge_service.find_callers.return_value = many_callers

        answer = qa_agent.find_usage("calculate_sum")

        assert "15 location(s)" in answer.answer
        assert "... and 5 more locations" in answer.answer
        assert len(answer.relevant_symbols) == 11  # Original + 10 callers


# Test: Error Handling and Edge Cases
class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_workflow_continues_after_retrieval_error(
        self, qa_agent, mock_knowledge_service, mock_ollama_client
    ):
        """Test that workflow handles retrieval errors gracefully."""
        mock_knowledge_service.retrieve_context.side_effect = Exception("Retrieval failed")
        mock_ollama_client.chat.return_value = {"message": {"content": "Error response"}}

        # Mock the graph to return error state
        mock_final_state = {
            "question": "Test question",
            "answer_text": "Error: Failed to retrieve context: Retrieval failed",
            "relevant_symbols": [],
            "confidence": "low",
            "sources": [],
            "error": "Failed to retrieve context: Retrieval failed",
        }
        qa_agent.graph.invoke = Mock(return_value=mock_final_state)

        answer = qa_agent.answer_question("Test question")

        assert isinstance(answer, Answer)
        assert answer.confidence == "low"

    def test_system_prompt_is_used(self, qa_agent, mock_ollama_client):
        """Test that the system prompt is included in LLM calls."""
        mock_ollama_client.chat.return_value = {"message": {"content": "Test answer"}}

        state = {"prompt": "Test prompt"}
        qa_agent._generate_answer(state)

        call_args = mock_ollama_client.chat.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "code analysis assistant" in messages[0]["content"].lower()


# Test: Backward Compatibility
class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with original API."""

    def test_initialization_with_default_model(self, mock_knowledge_service):
        """Test that agent can be initialized with default model."""
        with patch("maris.agents.qa_agent.ollama.Client"):
            agent = QAAgent(knowledge_service=mock_knowledge_service)
            assert agent.model == "qwen2.5:7b"

    def test_initialization_with_custom_model(self, mock_knowledge_service):
        """Test that agent can be initialized with custom model."""
        with patch("maris.agents.qa_agent.ollama.Client"):
            agent = QAAgent(knowledge_service=mock_knowledge_service, model="llama2")
            assert agent.model == "llama2"

    def test_initialization_with_custom_host(self, mock_knowledge_service):
        """Test that agent can be initialized with custom Ollama host."""
        with patch("maris.agents.qa_agent.ollama.Client") as mock_client:
            QAAgent(
                knowledge_service=mock_knowledge_service,
                host="http://custom-host:11434",
            )
            mock_client.assert_called_once_with(host="http://custom-host:11434")


# Made with Bob
