"""Q&A Agent - LangGraph-based implementation for answering questions about repository code."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import ollama
from langgraph.graph import StateGraph, END

from maris.core.models import RetrievalContext, Symbol
from maris.knowledge.service import RepositoryKnowledgeService

logger = logging.getLogger(__name__)


@dataclass
class Answer:
    """Structured answer to a repository question."""

    question: str
    answer: str
    relevant_symbols: List[Symbol]
    confidence: str  # "high", "medium", "low"
    sources: List[str]  # File paths referenced


class QAAgent:
    """
    LangGraph-based Q&A Agent for answering questions about repository code.

    Uses a retrieval-augmented generation (RAG) approach with explicit workflow:
    1. Retrieve relevant context using vector search + graph expansion
    2. Build a structured prompt with code context
    3. Use local LLM (via Ollama) to generate grounded answers
    4. Assess confidence based on context quality

    Capabilities:
    - Answer "what" questions (what does X do?)
    - Answer "how" questions (how does X work?)
    - Answer "where" questions (where is X used?)
    - Explain code behavior and relationships
    """

    def __init__(
        self,
        knowledge_service: RepositoryKnowledgeService,
        model: str = "qwen2.5:7b",
        host: Optional[str] = None,
    ):
        """
        Initialize the Q&A agent.

        Args:
            knowledge_service: Repository knowledge service for retrieval
            model: Ollama model to use for reasoning (default: qwen2.5:7b)
            host: Optional Ollama host URL
        """
        self.knowledge_service = knowledge_service
        self.model = model
        self.client = ollama.Client(host=host) if host else ollama.Client()

        # Build the LangGraph workflow
        self.graph = self._build_graph()

        logger.info(f"Initialized QAAgent with LangGraph and model: {model}")

    def _build_graph(self) -> Any:
        """Build the LangGraph workflow for Q&A."""
        # Use dict directly as state schema (LangGraph supports this)
        workflow = StateGraph(dict)

        # Add nodes
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("build_prompt", self._build_prompt)
        workflow.add_node("generate_answer", self._generate_answer)
        workflow.add_node("assess_confidence", self._assess_confidence)

        # Define edges
        workflow.set_entry_point("retrieve_context")
        workflow.add_edge("retrieve_context", "build_prompt")
        workflow.add_edge("build_prompt", "generate_answer")
        workflow.add_edge("generate_answer", "assess_confidence")
        workflow.add_edge("assess_confidence", END)

        return workflow.compile()

    def _retrieve_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Retrieve relevant context from the knowledge service.

        Args:
            state: Current workflow state

        Returns:
            Updated state with retrieval context
        """
        try:
            logger.info(f"Retrieving context for: {state['question']}")
            context = self.knowledge_service.retrieve_context(
                state["question"], state.get("max_symbols", 10)
            )

            state["context"] = context
            state["relevant_symbols"] = context.primary_symbols
            state["sources"] = list(context.related_files)

            logger.info(f"Retrieved {len(context.primary_symbols)} primary symbols")

        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            state["error"] = f"Failed to retrieve context: {str(e)}"
            state["context"] = RetrievalContext()
            state["relevant_symbols"] = []
            state["sources"] = []

        return state

    def _build_prompt(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Build the prompt for the LLM with retrieved context.

        Args:
            state: Current workflow state

        Returns:
            Updated state with formatted prompt
        """
        if state.get("error"):
            return state

        try:
            context = state.get("context")
            if not context:
                state["error"] = "No context available"
                return state

            question = state["question"]
            include_dependencies = state.get("include_dependencies", True)

            prompt_parts = [
                "You are a code analysis assistant. Answer the following question based on the provided code context.",
                "",
                "# Code Context",
                "",
            ]

            # Add primary symbols
            if context.primary_symbols:
                prompt_parts.append("## Relevant Symbols")
                prompt_parts.append("")

                for symbol in context.primary_symbols:
                    prompt_parts.append(f"### {symbol.name} ({symbol.type.value})")
                    prompt_parts.append(f"File: {symbol.file_path}:{symbol.start_line}")

                    if symbol.signature:
                        prompt_parts.append(f"Signature: `{symbol.signature}`")

                    if symbol.docstring:
                        prompt_parts.append(f"Documentation: {symbol.docstring}")

                    prompt_parts.append("")

            # Add expanded symbols if requested
            if include_dependencies and context.expanded_symbols:
                prompt_parts.append("## Related Symbols")
                prompt_parts.append("")

                for symbol in context.expanded_symbols[:5]:  # Limit to 5
                    prompt_parts.append(
                        f"- {symbol.name} ({symbol.type.value}) in {symbol.file_path}"
                    )

                prompt_parts.append("")

            # Add the question
            prompt_parts.extend(
                [
                    "# Question",
                    "",
                    question,
                    "",
                    "# Instructions",
                    "",
                    "Provide a clear, accurate answer based on the code context above. If the context doesn't contain enough information, say so.",
                ]
            )

            state["prompt"] = "\n".join(prompt_parts)
            logger.info("Built prompt for LLM")

        except Exception as e:
            logger.error(f"Error building prompt: {e}")
            state["error"] = f"Failed to build prompt: {str(e)}"

        return state

    def _generate_answer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Generate answer using the LLM.

        Args:
            state: Current workflow state

        Returns:
            Updated state with generated answer
        """
        if state.get("error"):
            state["answer_text"] = f"Error: {state['error']}"
            return state

        try:
            logger.info("Generating answer with LLM")

            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": state["prompt"],
                    },
                ],
            )

            state["answer_text"] = response["message"]["content"]
            logger.info("Answer generated successfully")

        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            state["answer_text"] = f"Error generating answer: {str(e)}"
            state["error"] = str(e)

        return state

    def _assess_confidence(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Assess confidence level based on retrieved context.

        Args:
            state: Current workflow state

        Returns:
            Updated state with confidence assessment
        """
        context = state.get("context")

        if not context or not context.primary_symbols:
            state["confidence"] = "low"
            return state

        # High confidence if we have symbols with documentation
        documented_symbols = sum(1 for s in context.primary_symbols if s.docstring)

        if documented_symbols >= len(context.primary_symbols) * 0.7:
            state["confidence"] = "high"
        elif documented_symbols >= len(context.primary_symbols) * 0.3:
            state["confidence"] = "medium"
        else:
            state["confidence"] = "low"

        logger.info(f"Confidence assessed as: {state['confidence']}")
        return state

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the LLM."""
        return """You are an expert code analysis assistant. Your role is to help developers understand codebases by answering questions based on retrieved code context.

Guidelines:
- Be accurate and precise
- Reference specific symbols, files, and line numbers when relevant
- If the context is insufficient, acknowledge it
- Explain technical concepts clearly
- Focus on what the code does, not what it should do"""

    def answer_question(
        self,
        question: str,
        max_symbols: int = 10,
        include_dependencies: bool = True,
    ) -> Answer:
        """
        Answer a question about the repository.

        Args:
            question: Natural language question
            max_symbols: Maximum number of symbols to retrieve
            include_dependencies: Whether to include related symbols

        Returns:
            Structured answer with sources
        """
        logger.info(f"Answering question: {question}")

        # Initialize state
        initial_state: Dict[str, Any] = {
            "question": question,
            "max_symbols": max_symbols,
            "include_dependencies": include_dependencies,
            "context": None,
            "prompt": None,
            "answer_text": None,
            "confidence": None,
            "sources": [],
            "relevant_symbols": [],
            "error": None,
        }

        # Run the workflow
        final_state = self.graph.invoke(initial_state)

        # Build and return answer
        return Answer(
            question=question,
            answer=final_state.get("answer_text") or "No answer generated",
            relevant_symbols=final_state.get("relevant_symbols", []),
            confidence=final_state.get("confidence") or "low",
            sources=final_state.get("sources", []),
        )

    def explain_symbol(self, symbol_name: str, language: Optional[str] = None) -> Answer:
        """
        Explain what a specific symbol does.

        Args:
            symbol_name: Name of the symbol to explain
            language: Optional language filter

        Returns:
            Detailed explanation of the symbol
        """
        question = f"Explain what {symbol_name} does and how it works."

        # Find the symbol
        symbols = self.knowledge_service.find_symbol(symbol_name, language)

        if not symbols:
            return Answer(
                question=question,
                answer=f"Symbol '{symbol_name}' not found in the repository.",
                relevant_symbols=[],
                confidence="low",
                sources=[],
            )

        # Use the first matching symbol
        symbol = symbols[0]

        # Get related symbols
        callees = self.knowledge_service.find_callees(symbol)
        callers = self.knowledge_service.find_callers(symbol)

        # Build detailed context
        context_parts = [
            f"Symbol: {symbol.name}",
            f"Type: {symbol.type.value}",
            f"File: {symbol.file_path}",
            f"Lines: {symbol.start_line}-{symbol.end_line}",
        ]

        if symbol.signature:
            context_parts.append(f"Signature: {symbol.signature}")

        if symbol.docstring:
            context_parts.append(f"Documentation: {symbol.docstring}")

        if callees:
            context_parts.append(f"Calls: {', '.join(c.name for c in callees[:5])}")

        if callers:
            context_parts.append(f"Called by: {', '.join(c.name for c in callers[:5])}")

        context_text = "\n".join(context_parts)

        # Generate explanation
        prompt = f"""Based on the following information about a code symbol, provide a clear explanation of what it does and how it works:

{context_text}

Question: {question}

Provide a detailed but concise explanation."""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )

            answer_text = response["message"]["content"]

        except Exception as e:
            logger.error(f"Failed to generate explanation: {e}")
            answer_text = f"Error generating explanation: {str(e)}"

        return Answer(
            question=question,
            answer=answer_text,
            relevant_symbols=[symbol],
            confidence="high" if symbol.docstring else "medium",
            sources=[symbol.file_path],
        )

    def find_usage(self, symbol_name: str) -> Answer:
        """
        Find where a symbol is used in the codebase.

        Args:
            symbol_name: Name of the symbol to find usage for

        Returns:
            Answer describing where and how the symbol is used
        """
        question = f"Where is {symbol_name} used?"

        # Find the symbol
        symbols = self.knowledge_service.find_symbol(symbol_name)

        if not symbols:
            return Answer(
                question=question,
                answer=f"Symbol '{symbol_name}' not found in the repository.",
                relevant_symbols=[],
                confidence="low",
                sources=[],
            )

        symbol = symbols[0]

        # Find callers
        callers = self.knowledge_service.find_callers(symbol)

        if not callers:
            answer_text = f"'{symbol_name}' is defined in {symbol.file_path} but is not called by any other symbols in the indexed codebase."
        else:
            caller_info = []
            for caller in callers[:10]:  # Limit to 10 callers
                caller_info.append(f"- {caller.name} in {caller.file_path}:{caller.start_line}")

            answer_text = f"'{symbol_name}' is used in {len(callers)} location(s):\n\n" + "\n".join(
                caller_info
            )

            if len(callers) > 10:
                answer_text += f"\n\n... and {len(callers) - 10} more locations."

        return Answer(
            question=question,
            answer=answer_text,
            relevant_symbols=[symbol] + callers[:10],
            confidence="high",
            sources=list(set([symbol.file_path] + [c.file_path for c in callers])),
        )


# Made with Bob
