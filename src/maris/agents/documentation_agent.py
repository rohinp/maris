"""Documentation Agent - generates repository documentation from indexed knowledge."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

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
    Agent responsible for generating repository documentation.

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
        logger.info("Initialized DocumentationAgent")

    def generate_module_documentation(self, file_path: str) -> ModuleDocumentation:
        """
        Generate documentation for a specific module/file.

        Args:
            file_path: Path to the file to document

        Returns:
            Structured module documentation
        """
        logger.info(f"Generating documentation for: {file_path}")

        # Get all symbols in the file
        symbols = self.knowledge_service.find_symbols_in_file(file_path)

        if not symbols:
            return ModuleDocumentation(
                file_path=file_path,
                language="unknown",
                summary="No symbols found in this file.",
                classes=[],
                functions=[],
                constants=[],
                dependencies=[],
            )

        # Categorize symbols
        classes = []
        functions = []
        constants = []
        language = symbols[0].language if symbols else "unknown"

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

        # Find dependencies (files that this file depends on)
        dependencies = self._find_file_dependencies(symbols)

        # Generate summary
        summary = self._generate_file_summary(file_path, classes, functions, constants)

        return ModuleDocumentation(
            file_path=file_path,
            language=language,
            summary=summary,
            classes=classes,
            functions=functions,
            constants=constants,
            dependencies=dependencies,
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
        doc = self.generate_module_documentation(file_path)

        lines = [
            f"# {file_path}",
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
            lines.extend(
                [
                    "## Classes",
                    "",
                ]
            )
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
            lines.extend(
                [
                    "## Functions",
                    "",
                ]
            )
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
            lines.extend(
                [
                    "## Constants",
                    "",
                ]
            )
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
            lines.extend(
                [
                    "## Key Modules",
                    "",
                ]
            )
            for module in overview.key_modules:
                lines.append(f"- `{module}`")
            lines.append("")

        return "\n".join(lines)

    def _find_file_dependencies(self, symbols: List[Symbol]) -> List[str]:
        """
        Find files that the given symbols depend on.

        Args:
            symbols: List of symbols in a file

        Returns:
            List of file paths that are dependencies
        """
        dependencies = set()

        for symbol in symbols:
            # Find callees (symbols this symbol calls)
            callees = self.knowledge_service.find_callees(symbol)

            for callee in callees:
                if callee.file_path != symbol.file_path:
                    dependencies.add(callee.file_path)

        return sorted(list(dependencies))

    def _generate_file_summary(
        self,
        file_path: str,
        classes: List[Dict],
        functions: List[Dict],
        constants: List[Dict],
    ) -> str:
        """
        Generate a summary description for a file.

        Args:
            file_path: Path to the file
            classes: List of class documentation entries
            functions: List of function documentation entries
            constants: List of constant documentation entries

        Returns:
            Summary text
        """
        parts = []

        if classes:
            parts.append(f"{len(classes)} class{'es' if len(classes) != 1 else ''}")
        if functions:
            parts.append(f"{len(functions)} function{'s' if len(functions) != 1 else ''}")
        if constants:
            parts.append(f"{len(constants)} constant{'s' if len(constants) != 1 else ''}")

        if not parts:
            return "This file contains no documented symbols."

        return f"This module defines {', '.join(parts)}."


# Made with Bob
