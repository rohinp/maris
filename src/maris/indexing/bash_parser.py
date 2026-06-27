"""Bash-specific Tree-sitter parser for symbol extraction."""

from typing import List, Optional

import tree_sitter
import tree_sitter_bash

from maris.core.models import (
    METADATA_BODY_SUMMARY,
    METADATA_CALLS,
    METADATA_SOURCE,
    Dependency,
    Symbol,
    SymbolType,
)
from maris.indexing.parser import TreeSitterParser


class BashParser(TreeSitterParser):
    """
    Bash-specific implementation of Tree-sitter parser.

    Extracts symbols (functions) and dependencies (source statements)
    from Bash/Shell script source code.
    """

    def __init__(self):
        """Initialize the Bash parser."""
        super().__init__("bash")

    def setup_parser(self) -> None:
        """Set up the Tree-sitter parser with Bash grammar."""
        bash_language = tree_sitter.Language(tree_sitter_bash.language())
        self.parser = tree_sitter.Parser(bash_language)

    def extract_symbols(self, tree: tree_sitter.Tree, file_path: str, content: str) -> List[Symbol]:
        """
        Extract symbols from Bash source code.

        Extracts:
        - Functions

        Args:
            tree: Parsed Tree-sitter syntax tree
            file_path: Relative path to the source file
            content: Source code content

        Returns:
            List of extracted symbols
        """
        symbols = []
        root_node = tree.root_node

        # Extract functions
        function_nodes = self.find_nodes_by_type(root_node, "function_definition")
        for func_node in function_nodes:
            symbol = self._extract_function(func_node, file_path, content)
            if symbol:
                symbols.append(symbol)

        return symbols

    def extract_dependencies(
        self, tree: tree_sitter.Tree, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """
        Extract dependency relationships from Bash code.

        Extracts:
        - Source statements (. or source)
        - Function calls

        Args:
            tree: Parsed Tree-sitter syntax tree
            symbols: List of symbols extracted from the file
            file_path: Relative path to the source file
            content: Source code content

        Returns:
            List of dependency relationships
        """
        dependencies = []
        root_node = tree.root_node

        # Create a map of symbol names to IDs for quick lookup
        symbol_map = {s.name: s.id for s in symbols}

        # Extract source dependencies
        source_deps = self._extract_source_dependencies(root_node, symbols, file_path, content)
        dependencies.extend(source_deps)

        # Extract function call dependencies
        call_deps = self._extract_call_dependencies(
            root_node, symbols, symbol_map, file_path, content
        )
        dependencies.extend(call_deps)

        return dependencies

    def _extract_function(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract a function symbol."""
        # Find the function name
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        func_name = self.get_node_text(name_node, content)
        start_line = self.get_line_number(node)
        end_line = self.get_end_line_number(node)

        # Extract any comment above the function as documentation
        docstring = self._extract_bash_comment(node, content)

        # Calls + source from the function body
        body_node = node.child_by_field_name("body")
        calls: List[str] = []
        source: Optional[str] = None
        if body_node:
            calls = self.extract_calls(body_node, content)
            source = self.get_node_text(node, content)

        # Build metadata
        body_summary = self.body_summary_from_docstring(docstring)
        metadata = {}
        if calls:
            metadata[METADATA_CALLS] = calls
        if source:
            metadata[METADATA_SOURCE] = source
        if body_summary:
            metadata[METADATA_BODY_SUMMARY] = body_summary

        symbol_id = self.generate_symbol_id(file_path, func_name, start_line)

        return Symbol(
            id=symbol_id,
            name=func_name,
            type=SymbolType.FUNCTION,
            file_path=file_path,
            language=self.language,
            start_line=start_line,
            end_line=end_line,
            docstring=docstring,
            metadata=metadata,
        )

    def _extract_bash_comment(self, node: tree_sitter.Node, content: str) -> Optional[str]:
        """
        Extract comment above a function as documentation.

        Args:
            node: Function definition node
            content: Source code content

        Returns:
            Comment text or None
        """
        # Look for comment nodes immediately before this node
        if node.prev_sibling and node.prev_sibling.type == "comment":
            comment_text = self.get_node_text(node.prev_sibling, content)
            # Remove leading # and whitespace
            cleaned = comment_text.lstrip("#").strip()
            # Discard shebang lines (e.g. "!/bin/bash") — they are file-level
            # directives, not function documentation.
            if cleaned.startswith("!"):
                return None
            return cleaned if cleaned else None
        return None

    def _extract_source_dependencies(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract source/dot command dependencies."""
        dependencies = []

        # Find command nodes that might be source statements
        command_nodes = self.find_nodes_by_type(node, "command")

        for cmd_node in command_nodes:
            cmd_text = self.get_node_text(cmd_node, content).strip()

            # Check if it's a source or . command
            if cmd_text.startswith("source ") or cmd_text.startswith(". "):
                # Extract the sourced file
                parts = cmd_text.split(maxsplit=1)
                if len(parts) > 1:
                    sourced_file = parts[1].strip().strip('"').strip("'")

                    # Create a dependency for the source
                    dep_id = f"{file_path}:source:{sourced_file}"
                    dependencies.append(
                        Dependency(
                            id=dep_id,
                            from_symbol_id=file_path,
                            to_symbol_id=sourced_file,
                            relationship_type="sources",
                        )
                    )

        return dependencies

    def _extract_call_dependencies(
        self,
        node: tree_sitter.Node,
        symbols: List[Symbol],
        symbol_map: dict,
        file_path: str,
        content: str,
    ) -> List[Dependency]:
        """Extract function call dependencies within the file."""
        dependencies = []

        # Find all command nodes (potential function calls)
        command_nodes = self.find_nodes_by_type(node, "command")

        for cmd_node in command_nodes:
            # Get the command name (first word)
            if not cmd_node.children:
                continue

            first_child = cmd_node.children[0]
            if first_child.type == "command_name":
                # Get the actual name
                name_node = first_child.children[0] if first_child.children else None
                if name_node and name_node.type == "word":
                    called_name = self.get_node_text(name_node, content)

                    # Check if this is a function defined in this file
                    if called_name in symbol_map:
                        # Find which symbol contains this call
                        call_line = self.get_line_number(cmd_node)
                        from_symbol = None
                        for symbol in symbols:
                            if symbol.start_line <= call_line <= symbol.end_line:
                                from_symbol = symbol
                                break

                        if from_symbol:
                            to_symbol_id = symbol_map[called_name]
                            dep_id = f"{from_symbol.id}:calls:{to_symbol_id}"
                            dependencies.append(
                                Dependency(
                                    id=dep_id,
                                    from_symbol_id=from_symbol.id,
                                    to_symbol_id=to_symbol_id,
                                    relationship_type="calls",
                                )
                            )

        return dependencies


# Made with Bob
