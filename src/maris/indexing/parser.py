"""Base Tree-sitter parser for extracting symbols from source code."""

import hashlib
import re
from abc import ABC, abstractmethod
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

    def body_summary_from_docstring(self, docstring: Optional[str]) -> Optional[str]:
        """
        Extract the first sentence of a docstring for use as a body summary.

        This is a static, parser-time approximation: it returns the leading
        sentence of the existing docstring/comment, not a generated summary of
        what the code actually does.  Methods with no docstring produce no
        summary.  A richer summary (e.g. LLM-generated) can be injected later
        by writing directly to ``symbol.metadata[METADATA_BODY_SUMMARY]``.

        Args:
            docstring: Raw docstring text or None

        Returns:
            First sentence of the docstring, or None if absent/empty
        """
        if not docstring:
            return None
        # Strip leading/trailing whitespace
        text = docstring.strip()
        if not text:
            return None
        # Take up to the first blank line
        first_para = text.split("\n\n")[0].replace("\n", " ").strip()
        # Take up to the first sentence-ending period followed by whitespace or end
        match = re.search(r"\.(\s|$)", first_para)
        if match:
            first_para = first_para[: match.start() + 1]
        return first_para if first_para else None

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

    def extract_calls(self, body_node: tree_sitter.Node, content: str) -> List[str]:
        """
        Extract names of called functions/methods from a body node.

        Walks the body looking for call_expression / method_invocation nodes
        and returns the de-duplicated list of callee names.  This is a generic
        best-effort implementation; language parsers may override it for
        higher accuracy.

        Args:
            body_node: The body/block node of a function or method
            content: Source code content

        Returns:
            Sorted, de-duplicated list of callee name strings
        """
        # Common call node types across languages supported by tree-sitter
        call_node_types = {
            "call_expression",      # JS/TS, Scala (some grammars)
            "method_invocation",    # Java
            "method_call",          # alternative name in some grammars
            "call",                 # Python tree-sitter grammar
            "function_call",        # fallback
        }
        seen: set = set()
        stack = [body_node]

        while stack:
            node = stack.pop()
            if node.type in call_node_types:
                # Try the "function" or "method" named field first, then fall back
                # to reading the first identifier child.
                callee_node = (
                    node.child_by_field_name("function")
                    or node.child_by_field_name("method")
                    or node.child_by_field_name("name")
                )
                if callee_node:
                    name = self.get_node_text(callee_node, content)
                    name = self._normalize_call_name(name)
                    if name:
                        seen.add(name)
            stack.extend(node.children)

        return sorted(seen)

    def _normalize_call_name(self, name: str) -> str:
        """
        Normalize a callee name while preserving useful receiver context.

        Examples:
        - ``this.reducer.reduce`` -> ``reducer.reduce``
        - ``a.b.c.deepCall`` -> ``c.deepCall``
        - ``emitEvent`` -> ``emitEvent``
        """
        parts = name.split(".")
        if len(parts) > 2:
            return ".".join(parts[-2:])
        return name

    def extract_return_type(self, node: tree_sitter.Node, content: str) -> Optional[str]:
        """
        Extract the declared return type from a function/method node.

        Looks for the "return_type" named field used by most tree-sitter
        grammars.  Returns None when no annotation is present.

        Args:
            node: Function or method definition node
            content: Source code content

        Returns:
            Return type text or None
        """
        rt_node = node.child_by_field_name("return_type")
        if rt_node:
            return self.get_node_text(rt_node, content).lstrip(":").strip()
        return None

    def build_symbol_text(self, symbol: Symbol) -> str:
        """
        Delegate to ``Symbol.to_rich_text()``.

        Provided as a convenience method on the parser so that any code
        already calling ``parser.build_symbol_text(symbol)`` continues to
        work without change.

        Args:
            symbol: Symbol to convert to text

        Returns:
            Rich text string suitable for embedding
        """
        return symbol.to_rich_text()


# Made with Bob
