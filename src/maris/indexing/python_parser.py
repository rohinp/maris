"""Python-specific Tree-sitter parser for symbol extraction."""

from typing import List, Optional

import tree_sitter
import tree_sitter_python

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


class PythonParser(TreeSitterParser):
    """
    Python-specific implementation of Tree-sitter parser.

    Extracts symbols (classes, functions, methods) and dependencies
    (imports, function calls) from Python source code.
    """

    def __init__(self):
        """Initialize the Python parser."""
        super().__init__("python")

    def setup_parser(self) -> None:
        """Set up the Tree-sitter parser with Python grammar."""
        # Create Language object from PyCapsule
        python_language = tree_sitter.Language(tree_sitter_python.language())
        self.parser = tree_sitter.Parser(python_language)

    def extract_symbols(self, tree: tree_sitter.Tree, file_path: str, content: str) -> List[Symbol]:
        """
        Extract symbols from Python source code.

        Extracts:
        - Classes
        - Functions (top-level and methods)
        - Constants (UPPER_CASE variables)

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

                # Extract methods within the class
                method_symbols = self._extract_methods(
                    class_node, file_path, content, symbol.id, parent_name=symbol.name
                )
                symbols.extend(method_symbols)

        # Extract top-level functions
        function_nodes = self._find_top_level_functions(root_node)
        for func_node in function_nodes:
            symbol = self._extract_function(func_node, file_path, content)
            if symbol:
                symbols.append(symbol)

        # Extract constants (UPPER_CASE assignments at module level)
        constant_symbols = self._extract_constants(root_node, file_path, content)
        symbols.extend(constant_symbols)

        return symbols

    def extract_dependencies(
        self, tree: tree_sitter.Tree, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """
        Extract dependency relationships from Python code.

        Extracts:
        - Import statements
        - Function calls
        - Class inheritance

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

        # Extract import dependencies
        import_deps = self._extract_import_dependencies(root_node, symbols, file_path, content)
        dependencies.extend(import_deps)

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

        # Extract docstring
        docstring = self._extract_python_docstring(node, content)

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

    def _extract_methods(
        self,
        class_node: tree_sitter.Node,
        file_path: str,
        content: str,
        parent_id: str,
        parent_name: Optional[str] = None,
    ) -> List[Symbol]:
        """Extract method symbols from a class."""
        methods = []
        body_node = class_node.child_by_field_name("body")
        if not body_node:
            return methods

        for child in body_node.children:
            if child.type == "function_definition":
                method = self._extract_function(
                    child, file_path, content, parent_id, parent_name=parent_name
                )
                if method:
                    # Change type to METHOD
                    method.type = SymbolType.METHOD
                    methods.append(method)

        return methods

    def _extract_function(
        self,
        node: tree_sitter.Node,
        file_path: str,
        content: str,
        parent_id: Optional[str] = None,
        parent_name: Optional[str] = None,
    ) -> Optional[Symbol]:
        """Extract a function or method symbol."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        func_name = self.get_node_text(name_node, content)
        start_line = self.get_line_number(node)
        end_line = self.get_end_line_number(node)

        # Extract parameters for signature
        params_node = node.child_by_field_name("parameters")
        signature = None
        if params_node:
            params_text = self.get_node_text(params_node, content)
            signature = f"def {func_name}{params_text}"

        # Return type annotation (Python 3 -> annotation)
        return_type = self.extract_return_type(node, content)
        if return_type and signature:
            signature = f"{signature} -> {return_type}"
        elif return_type:
            signature = f"def {func_name} -> {return_type}"

        # Extract docstring
        docstring = self._extract_python_docstring(node, content)

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

        symbol_id = self.generate_symbol_id(file_path, func_name, start_line)

        return Symbol(
            id=symbol_id,
            name=func_name,
            type=SymbolType.FUNCTION,
            file_path=file_path,
            language=self.language,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            docstring=docstring,
            parent_id=parent_id,
            metadata=metadata,
        )

    def _extract_constants(
        self, node: tree_sitter.Node, file_path: str, content: str
    ) -> List[Symbol]:
        """Extract module-level constants (UPPER_CASE variables)."""
        constants = []

        # Find top-level assignments
        for child in node.children:
            if child.type == "expression_statement":
                # The assignment is the first child of expression_statement
                for subchild in child.children:
                    if subchild.type == "assignment":
                        # Get the left side (identifier)
                        left = subchild.children[0] if subchild.children else None
                        if left and left.type == "identifier":
                            var_name = self.get_node_text(left, content)
                            # Check if it's UPPER_CASE (constant convention)
                            if var_name.isupper() and len(var_name) > 1:
                                start_line = self.get_line_number(subchild)
                                symbol_id = self.generate_symbol_id(file_path, var_name, start_line)

                                constants.append(
                                    Symbol(
                                        id=symbol_id,
                                        name=var_name,
                                        type=SymbolType.CONSTANT,
                                        file_path=file_path,
                                        language=self.language,
                                        start_line=start_line,
                                        end_line=start_line,
                                    )
                                )

        return constants

    def _find_top_level_functions(self, node: tree_sitter.Node) -> List[tree_sitter.Node]:
        """Find function definitions at module level (not inside classes)."""
        functions = []

        for child in node.children:
            if child.type == "function_definition":
                functions.append(child)

        return functions

    def _extract_python_docstring(self, node: tree_sitter.Node, content: str) -> Optional[str]:
        """
        Extract Python docstring from a function or class.

        Args:
            node: Function or class definition node
            content: Source code content

        Returns:
            Docstring text or None
        """
        body_node = node.child_by_field_name("body")
        if not body_node or len(body_node.children) == 0:
            return None

        # Check if first statement in body is a string (docstring)
        first_stmt = body_node.children[0]
        if first_stmt.type == "expression_statement":
            expr = first_stmt.children[0] if first_stmt.children else None
            if expr and expr.type == "string":
                docstring = self.get_node_text(expr, content)
                # Remove quotes and clean up
                docstring = docstring.strip('"""').strip("'''").strip('"').strip("'")
                return docstring.strip()

        return None

    def _extract_import_dependencies(
        self, node: tree_sitter.Node, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:
        """Extract import dependencies from import statements."""
        dependencies = []

        # Find import statements: import module
        import_nodes = self.find_nodes_by_type(node, "import_statement")
        for import_node in import_nodes:
            # Get the module name
            dotted_name = import_node.child_by_field_name("name")
            if dotted_name:
                module_name = self.get_node_text(dotted_name, content)

                # Create a dependency for the import
                dep_id = f"{file_path}:import:{module_name}"
                dependencies.append(
                    Dependency(
                        id=dep_id,
                        from_symbol_id=file_path,  # File-level import
                        to_symbol_id=module_name,
                        relationship_type="imports",
                    )
                )

        # Find from...import statements: from module import name
        import_from_nodes = self.find_nodes_by_type(node, "import_from_statement")
        for import_node in import_from_nodes:
            # Get the module name
            module_name_node = import_node.child_by_field_name("module_name")
            if module_name_node:
                module_name = self.get_node_text(module_name_node, content)

                # Get imported names
                for child in import_node.children:
                    if child.type == "dotted_name" or child.type == "identifier":
                        imported_name = self.get_node_text(child, content)
                        if imported_name and imported_name not in ["from", "import"]:
                            dep_id = f"{file_path}:import:{module_name}.{imported_name}"
                            dependencies.append(
                                Dependency(
                                    id=dep_id,
                                    from_symbol_id=file_path,
                                    to_symbol_id=f"{module_name}.{imported_name}",
                                    relationship_type="imports",
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

        # Find all function calls
        call_nodes = self.find_nodes_by_type(node, "call")

        for call_node in call_nodes:
            # Get the function being called
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
                # Direct function call: func()
                called_name = self.get_node_text(func_node, content)
            elif func_node.type == "attribute":
                # Method call: obj.method()
                # Get the attribute name (method name)
                attr_node = func_node.child_by_field_name("attribute")
                if attr_node:
                    called_name = self.get_node_text(attr_node, content)

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

        class_nodes = self.find_nodes_by_type(node, "class_definition")

        for class_node in class_nodes:
            # Get class name
            name_node = class_node.child_by_field_name("name")
            if not name_node:
                continue

            class_name = self.get_node_text(name_node, content)

            # Get superclasses
            superclasses_node = class_node.child_by_field_name("superclasses")
            if not superclasses_node:
                continue

            # Find the symbol for this class
            from_symbol = None
            for symbol in symbols:
                if symbol.name == class_name and symbol.type == SymbolType.CLASS:
                    from_symbol = symbol
                    break

            if not from_symbol:
                continue

            # Extract base class names
            for child in superclasses_node.children:
                if child.type == "identifier":
                    base_class = self.get_node_text(child, content)
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


# Made with Bob
