"""Scala-specific Tree-sitter parser for symbol extraction."""

from typing import List, Optional

import tree_sitter
import tree_sitter_scala

from maris.core.models import Dependency, Symbol, SymbolType
from maris.indexing.parser import TreeSitterParser


class ScalaParser(TreeSitterParser):
    """
    Scala-specific implementation of Tree-sitter parser.

    Extracts symbols (classes, traits, objects, functions, values) and dependencies
    (imports, inheritance, trait mixing) from Scala source code.
    """

    def __init__(self):
        """Initialize the Scala parser."""
        super().__init__("scala")

    def setup_parser(self) -> None:
        """Set up the Tree-sitter parser with Scala grammar."""
        scala_language = tree_sitter.Language(tree_sitter_scala.language())
        self.parser = tree_sitter.Parser(scala_language)

    def extract_symbols(self, tree: tree_sitter.Tree, file_path: str, content: str) -> List[Symbol]:
        """
        Extract symbols from Scala source code.

        Extracts:
        - Classes
        - Traits
        - Objects (including companion objects)
        - Functions (def)
        - Values (val/var)

        Args:
            tree: Parsed Tree-sitter syntax tree
            file_path: Relative path to the source file
            content: Source code content

        Returns:
            List of extracted symbols
        """
        symbols = []
        root_node = tree.root_node

        # Extract classes
        class_nodes = self.find_nodes_by_type(root_node, "class_definition")
        for class_node in class_nodes:
            symbol = self._extract_class(class_node, file_path, content)
            if symbol:
                symbols.append(symbol)

                # Extract members within the class
                member_symbols = self._extract_class_members(
                    class_node, file_path, content, symbol.id
                )
                symbols.extend(member_symbols)

        # Extract traits
        trait_nodes = self.find_nodes_by_type(root_node, "trait_definition")
        for trait_node in trait_nodes:
            symbol = self._extract_trait(trait_node, file_path, content)
            if symbol:
                symbols.append(symbol)

                # Extract members within the trait
                member_symbols = self._extract_trait_members(
                    trait_node, file_path, content, symbol.id
                )
                symbols.extend(member_symbols)

        # Extract objects
        object_nodes = self.find_nodes_by_type(root_node, "object_definition")
        for object_node in object_nodes:
            symbol = self._extract_object(object_node, file_path, content)
            if symbol:
                symbols.append(symbol)

                # Extract members within the object
                member_symbols = self._extract_object_members(
                    object_node, file_path, content, symbol.id
                )
                symbols.extend(member_symbols)

        # Extract top-level functions
        function_nodes = self._find_top_level_functions(root_node)
        for func_node in function_nodes:
            symbol = self._extract_function(func_node, file_path, content)
            if symbol:
                symbols.append(symbol)

        return symbols

    def extract_dependencies(
        self, tree: tree_sitter.Tree, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """
        Extract dependency relationships from Scala code.

        Extracts:
        - Import statements
        - Class inheritance (extends)
        - Trait mixing (with)

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

        # Extract import dependencies
        import_nodes = self.find_nodes_by_type(root_node, "import_declaration")
        for import_node in import_nodes:
            deps = self._extract_import_dependency(import_node, symbols, file_path, content)
            dependencies.extend(deps)

        # Extract inheritance dependencies (extends)
        class_nodes = self.find_nodes_by_type(root_node, "class_definition")
        for class_node in class_nodes:
            deps = self._extract_inheritance_dependencies(class_node, symbols, file_path, content)
            dependencies.extend(deps)

        # Extract trait mixing dependencies (with)
        for class_node in class_nodes:
            deps = self._extract_trait_dependencies(class_node, symbols, file_path, content)
            dependencies.extend(deps)

        return dependencies

    def _extract_class(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract a class symbol."""
        # Find the class name
        name_node = None
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break

        if not name_node:
            return None

        class_name = self.get_node_text(name_node, content)
        symbol_id = self.generate_symbol_id(file_path, class_name, self.get_line_number(node))

        # Extract Scaladoc comment
        docstring = self._extract_scaladoc(node, content)

        return Symbol(
            id=symbol_id,
            name=class_name,
            type=SymbolType.CLASS,
            file_path=file_path,
            language="scala",
            start_line=self.get_line_number(node),
            end_line=self.get_end_line_number(node),
            docstring=docstring,
        )

    def _extract_trait(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract a trait symbol."""
        # Find the trait name
        name_node = None
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break

        if not name_node:
            return None

        trait_name = self.get_node_text(name_node, content)
        symbol_id = self.generate_symbol_id(file_path, trait_name, self.get_line_number(node))

        # Extract Scaladoc comment
        docstring = self._extract_scaladoc(node, content)

        return Symbol(
            id=symbol_id,
            name=trait_name,
            type=SymbolType.INTERFACE,  # Treat traits as interfaces
            file_path=file_path,
            language="scala",
            start_line=self.get_line_number(node),
            end_line=self.get_end_line_number(node),
            docstring=docstring,
        )

    def _extract_object(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract an object symbol."""
        # Find the object name
        name_node = None
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break

        if not name_node:
            return None

        object_name = self.get_node_text(name_node, content)
        symbol_id = self.generate_symbol_id(file_path, object_name, self.get_line_number(node))

        # Extract Scaladoc comment
        docstring = self._extract_scaladoc(node, content)

        return Symbol(
            id=symbol_id,
            name=object_name,
            type=SymbolType.CLASS,  # Treat objects as classes (singleton)
            file_path=file_path,
            language="scala",
            start_line=self.get_line_number(node),
            end_line=self.get_end_line_number(node),
            docstring=docstring,
        )

    def _extract_class_members(
        self, class_node: tree_sitter.Node, file_path: str, content: str, parent_id: str
    ) -> List[Symbol]:
        """Extract functions and values from a class."""
        members = []

        # Find the template body
        template_body = self._find_template_body(class_node)
        if not template_body:
            return members

        # Extract functions (def)
        function_nodes = self.find_nodes_by_type(template_body, "function_definition")
        for func_node in function_nodes:
            symbol = self._extract_function(func_node, file_path, content, parent_id)
            if symbol:
                members.append(symbol)

        # Extract values (val/var)
        val_nodes = self.find_nodes_by_type(template_body, "val_definition")
        for val_node in val_nodes:
            value_symbols = self._extract_values(val_node, file_path, content, parent_id)
            members.extend(value_symbols)

        var_nodes = self.find_nodes_by_type(template_body, "var_definition")
        for var_node in var_nodes:
            value_symbols = self._extract_values(var_node, file_path, content, parent_id)
            members.extend(value_symbols)

        return members

    def _extract_trait_members(
        self, trait_node: tree_sitter.Node, file_path: str, content: str, parent_id: str
    ) -> List[Symbol]:
        """Extract functions from a trait."""
        members = []

        # Find the template body
        template_body = self._find_template_body(trait_node)
        if not template_body:
            return members

        # Extract functions
        function_nodes = self.find_nodes_by_type(template_body, "function_definition")
        for func_node in function_nodes:
            symbol = self._extract_function(func_node, file_path, content, parent_id)
            if symbol:
                members.append(symbol)

        return members

    def _extract_object_members(
        self, object_node: tree_sitter.Node, file_path: str, content: str, parent_id: str
    ) -> List[Symbol]:
        """Extract functions and values from an object."""
        return self._extract_class_members(object_node, file_path, content, parent_id)

    def _extract_function(
        self, node: tree_sitter.Node, file_path: str, content: str, parent_id: Optional[str] = None
    ) -> Optional[Symbol]:
        """Extract a function symbol."""
        # Find the function name
        name_node = None
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break

        if not name_node:
            return None

        function_name = self.get_node_text(name_node, content)
        symbol_id = self.generate_symbol_id(file_path, function_name, self.get_line_number(node))

        # Extract Scaladoc comment
        docstring = self._extract_scaladoc(node, content)

        return Symbol(
            id=symbol_id,
            name=function_name,
            type=SymbolType.FUNCTION if parent_id is None else SymbolType.METHOD,
            file_path=file_path,
            language="scala",
            start_line=self.get_line_number(node),
            end_line=self.get_end_line_number(node),
            parent_id=parent_id,
            docstring=docstring,
        )

    def _extract_values(
        self, node: tree_sitter.Node, file_path: str, content: str, parent_id: Optional[str] = None
    ) -> List[Symbol]:
        """Extract value symbols from val/var definitions."""
        values = []

        # Find pattern definitions (can be multiple in one declaration)
        pattern_nodes = self.find_nodes_by_type(node, "identifier")

        for pattern_node in pattern_nodes:
            value_name = self.get_node_text(pattern_node, content)

            # Skip type identifiers
            if pattern_node.parent and pattern_node.parent.type in ["type_identifier", "type"]:
                continue

            symbol_id = self.generate_symbol_id(file_path, value_name, self.get_line_number(node))

            values.append(
                Symbol(
                    id=symbol_id,
                    name=value_name,
                    type=SymbolType.FIELD,
                    file_path=file_path,
                    language="scala",
                    start_line=self.get_line_number(node),
                    end_line=self.get_end_line_number(node),
                    parent_id=parent_id,
                )
            )
            break  # Only take the first identifier as the value name

        return values

    def _find_template_body(self, node: tree_sitter.Node) -> Optional[tree_sitter.Node]:
        """Find the template body of a class/trait/object."""
        for child in node.children:
            if child.type == "template_body":
                return child
        return None

    def _find_top_level_functions(self, root_node: tree_sitter.Node) -> List[tree_sitter.Node]:
        """Find top-level function definitions."""
        functions = []

        for child in root_node.children:
            if child.type == "function_definition":
                functions.append(child)

        return functions

    def _extract_scaladoc(self, node: tree_sitter.Node, content: str) -> Optional[str]:
        """Extract Scaladoc comment before a node."""
        # Look for a comment node immediately before this node
        if node.prev_sibling and node.prev_sibling.type == "comment":
            comment_text = self.get_node_text(node.prev_sibling, content)
            # Clean up Scaladoc formatting
            if comment_text.startswith("/**") and comment_text.endswith("*/"):
                # Remove /** and */ and clean up asterisks
                lines = comment_text[3:-2].split("\n")
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if line.startswith("*"):
                        line = line[1:].strip()
                    if line:
                        cleaned_lines.append(line)
                return "\n".join(cleaned_lines)
        return None

    def _extract_import_dependency(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract import dependencies."""
        dependencies = []

        # Get the imported name
        import_text = self.get_node_text(node, content)
        # Remove 'import' keyword
        import_text = import_text.replace("import", "").strip()

        # For now, create a simple import dependency
        for symbol in symbols:
            if symbol.type in [SymbolType.CLASS, SymbolType.INTERFACE]:
                # Use a placeholder ID for external dependencies
                to_symbol_id = f"external:{import_text}"
                dep_id = self.generate_dependency_id(symbol.id, to_symbol_id)
                dependencies.append(
                    Dependency(
                        id=dep_id,
                        from_symbol_id=symbol.id,
                        to_symbol_id=to_symbol_id,
                        relationship_type="import",
                    )
                )
                break  # Only create one import dependency per import statement

        return dependencies

    def _extract_inheritance_dependencies(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract inheritance dependencies (extends)."""
        dependencies = []

        # Find the class name
        class_name = None
        for child in node.children:
            if child.type == "identifier":
                class_name = self.get_node_text(child, content)
                break

        if not class_name:
            return dependencies

        # Find extends clause
        extends_clause = None
        for child in node.children:
            if child.type == "extends_clause":
                extends_clause = child
                break

        if not extends_clause:
            return dependencies

        # Get the parent class name
        parent_name = None
        for child in extends_clause.children:
            if child.type in ["type_identifier", "identifier"]:
                parent_name = self.get_node_text(child, content)
                break

        if not parent_name:
            return dependencies

        # Find the class symbol
        class_symbol = None
        for symbol in symbols:
            if symbol.name == class_name and symbol.type == SymbolType.CLASS:
                class_symbol = symbol
                break

        if class_symbol:
            # Use a placeholder ID for external dependencies
            to_symbol_id = f"external:{parent_name}"
            dep_id = self.generate_dependency_id(class_symbol.id, to_symbol_id)
            dependencies.append(
                Dependency(
                    id=dep_id,
                    from_symbol_id=class_symbol.id,
                    to_symbol_id=to_symbol_id,
                    relationship_type="extends",
                )
            )

        return dependencies

    def _extract_trait_dependencies(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract trait mixing dependencies (with)."""
        dependencies = []

        # Find the class name
        class_name = None
        for child in node.children:
            if child.type == "identifier":
                class_name = self.get_node_text(child, content)
                break

        if not class_name:
            return dependencies

        # Find extends clause which may contain 'with' traits
        extends_clause = None
        for child in node.children:
            if child.type == "extends_clause":
                extends_clause = child
                break

        if not extends_clause:
            return dependencies

        # Get all trait names (after 'with' keyword)
        trait_names = []
        found_with = False
        for child in extends_clause.children:
            if self.get_node_text(child, content) == "with":
                found_with = True
            elif found_with and child.type in ["type_identifier", "identifier"]:
                trait_names.append(self.get_node_text(child, content))

        # Find the class symbol
        class_symbol = None
        for symbol in symbols:
            if symbol.name == class_name and symbol.type == SymbolType.CLASS:
                class_symbol = symbol
                break

        if class_symbol:
            for trait_name in trait_names:
                # Use a placeholder ID for external dependencies
                to_symbol_id = f"external:{trait_name}"
                dep_id = self.generate_dependency_id(class_symbol.id, to_symbol_id)
                dependencies.append(
                    Dependency(
                        id=dep_id,
                        from_symbol_id=class_symbol.id,
                        to_symbol_id=to_symbol_id,
                        relationship_type="mixes",
                    )
                )

        return dependencies


# Made with Bob
