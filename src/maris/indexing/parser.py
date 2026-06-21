"""Base Tree-sitter parser for extracting symbols from source code."""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

import tree_sitter

from maris.core.models import Dependency, Symbol


class TreeSitterParser(ABC):
    """
    Abstract base class for language-specific Tree-sitter parsers.

    Each language parser should inherit from this class and implement
    the abstract methods for symbol and dependency extraction.
    """

    def __init__(self, language: str):
        """
        Initialize the parser.

        Args:
            language: Programming language name (e.g., "python", "java")
        """
        self.language = language
        self.parser: Optional[tree_sitter.Parser] = None

    @abstractmethod
    def setup_parser(self) -> None:
        """
        Set up the Tree-sitter parser with the appropriate language grammar.

        This method should be implemented by each language-specific parser
        to load the correct Tree-sitter language library.
        """
        pass

    @abstractmethod
    def extract_symbols(self, tree: tree_sitter.Tree, file_path: str, content: str) -> List[Symbol]:
        """
        Extract symbols from the parsed syntax tree.

        Args:
            tree: Parsed Tree-sitter syntax tree
            file_path: Relative path to the source file
            content: Source code content

        Returns:
            List of extracted symbols
        """
        pass

    @abstractmethod
    def extract_dependencies(
        self, tree: tree_sitter.Tree, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """
        Extract dependency relationships from the syntax tree.

        Args:
            tree: Parsed Tree-sitter syntax tree
            symbols: List of symbols extracted from the file
            file_path: Relative path to the source file
            content: Source code content

        Returns:
            List of dependency relationships
        """
        pass

    def parse_file(self, file_path: str, content: str) -> Optional[tree_sitter.Tree]:
        """
        Parse a source file using Tree-sitter.

        Args:
            file_path: Path to the source file
            content: Source code content

        Returns:
            Parsed syntax tree or None if parsing fails
        """
        if self.parser is None:
            self.setup_parser()

        if self.parser is None:
            return None

        try:
            tree = self.parser.parse(bytes(content, "utf8"))
            return tree
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None

    def generate_symbol_id(self, file_path: str, symbol_name: str, line: int) -> str:
        """
        Generate a unique identifier for a symbol.

        Args:
            file_path: File path
            symbol_name: Symbol name
            line: Line number

        Returns:
            Unique symbol ID (16-character hash)
        """
        content = f"{file_path}:{symbol_name}:{line}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def generate_dependency_id(self, from_symbol_id: str, to_symbol_id: str) -> str:
        """
        Generate a unique identifier for a dependency.

        Args:
            from_symbol_id: Source symbol ID
            to_symbol_id: Target symbol ID

        Returns:
            Unique dependency ID
        """
        content = f"{from_symbol_id}->{to_symbol_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_node_text(self, node: tree_sitter.Node, content: str) -> str:
        """
        Extract text content from a Tree-sitter node.

        Args:
            node: Tree-sitter node
            content: Source code content

        Returns:
            Text content of the node
        """
        return content[node.start_byte : node.end_byte]

    def get_line_number(self, node: tree_sitter.Node) -> int:
        """
        Get the line number of a Tree-sitter node (1-based).

        Args:
            node: Tree-sitter node

        Returns:
            Line number
        """
        return node.start_point[0] + 1

    def get_end_line_number(self, node: tree_sitter.Node) -> int:
        """
        Get the end line number of a Tree-sitter node (1-based).

        Args:
            node: Tree-sitter node

        Returns:
            End line number
        """
        return node.end_point[0] + 1

    def find_nodes_by_type(self, node: tree_sitter.Node, node_type: str) -> List[tree_sitter.Node]:
        """
        Recursively find all nodes of a specific type.

        Args:
            node: Root node to search from
            node_type: Type of nodes to find

        Returns:
            List of matching nodes
        """
        results = []

        if node.type == node_type:
            results.append(node)

        for child in node.children:
            results.extend(self.find_nodes_by_type(child, node_type))

        return results

    def get_docstring(self, node: tree_sitter.Node, content: str) -> Optional[str]:
        """
        Extract docstring from a node if present.

        This is a generic implementation that should be overridden
        by language-specific parsers for better accuracy.

        Args:
            node: Tree-sitter node
            content: Source code content

        Returns:
            Docstring text or None
        """
        # Generic implementation - override in language-specific parsers
        return None


# Made with Bob
