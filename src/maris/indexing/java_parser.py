"""Java-specific Tree-sitter parser for symbol extraction."""

from typing import List, Optional

import tree_sitter
import tree_sitter_java

from maris.core.models import (
    METADATA_BODY_SUMMARY,
    METADATA_CALLS,
    METADATA_PARENT_NAME,
    METADATA_RETURN_TYPE,
    METADATA_SOURCE,
    Dependency,
    Symbol,
    SymbolType,
)
from maris.indexing.parser import TreeSitterParser


class JavaParser(TreeSitterParser):
    """
    Java-specific implementation of Tree-sitter parser.

    Extracts symbols (classes, interfaces, methods, fields) and dependencies
    (imports, method calls, inheritance) from Java source code.
    """

    def __init__(self):
        """Initialize the Java parser."""
        super().__init__("java")

    def setup_parser(self) -> None:
        """Set up the Tree-sitter parser with Java grammar."""
        java_language = tree_sitter.Language(tree_sitter_java.language())
        self.parser = tree_sitter.Parser(java_language)

    def extract_symbols(self, tree: tree_sitter.Tree, file_path: str, content: str) -> List[Symbol]:
        """
        Extract symbols from Java source code.

        Extracts:
        - Classes
        - Interfaces
        - Methods (including constructors)
        - Fields (instance and static)
        - Enums

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
        class_nodes = self.find_nodes_by_type(root_node, "class_declaration")
        for class_node in class_nodes:
            symbol = self._extract_class(class_node, file_path, content)
            if symbol:
                symbols.append(symbol)

                # Extract methods and fields within the class
                member_symbols = self._extract_class_members(
                    class_node, file_path, content, symbol.id, parent_name=symbol.name
                )
                symbols.extend(member_symbols)

        # Extract interfaces
        interface_nodes = self.find_nodes_by_type(root_node, "interface_declaration")
        for interface_node in interface_nodes:
            symbol = self._extract_interface(interface_node, file_path, content)
            if symbol:
                symbols.append(symbol)

                # Extract methods within the interface
                method_symbols = self._extract_interface_methods(
                    interface_node, file_path, content, symbol.id, parent_name=symbol.name
                )
                symbols.extend(method_symbols)

        # Extract enums
        enum_nodes = self.find_nodes_by_type(root_node, "enum_declaration")
        for enum_node in enum_nodes:
            symbol = self._extract_enum(enum_node, file_path, content)
            if symbol:
                symbols.append(symbol)

        return symbols

    def extract_dependencies(
        self, tree: tree_sitter.Tree, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """
        Extract dependency relationships from Java code.

        Extracts:
        - Import statements
        - Method calls
        - Class inheritance (extends)
        - Interface implementation (implements)

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
        class_nodes = self.find_nodes_by_type(root_node, "class_declaration")
        for class_node in class_nodes:
            deps = self._extract_inheritance_dependencies(class_node, symbols, file_path, content)
            dependencies.extend(deps)

        # Extract interface implementation dependencies (implements)
        for class_node in class_nodes:
            deps = self._extract_interface_dependencies(class_node, symbols, file_path, content)
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

        # Extract docstring (Javadoc comment before the class)
        docstring = self._extract_javadoc(node, content)

        return Symbol(
            id=symbol_id,
            name=class_name,
            type=SymbolType.CLASS,
            file_path=file_path,
            language="java",
            start_line=self.get_line_number(node),
            end_line=self.get_end_line_number(node),
            docstring=docstring,
        )

    def _extract_interface(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract an interface symbol."""
        # Find the interface name
        name_node = None
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break

        if not name_node:
            return None

        interface_name = self.get_node_text(name_node, content)
        symbol_id = self.generate_symbol_id(file_path, interface_name, self.get_line_number(node))

        # Extract docstring
        docstring = self._extract_javadoc(node, content)

        return Symbol(
            id=symbol_id,
            name=interface_name,
            type=SymbolType.INTERFACE,
            file_path=file_path,
            language="java",
            start_line=self.get_line_number(node),
            end_line=self.get_end_line_number(node),
            docstring=docstring,
        )

    def _extract_enum(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract an enum symbol."""
        # Find the enum name
        name_node = None
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break

        if not name_node:
            return None

        enum_name = self.get_node_text(name_node, content)
        symbol_id = self.generate_symbol_id(file_path, enum_name, self.get_line_number(node))

        # Extract docstring
        docstring = self._extract_javadoc(node, content)

        return Symbol(
            id=symbol_id,
            name=enum_name,
            type=SymbolType.CLASS,  # Treat enums as classes
            file_path=file_path,
            language="java",
            start_line=self.get_line_number(node),
            end_line=self.get_end_line_number(node),
            docstring=docstring,
        )

    def _extract_class_members(
        self,
        class_node: tree_sitter.Node,
        file_path: str,
        content: str,
        parent_id: str,
        parent_name: Optional[str] = None,
    ) -> List[Symbol]:
        """Extract methods and fields from a class."""
        members = []

        # Find the class body
        body_node = None
        for child in class_node.children:
            if child.type == "class_body":
                body_node = child
                break

        if not body_node:
            return members

        # Extract methods (including constructors)
        for child in body_node.children:
            if child.type == "method_declaration":
                symbol = self._extract_method(
                    child, file_path, content, parent_id, parent_name=parent_name
                )
                if symbol:
                    members.append(symbol)
            elif child.type == "constructor_declaration":
                symbol = self._extract_constructor(child, file_path, content, parent_id)
                if symbol:
                    members.append(symbol)
            elif child.type == "field_declaration":
                field_symbols = self._extract_fields(child, file_path, content, parent_id)
                members.extend(field_symbols)

        return members

    def _extract_interface_methods(
        self,
        interface_node: tree_sitter.Node,
        file_path: str,
        content: str,
        parent_id: str,
        parent_name: Optional[str] = None,
    ) -> List[Symbol]:
        """Extract methods from an interface."""
        methods = []

        # Find the interface body
        body_node = None
        for child in interface_node.children:
            if child.type == "interface_body":
                body_node = child
                break

        if not body_node:
            return methods

        # Extract method declarations
        for child in body_node.children:
            if child.type == "method_declaration":
                symbol = self._extract_method(
                    child, file_path, content, parent_id, parent_name=parent_name
                )
                if symbol:
                    methods.append(symbol)

        return methods

    def _extract_method(
        self,
        node: tree_sitter.Node,
        file_path: str,
        content: str,
        parent_id: Optional[str] = None,
        parent_name: Optional[str] = None,
    ) -> Optional[Symbol]:
        """Extract a method symbol."""
        # Find the method name
        name_node = None
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break

        if not name_node:
            return None

        method_name = self.get_node_text(name_node, content)
        symbol_id = self.generate_symbol_id(file_path, method_name, self.get_line_number(node))

        # Extract Javadoc comment
        docstring = self._extract_javadoc(node, content)

        # Signature: return type + name + parameters
        type_node = node.child_by_field_name("type")
        params_node = node.child_by_field_name("parameters")
        return_type: Optional[str] = None
        if type_node:
            return_type = self.get_node_text(type_node, content)
        signature: Optional[str] = None
        if params_node:
            params_text = self.get_node_text(params_node, content)
            rt_prefix = f"{return_type} " if return_type else ""
            signature = f"{rt_prefix}{method_name}{params_text}"

        # Calls + source from the method body
        body_node = node.child_by_field_name("body")
        calls: List[str] = []
        source: Optional[str] = None
        if body_node:
            calls = self.extract_calls(body_node, content)
            source = self.get_node_text(node, content)

        # Build metadata
        body_summary = self.body_summary_from_docstring(docstring)
        metadata = {}
        if parent_name:
            metadata[METADATA_PARENT_NAME] = parent_name
        if return_type:
            metadata[METADATA_RETURN_TYPE] = return_type
        if calls:
            metadata[METADATA_CALLS] = calls
        if source:
            metadata[METADATA_SOURCE] = source
        if body_summary:
            metadata[METADATA_BODY_SUMMARY] = body_summary

        return Symbol(
            id=symbol_id,
            name=method_name,
            type=SymbolType.METHOD,
            file_path=file_path,
            language="java",
            start_line=self.get_line_number(node),
            end_line=self.get_end_line_number(node),
            signature=signature,
            parent_id=parent_id,
            docstring=docstring,
            metadata=metadata,
        )

    def _extract_constructor(
        self, node: tree_sitter.Node, file_path: str, content: str, parent_id: Optional[str] = None
    ) -> Optional[Symbol]:
        """Extract a constructor symbol."""
        # Find the constructor name
        name_node = None
        for child in node.children:
            if child.type == "identifier":
                name_node = child
                break

        if not name_node:
            return None

        constructor_name = self.get_node_text(name_node, content)
        symbol_id = self.generate_symbol_id(file_path, constructor_name, self.get_line_number(node))

        # Extract docstring
        docstring = self._extract_javadoc(node, content)

        return Symbol(
            id=symbol_id,
            name=constructor_name,
            type=SymbolType.METHOD,  # Treat constructors as methods
            file_path=file_path,
            language="java",
            start_line=self.get_line_number(node),
            end_line=self.get_end_line_number(node),
            parent_id=parent_id,
            docstring=docstring,
        )

    def _extract_fields(
        self, node: tree_sitter.Node, file_path: str, content: str, parent_id: Optional[str] = None
    ) -> List[Symbol]:
        """Extract field symbols from a field declaration."""
        fields = []

        # A field declaration can declare multiple fields (e.g., int x, y, z;)
        declarators = self.find_nodes_by_type(node, "variable_declarator")

        for declarator in declarators:
            # Find the field name
            name_node = None
            for child in declarator.children:
                if child.type == "identifier":
                    name_node = child
                    break

            if not name_node:
                continue

            field_name = self.get_node_text(name_node, content)
            symbol_id = self.generate_symbol_id(file_path, field_name, self.get_line_number(node))

            fields.append(
                Symbol(
                    id=symbol_id,
                    name=field_name,
                    type=SymbolType.FIELD,
                    file_path=file_path,
                    language="java",
                    start_line=self.get_line_number(node),
                    end_line=self.get_end_line_number(node),
                    parent_id=parent_id,
                )
            )

        return fields

    def _extract_javadoc(self, node: tree_sitter.Node, content: str) -> Optional[str]:
        """Extract Javadoc comment before a node."""
        # Look for a comment node immediately before this node
        if node.prev_sibling and node.prev_sibling.type == "block_comment":
            comment_text = self.get_node_text(node.prev_sibling, content)
            # Clean up Javadoc formatting
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

    def extract_calls(self, body_node: tree_sitter.Node, content: str) -> List[str]:
        """
        Extract Java method calls while preserving receiver context.

        The generic implementation sees the ``name`` field of Java
        ``method_invocation`` nodes, which turns ``reducer.reduce()`` into just
        ``reduce``. Java exposes the receiver as the ``object`` field, so use
        that when present.
        """
        seen: set[str] = set()
        stack = [body_node]

        while stack:
            node = stack.pop()
            if node.type == "method_invocation":
                name_node = node.child_by_field_name("name")
                object_node = node.child_by_field_name("object")
                if name_node:
                    method_name = self.get_node_text(name_node, content)
                    if object_node:
                        object_name = self.get_node_text(object_node, content)
                        name = self._normalize_call_name(f"{object_name}.{method_name}")
                    else:
                        name = method_name
                    if name:
                        seen.add(name)
            stack.extend(node.children)

        return sorted(seen)

    def _extract_import_dependency(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract import dependencies."""
        dependencies = []

        # Get the imported name
        import_text = self.get_node_text(node, content)
        # Remove 'import' keyword and semicolon
        import_text = import_text.replace("import", "").replace(";", "").strip()

        # For now, we'll create a simple import dependency
        # In a full implementation, we'd resolve these to actual symbols
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

        # Find the superclass
        superclass_node = None
        for child in node.children:
            if child.type == "superclass":
                superclass_node = child
                break

        if not superclass_node:
            return dependencies

        # Get the superclass name
        superclass_name = None
        for child in superclass_node.children:
            if child.type == "type_identifier":
                superclass_name = self.get_node_text(child, content)
                break

        if not superclass_name:
            return dependencies

        # Find the class symbol
        class_symbol = None
        for symbol in symbols:
            if symbol.name == class_name and symbol.type == SymbolType.CLASS:
                class_symbol = symbol
                break

        if class_symbol:
            # Use a placeholder ID for external dependencies
            to_symbol_id = f"external:{superclass_name}"
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

    def _extract_interface_dependencies(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract interface implementation dependencies (implements)."""
        dependencies = []

        # Find the class name
        class_name = None
        for child in node.children:
            if child.type == "identifier":
                class_name = self.get_node_text(child, content)
                break

        if not class_name:
            return dependencies

        # Find the interfaces
        interfaces_node = None
        for child in node.children:
            if child.type == "super_interfaces":
                interfaces_node = child
                break

        if not interfaces_node:
            return dependencies

        # Get all interface names
        interface_names = []
        for child in interfaces_node.children:
            if child.type == "type_identifier":
                interface_names.append(self.get_node_text(child, content))

        # Find the class symbol
        class_symbol = None
        for symbol in symbols:
            if symbol.name == class_name and symbol.type == SymbolType.CLASS:
                class_symbol = symbol
                break

        if class_symbol:
            for interface_name in interface_names:
                # Use a placeholder ID for external dependencies
                to_symbol_id = f"external:{interface_name}"
                dep_id = self.generate_dependency_id(class_symbol.id, to_symbol_id)
                dependencies.append(
                    Dependency(
                        id=dep_id,
                        from_symbol_id=class_symbol.id,
                        to_symbol_id=to_symbol_id,
                        relationship_type="implements",
                    )
                )

        return dependencies


# Made with Bob
