"""TypeScript-specific Tree-sitter parser for symbol extraction."""

from typing import List, Optional

import tree_sitter
import tree_sitter_typescript

from maris.core.models import Dependency, Symbol, SymbolType
from maris.indexing.parser import TreeSitterParser


class TypeScriptParser(TreeSitterParser):
    """
    TypeScript-specific implementation of Tree-sitter parser.

    Extracts symbols (classes, interfaces, functions, methods, constants) and dependencies
    (imports, function calls, class inheritance) from TypeScript source code.
    """

    def __init__(self):
        """Initialize the TypeScript parser."""
        super().__init__("typescript")

    def setup_parser(self) -> None:
        """Set up the Tree-sitter parser with TypeScript grammar."""
        # tree_sitter_typescript provides both TypeScript and TSX
        typescript_language = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        self.parser = tree_sitter.Parser(typescript_language)

    def extract_symbols(self, tree: tree_sitter.Tree, file_path: str, content: str) -> List[Symbol]:
        """
        Extract symbols from TypeScript source code.

        Extracts:
        - Classes
        - Interfaces
        - Functions (regular, arrow, async)
        - Methods
        - Constants (const declarations)
        - Type aliases

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

                # Extract methods within the class
                method_symbols = self._extract_methods(class_node, file_path, content, symbol.id)
                symbols.extend(method_symbols)

        # Extract interfaces
        interface_nodes = self.find_nodes_by_type(root_node, "interface_declaration")
        for interface_node in interface_nodes:
            symbol = self._extract_interface(interface_node, file_path, content)
            if symbol:
                symbols.append(symbol)

        # Extract type aliases
        type_nodes = self.find_nodes_by_type(root_node, "type_alias_declaration")
        for type_node in type_nodes:
            symbol = self._extract_type_alias(type_node, file_path, content)
            if symbol:
                symbols.append(symbol)

        # Extract top-level functions
        function_symbols = self._extract_top_level_functions(root_node, file_path, content)
        symbols.extend(function_symbols)

        # Extract constants
        constant_symbols = self._extract_constants(root_node, file_path, content)
        symbols.extend(constant_symbols)

        return symbols

    def extract_dependencies(
        self, tree: tree_sitter.Tree, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """
        Extract dependency relationships from TypeScript code.

        Extracts:
        - Import statements (ES6 imports)
        - Require statements (CommonJS)
        - Function calls
        - Class inheritance
        - Interface implementation

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

        # Extract import dependencies (ES6)
        import_deps = self._extract_import_dependencies(root_node, symbols, file_path, content)
        dependencies.extend(import_deps)

        # Extract require dependencies (CommonJS)
        require_deps = self._extract_require_dependencies(root_node, symbols, file_path, content)
        dependencies.extend(require_deps)

        # Extract function call dependencies
        call_deps = self._extract_call_dependencies(
            root_node, symbols, symbol_map, file_path, content
        )
        dependencies.extend(call_deps)

        # Extract inheritance dependencies
        inheritance_deps = self._extract_inheritance_dependencies(
            root_node, symbols, file_path, content
        )
        dependencies.extend(inheritance_deps)

        # Extract interface implementation dependencies
        implements_deps = self._extract_implements_dependencies(
            root_node, symbols, file_path, content
        )
        dependencies.extend(implements_deps)

        return dependencies

    def _extract_class(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract a class symbol."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        class_name = self.get_node_text(name_node, content)
        start_line = self.get_line_number(node)
        end_line = self.get_end_line_number(node)

        # Extract TSDoc comment
        docstring = self._extract_tsdoc(node, content)

        symbol_id = self.generate_symbol_id(file_path, class_name, start_line)

        return Symbol(
            id=symbol_id,
            name=class_name,
            type=SymbolType.CLASS,
            file_path=file_path,
            language=self.language,
            start_line=start_line,
            end_line=end_line,
            docstring=docstring,
        )

    def _extract_interface(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract an interface symbol."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        interface_name = self.get_node_text(name_node, content)
        start_line = self.get_line_number(node)
        end_line = self.get_end_line_number(node)

        # Extract TSDoc comment
        docstring = self._extract_tsdoc(node, content)

        symbol_id = self.generate_symbol_id(file_path, interface_name, start_line)

        return Symbol(
            id=symbol_id,
            name=interface_name,
            type=SymbolType.INTERFACE,
            file_path=file_path,
            language=self.language,
            start_line=start_line,
            end_line=end_line,
            docstring=docstring,
        )

    def _extract_type_alias(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract a type alias symbol."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        type_name = self.get_node_text(name_node, content)
        start_line = self.get_line_number(node)
        end_line = self.get_end_line_number(node)

        # Extract TSDoc comment
        docstring = self._extract_tsdoc(node, content)

        symbol_id = self.generate_symbol_id(file_path, type_name, start_line)

        return Symbol(
            id=symbol_id,
            name=type_name,
            type=SymbolType.INTERFACE,  # Treat type aliases as interfaces
            file_path=file_path,
            language=self.language,
            start_line=start_line,
            end_line=end_line,
            docstring=docstring,
        )

    def _extract_methods(
        self, class_node: tree_sitter.Node, file_path: str, content: str, parent_id: str
    ) -> List[Symbol]:
        """Extract method symbols from a class."""
        methods = []
        body_node = class_node.child_by_field_name("body")
        if not body_node:
            return methods

        for child in body_node.children:
            if child.type in ["method_definition", "public_field_definition"]:
                method = self._extract_method(child, file_path, content, parent_id)
                if method:
                    methods.append(method)

        return methods

    def _extract_method(
        self, node: tree_sitter.Node, file_path: str, content: str, parent_id: str
    ) -> Optional[Symbol]:
        """Extract a method symbol."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        method_name = self.get_node_text(name_node, content)
        start_line = self.get_line_number(node)
        end_line = self.get_end_line_number(node)

        # Extract TSDoc comment
        docstring = self._extract_tsdoc(node, content)

        symbol_id = self.generate_symbol_id(file_path, method_name, start_line)

        return Symbol(
            id=symbol_id,
            name=method_name,
            type=SymbolType.METHOD,
            file_path=file_path,
            language=self.language,
            start_line=start_line,
            end_line=end_line,
            docstring=docstring,
            parent_id=parent_id,
        )

    def _extract_top_level_functions(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> List[Symbol]:
        """Extract top-level function declarations."""
        functions = []

        for child in node.children:
            symbol = None
            if child.type == "function_declaration":
                symbol = self._extract_function_declaration(child, file_path, content)
            elif child.type == "lexical_declaration":
                # Check for arrow functions: const foo = () => {}
                symbol = self._extract_arrow_function(child, file_path, content)

            if symbol:
                functions.append(symbol)

        return functions

    def _extract_function_declaration(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract a function declaration."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        func_name = self.get_node_text(name_node, content)
        start_line = self.get_line_number(node)
        end_line = self.get_end_line_number(node)

        # Extract TSDoc comment
        docstring = self._extract_tsdoc(node, content)

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
        )

    def _extract_arrow_function(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> Optional[Symbol]:
        """Extract arrow function from const/let declaration."""
        # Look for pattern: const name = () => {}
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")

                if name_node and value_node and value_node.type == "arrow_function":
                    func_name = self.get_node_text(name_node, content)
                    start_line = self.get_line_number(node)
                    end_line = self.get_end_line_number(node)

                    # Extract TSDoc comment
                    docstring = self._extract_tsdoc(node, content)

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
                    )
        return None

    def _extract_constants(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> List[Symbol]:
        """Extract module-level constants (const declarations)."""
        constants = []

        for child in node.children:
            if child.type == "lexical_declaration":
                # Check if it's a const declaration
                for subchild in child.children:
                    if subchild.type == "const":
                        # Find the variable declarator
                        for declarator in child.children:
                            if declarator.type == "variable_declarator":
                                name_node = declarator.child_by_field_name("name")
                                value_node = declarator.child_by_field_name("value")

                                if name_node and value_node:
                                    # Skip if value is a function (already extracted)
                                    if value_node.type in ["arrow_function", "function"]:
                                        continue

                                    const_name = self.get_node_text(name_node, content)
                                    # Only extract UPPER_CASE constants
                                    if const_name.isupper() and len(const_name) > 1:
                                        start_line = self.get_line_number(child)
                                        symbol_id = self.generate_symbol_id(
                                            file_path, const_name, start_line
                                        )

                                        constants.append(
                                            Symbol(
                                                id=symbol_id,
                                                name=const_name,
                                                type=SymbolType.CONSTANT,
                                                file_path=file_path,
                                                language=self.language,
                                                start_line=start_line,
                                                end_line=start_line,
                                            )
                                        )

        return constants

    def _extract_tsdoc(self, node: tree_sitter.Node, content: str) -> Optional[str]:
        """
        Extract TSDoc comment before a node.

        Args:
            node: Node to extract documentation for
            content: Source code content

        Returns:
            TSDoc text or None
        """
        if node.prev_sibling and node.prev_sibling.type == "comment":
            comment_text = self.get_node_text(node.prev_sibling, content)
            # Check if it's a TSDoc comment (/** ... */)
            if comment_text.startswith("/**") and comment_text.endswith("*/"):
                # Clean up TSDoc formatting
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

    def _extract_import_dependencies(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract ES6 import dependencies."""
        dependencies = []

        import_nodes = self.find_nodes_by_type(node, "import_statement")
        for import_node in import_nodes:
            source_node = import_node.child_by_field_name("source")
            if source_node:
                module_name = self.get_node_text(source_node, content).strip('"').strip("'")

                dep_id = f"{file_path}:import:{module_name}"
                dependencies.append(
                    Dependency(
                        id=dep_id,
                        from_symbol_id=file_path,
                        to_symbol_id=module_name,
                        relationship_type="imports",
                    )
                )

        return dependencies

    def _extract_require_dependencies(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract CommonJS require dependencies."""
        dependencies = []

        # Find call expressions that might be require()
        call_nodes = self.find_nodes_by_type(node, "call_expression")
        for call_node in call_nodes:
            func_node = call_node.child_by_field_name("function")
            if func_node and self.get_node_text(func_node, content) == "require":
                # Get the argument (module name)
                args_node = call_node.child_by_field_name("arguments")
                if args_node and args_node.children:
                    for arg in args_node.children:
                        if arg.type == "string":
                            module_name = self.get_node_text(arg, content).strip('"').strip("'")

                            dep_id = f"{file_path}:require:{module_name}"
                            dependencies.append(
                                Dependency(
                                    id=dep_id,
                                    from_symbol_id=file_path,
                                    to_symbol_id=module_name,
                                    relationship_type="requires",
                                )
                            )
                            break

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

        call_nodes = self.find_nodes_by_type(node, "call_expression")

        for call_node in call_nodes:
            func_node = call_node.child_by_field_name("function")
            if not func_node:
                continue

            # Find which symbol contains this call
            call_line = self.get_line_number(call_node)
            from_symbol = None
            for symbol in symbols:
                if symbol.start_line <= call_line <= symbol.end_line:
                    from_symbol = symbol
                    break

            if not from_symbol:
                continue

            # Extract the called function name
            called_name = None
            if func_node.type == "identifier":
                called_name = self.get_node_text(func_node, content)
            elif func_node.type == "member_expression":
                # Method call: obj.method()
                property_node = func_node.child_by_field_name("property")
                if property_node:
                    called_name = self.get_node_text(property_node, content)

            if not called_name:
                continue

            # Try to find the called symbol in our symbol map
            to_symbol_id = symbol_map.get(called_name)
            if to_symbol_id:
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

    def _extract_inheritance_dependencies(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract class inheritance dependencies."""
        dependencies = []

        class_nodes = self.find_nodes_by_type(node, "class_declaration")

        for class_node in class_nodes:
            name_node = class_node.child_by_field_name("name")
            if not name_node:
                continue

            class_name = self.get_node_text(name_node, content)

            # Get superclass
            heritage_node = class_node.child_by_field_name("heritage")
            if not heritage_node:
                continue

            # Find the class symbol
            class_line = self.get_line_number(class_node)
            from_symbol = None
            for symbol in symbols:
                if symbol.name == class_name and symbol.type == SymbolType.CLASS:
                    from_symbol = symbol
                    break

            if not from_symbol:
                continue

            # Extract base class name
            for child in heritage_node.children:
                if child.type == "extends_clause":
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            base_class = self.get_node_text(subchild, content)
                            dep_id = f"{from_symbol.id}:extends:{base_class}"
                            dependencies.append(
                                Dependency(
                                    id=dep_id,
                                    from_symbol_id=from_symbol.id,
                                    to_symbol_id=base_class,
                                    relationship_type="extends",
                                )
                            )

        return dependencies

    def _extract_implements_dependencies(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract interface implementation dependencies."""
        dependencies = []

        class_nodes = self.find_nodes_by_type(node, "class_declaration")

        for class_node in class_nodes:
            name_node = class_node.child_by_field_name("name")
            if not name_node:
                continue

            class_name = self.get_node_text(name_node, content)

            # Get implements clause
            heritage_node = class_node.child_by_field_name("heritage")
            if not heritage_node:
                continue

            # Find the class symbol
            from_symbol = None
            for symbol in symbols:
                if symbol.name == class_name and symbol.type == SymbolType.CLASS:
                    from_symbol = symbol
                    break

            if not from_symbol:
                continue

            # Extract implemented interfaces
            for child in heritage_node.children:
                if child.type == "implements_clause":
                    # Get all interface names
                    for subchild in child.children:
                        if subchild.type == "type_identifier":
                            interface_name = self.get_node_text(subchild, content)
                            dep_id = f"{from_symbol.id}:implements:{interface_name}"
                            dependencies.append(
                                Dependency(
                                    id=dep_id,
                                    from_symbol_id=from_symbol.id,
                                    to_symbol_id=interface_name,
                                    relationship_type="implements",
                                )
                            )

        return dependencies


# Made with Bob
