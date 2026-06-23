"""Documentation Agent - LangGraph-based implementation for generating repository documentation."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from langgraph.graph import StateGraph, END

from maris.core.models import Symbol, SymbolType
from maris.knowledge.service import RepositoryKnowledgeService

logger = logging.getLogger(__name__)


@dataclass
class ModuleDocumentation:
    """Documentation for a single module/file."""

    file_path: str
    language: str
    summary: str
    classes: List[Dict[str, str]]
    functions: List[Dict[str, str]]
    constants: List[Dict[str, str]]
    dependencies: List[str]


@dataclass
class ArchitectureOverview:
    """High-level architecture documentation."""

    total_files: int
    total_symbols: int
    languages: List[str]
    key_modules: List[str]
    dependency_graph_summary: str


class DocumentationAgent:
    """
    LangGraph-based Agent for generating repository documentation.

    Uses a workflow with explicit state management:
    1. retrieve_symbols: Get symbols from the file
    2. categorize_symbols: Organize symbols by type
    3. find_dependencies: Find file dependencies
    4. generate_summary: Create file summary
    5. format_output: Format as ModuleDocumentation or Markdown

    Capabilities:
    - Generate module-level documentation
    - Create architecture overviews
    - Document component relationships
    - Generate dependency diagrams (text-based)
    """

    def __init__(self, knowledge_service: RepositoryKnowledgeService):
        """
        Initialize the documentation agent.

        Args:
            knowledge_service: Repository knowledge service for data access
        """
        self.knowledge_service = knowledge_service

        # Build the LangGraph workflow
        self.graph = self._build_graph()

        logger.info("Initialized DocumentationAgent with LangGraph")

    def _build_graph(self) -> Any:
        """Build the LangGraph workflow for documentation generation."""

        # Define state schema
        class State(Dict[str, Any]):
            pass

        workflow = StateGraph(State)

        # Add nodes
        workflow.add_node("retrieve_symbols", self._retrieve_symbols)
        workflow.add_node("categorize_symbols", self._categorize_symbols)
        workflow.add_node("find_dependencies", self._find_dependencies)
        workflow.add_node("generate_summary", self._generate_summary)
        workflow.add_node("format_output", self._format_output)

        # Define edges
        workflow.set_entry_point("retrieve_symbols")
        workflow.add_edge("retrieve_symbols", "categorize_symbols")
        workflow.add_edge("categorize_symbols", "find_dependencies")
        workflow.add_edge("find_dependencies", "generate_summary")
        workflow.add_edge("generate_summary", "format_output")
        workflow.add_edge("format_output", END)

        return workflow.compile()

    def _retrieve_symbols(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Retrieve symbols from the file.

        Args:
            state: Current workflow state

        Returns:
            Updated state with symbols
        """
        try:
            file_path = state.get("file_path", "")
            if not file_path:
                raise ValueError("file_path is required")
            logger.info(f"Retrieving symbols for: {file_path}")

            symbols = self.knowledge_service.find_symbols_in_file(file_path)

            state["symbols"] = symbols
            state["language"] = symbols[0].language if symbols else "unknown"

            logger.info(f"Retrieved {len(symbols)} symbols")

        except Exception as e:
            logger.error(f"Error retrieving symbols: {e}")
            state["error"] = f"Failed to retrieve symbols: {str(e)}"
            state["symbols"] = []
            state["language"] = "unknown"

        return state

    def _categorize_symbols(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Categorize symbols by type.

        Args:
            state: Current workflow state

        Returns:
            Updated state with categorized symbols
        """
        if state.get("error"):
            return state

        try:
            logger.info("Categorizing symbols")

            symbols = state.get("symbols", [])
            classes = []
            functions = []
            constants = []

            for symbol in symbols:
                doc_entry = {
                    "name": symbol.name,
                    "signature": symbol.signature or "",
                    "docstring": symbol.docstring or "No documentation available.",
                    "line": symbol.start_line,
                }

                if symbol.type == SymbolType.CLASS:
                    # Find methods of this class
                    methods = [s for s in symbols if s.parent_id == symbol.id]
                    doc_entry["methods"] = [m.name for m in methods]
                    classes.append(doc_entry)
                elif symbol.type == SymbolType.FUNCTION and not symbol.parent_id:
                    functions.append(doc_entry)
                elif symbol.type == SymbolType.CONSTANT:
                    constants.append(doc_entry)

            state["classes"] = classes
            state["functions"] = functions
            state["constants"] = constants

            logger.info(
                f"Categorized: {len(classes)} classes, {len(functions)} functions, {len(constants)} constants"
            )

        except Exception as e:
            logger.error(f"Error categorizing symbols: {e}")
            state["error"] = f"Failed to categorize symbols: {str(e)}"
            state["classes"] = []
            state["functions"] = []
            state["constants"] = []

        return state

    def _find_dependencies(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Find file dependencies.

        Args:
            state: Current workflow state

        Returns:
            Updated state with dependencies
        """
        if state.get("error"):
            return state

        try:
            logger.info("Finding dependencies")

            symbols = state.get("symbols", [])
            dependencies = set()

            for symbol in symbols:
                # Find callees (symbols this symbol calls)
                callees = self.knowledge_service.find_callees(symbol)

                for callee in callees:
                    if callee.file_path != symbol.file_path:
                        dependencies.add(callee.file_path)

            state["dependencies"] = sorted(list(dependencies))

            logger.info(f"Found {len(dependencies)} dependencies")

        except Exception as e:
            logger.error(f"Error finding dependencies: {e}")
            # Don't fail the workflow for dependency errors
            state["dependencies"] = []
            state["dependency_error"] = str(e)

        return state

    def _generate_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Generate file summary.

        Args:
            state: Current workflow state

        Returns:
            Updated state with summary
        """
        if state.get("error"):
            return state

        try:
            logger.info("Generating summary")

            classes = state.get("classes", [])
            functions = state.get("functions", [])
            constants = state.get("constants", [])

            parts = []
            if classes:
                parts.append(f"{len(classes)} class{'es' if len(classes) != 1 else ''}")
            if functions:
                parts.append(f"{len(functions)} function{'s' if len(functions) != 1 else ''}")
            if constants:
                parts.append(f"{len(constants)} constant{'s' if len(constants) != 1 else ''}")

            if not parts:
                summary = "This file contains no documented symbols."
            else:
                summary = f"This module defines {', '.join(parts)}."

            state["summary"] = summary

            logger.info("Summary generated")

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            state["summary"] = "Error generating summary."

        return state

    def _format_output(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node: Format output as ModuleDocumentation or Markdown.

        Args:
            state: Current workflow state

        Returns:
            Updated state with formatted output
        """
        try:
            logger.info("Formatting output")

            file_path = state.get("file_path", "unknown")
            language = state.get("language", "unknown")
            summary = state.get("summary", "No summary available.")
            classes = state.get("classes", [])
            functions = state.get("functions", [])
            constants = state.get("constants", [])
            dependencies = state.get("dependencies", [])

            # Create ModuleDocumentation object
            doc = ModuleDocumentation(
                file_path=file_path,
                language=language,
                summary=summary,
                classes=classes,
                functions=functions,
                constants=constants,
                dependencies=dependencies,
            )

            state["documentation"] = doc

            # Generate markdown if requested
            if state.get("format") == "markdown":
                state["markdown"] = self._generate_markdown(doc)

            logger.info("Output formatted")

        except Exception as e:
            logger.error(f"Error formatting output: {e}")
            state["error"] = f"Failed to format output: {str(e)}"

        return state

    def _generate_markdown(self, doc: ModuleDocumentation) -> str:
        """
        Generate Markdown documentation from ModuleDocumentation.

        Args:
            doc: Module documentation object

        Returns:
            Markdown-formatted documentation
        """
        lines = [
            f"# {doc.file_path}",
            "",
            f"**Language:** {doc.language}",
            "",
            "## Summary",
            "",
            doc.summary,
            "",
        ]

        # Document classes
        if doc.classes:
            lines.extend(["## Classes", ""])
            for cls in doc.classes:
                lines.append(f"### `{cls['name']}`")
                lines.append("")
                if cls.get("signature"):
                    lines.append(f"```{doc.language}")
                    lines.append(cls["signature"])
                    lines.append("```")
                    lines.append("")
                lines.append(cls["docstring"])
                lines.append("")
                if cls.get("methods"):
                    lines.append("**Methods:**")
                    for method in cls["methods"]:
                        lines.append(f"- `{method}()`")
                    lines.append("")

        # Document functions
        if doc.functions:
            lines.extend(["## Functions", ""])
            for func in doc.functions:
                lines.append(f"### `{func['name']}()`")
                lines.append("")
                if func.get("signature"):
                    lines.append(f"```{doc.language}")
                    lines.append(func["signature"])
                    lines.append("```")
                    lines.append("")
                lines.append(func["docstring"])
                lines.append("")

        # Document constants
        if doc.constants:
            lines.extend(["## Constants", ""])
            for const in doc.constants:
                lines.append(f"- **`{const['name']}`**: {const['docstring']}")
            lines.append("")

        # Document dependencies
        if doc.dependencies:
            lines.extend(
                [
                    "## Dependencies",
                    "",
                    "This module depends on:",
                    "",
                ]
            )
            for dep in doc.dependencies:
                lines.append(f"- `{dep}`")
            lines.append("")

        return "\n".join(lines)

    def generate_module_documentation(self, file_path: str) -> ModuleDocumentation:
        """
        Generate documentation for a specific module/file.

        Args:
            file_path: Path to the file to document

        Returns:
            Structured module documentation
        """
        logger.info(f"Generating documentation for: {file_path}")

        # Initialize state
        initial_state: Dict[str, Any] = {
            "file_path": file_path,
            "format": "object",
            "symbols": [],
            "language": "unknown",
            "classes": [],
            "functions": [],
            "constants": [],
            "dependencies": [],
            "summary": "",
            "documentation": None,
            "error": None,
        }

        # Run the workflow
        final_state = self.graph.invoke(initial_state)

        # Handle None return from graph
        if final_state is None:
            final_state = initial_state

        # Return documentation or create empty one
        if final_state.get("documentation"):
            return final_state["documentation"]
        else:
            return ModuleDocumentation(
                file_path=file_path,
                language="unknown",
                summary="No symbols found in this file.",
                classes=[],
                functions=[],
                constants=[],
                dependencies=[],
            )

    def generate_architecture_overview(self) -> ArchitectureOverview:
        """
        Generate high-level architecture documentation.

        Returns:
            Architecture overview with statistics and key insights
        """
        logger.info("Generating architecture overview")

        # Get repository statistics
        stats = self.knowledge_service.get_repository_stats()

        total_files = stats.get("total_files", 0)
        total_symbols = stats.get("total_symbols", 0)
        languages = stats.get("languages", [])

        # Identify key modules (files with most symbols)
        # This is a simplified version - in production, we'd query the metadata store
        key_modules = []

        # Generate dependency graph summary
        dep_summary = f"Repository contains {total_symbols} symbols across {total_files} files."

        return ArchitectureOverview(
            total_files=total_files,
            total_symbols=total_symbols,
            languages=languages,
            key_modules=key_modules,
            dependency_graph_summary=dep_summary,
        )

    def generate_markdown_documentation(self, file_path: str) -> str:
        """
        Generate Markdown documentation for a file.

        Args:
            file_path: Path to the file to document

        Returns:
            Markdown-formatted documentation
        """
        logger.info(f"Generating markdown documentation for: {file_path}")

        # Initialize state
        initial_state: Dict[str, Any] = {
            "file_path": file_path,
            "format": "markdown",
            "symbols": [],
            "language": "unknown",
            "classes": [],
            "functions": [],
            "constants": [],
            "dependencies": [],
            "summary": "",
            "documentation": None,
            "markdown": None,
            "error": None,
        }

        # Run the workflow
        final_state = self.graph.invoke(initial_state)

        # Handle None return from graph
        if final_state is None:
            final_state = initial_state

        # Return markdown or generate from documentation
        if final_state.get("markdown"):
            return final_state["markdown"]
        elif final_state.get("documentation"):
            return self._generate_markdown(final_state["documentation"])
        else:
            # Return minimal markdown
            return f"# {file_path}\n\nNo symbols found in this file.\n"

    def generate_architecture_markdown(self) -> str:
        """
        Generate Markdown documentation for repository architecture.

        Returns:
            Markdown-formatted architecture overview
        """
        overview = self.generate_architecture_overview()

        lines = [
            "# Repository Architecture",
            "",
            "## Overview",
            "",
            f"- **Total Files:** {overview.total_files}",
            f"- **Total Symbols:** {overview.total_symbols}",
            f"- **Languages:** {', '.join(overview.languages)}",
            "",
            "## Dependency Graph",
            "",
            overview.dependency_graph_summary,
            "",
        ]

        if overview.key_modules:
            lines.extend(["## Key Modules", ""])
            for module in overview.key_modules:
                lines.append(f"- `{module}`")
            lines.append("")

        return "\n".join(lines)


# Made with Bob
