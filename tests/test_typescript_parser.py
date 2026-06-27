"""Tests for TypeScriptParser."""

import pytest

from maris.core.models import METADATA_CALLS, METADATA_RETURN_TYPE, METADATA_SOURCE, SymbolType
from maris.indexing.typescript_parser import TypeScriptParser


class TestTypeScriptParser:
    """Test suite for TypeScriptParser."""

    @pytest.fixture
    def parser(self):
        """Create a TypeScriptParser instance."""
        return TypeScriptParser()

    def test_parser_initialization(self, parser):
        """Test that parser initializes correctly."""
        assert parser.language == "typescript"
        assert parser.parser is None

    def test_setup_parser(self, parser):
        """Test parser setup."""
        parser.setup_parser()
        assert parser.parser is not None

    def test_extract_class(self, parser):
        """Test extracting a class with types."""
        content = """
/**
 * User class with type annotations
 */
class User {
    private name: string;

    constructor(name: string) {
        this.name = name;
    }

    /**
     * Get user name
     */
    getName(): string {
        return this.name;
    }
}
"""
        tree = parser.parse_file("test.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.ts", content)

        # Should extract class and method
        assert len(symbols) >= 2

        # Check class
        user_class = next((s for s in symbols if s.name == "User"), None)
        assert user_class is not None
        assert user_class.type == SymbolType.CLASS
        assert user_class.language == "typescript"
        assert "User class" in user_class.docstring

        # Check method
        get_name_method = next((s for s in symbols if s.name == "getName"), None)
        assert get_name_method is not None
        assert get_name_method.type == SymbolType.METHOD

    def test_extract_interface(self, parser):
        """Test extracting interfaces."""
        content = """
/**
 * User interface
 */
interface IUser {
    id: number;
    name: string;
    email: string;
}

/**
 * Admin interface
 */
interface IAdmin extends IUser {
    permissions: string[];
}
"""
        tree = parser.parse_file("test.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.ts", content)

        # Should extract both interfaces
        interfaces = [s for s in symbols if s.type == SymbolType.INTERFACE]
        assert len(interfaces) >= 2

        # Check IUser interface
        iuser = next((s for s in interfaces if s.name == "IUser"), None)
        assert iuser is not None
        assert "User interface" in iuser.docstring

        # Check IAdmin interface
        iadmin = next((s for s in interfaces if s.name == "IAdmin"), None)
        assert iadmin is not None
        assert "Admin interface" in iadmin.docstring

    def test_extract_type_alias(self, parser):
        """Test extracting type aliases."""
        content = """
/**
 * User ID type
 */
type UserId = string | number;

/**
 * Status type
 */
type Status = 'active' | 'inactive' | 'pending';
"""
        tree = parser.parse_file("test.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.ts", content)

        # Should extract type aliases as interfaces
        type_aliases = [s for s in symbols if s.name in ["UserId", "Status"]]
        assert len(type_aliases) == 2

    def test_extract_function_with_types(self, parser):
        """Test extracting functions with type annotations."""
        content = """
/**
 * Calculate sum with types
 */
function add(a: number, b: number): number {
    return a + b;
}

/**
 * Arrow function with types
 */
const multiply = (a: number, b: number): number => a * b;
"""
        tree = parser.parse_file("test.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.ts", content)

        # Should extract both functions
        functions = [s for s in symbols if s.type == SymbolType.FUNCTION]
        assert len(functions) >= 2

        # Check regular function
        add_func = next((s for s in functions if s.name == "add"), None)
        assert add_func is not None

        # Check arrow function
        multiply_func = next((s for s in functions if s.name == "multiply"), None)
        assert multiply_func is not None

    def test_extract_arrow_function_enriched_metadata(self, parser):
        """Test extracting rich metadata for typed arrow functions."""
        content = """
const retryExecuteNode = (node: Node, state: State): Try<State> => {
    attemptExecuteNode(node, state);
    this.reducer.reduce(state);
};
"""
        tree = parser.parse_file("test.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.ts", content)
        symbol = next((s for s in symbols if s.name == "retryExecuteNode"), None)

        assert symbol is not None
        assert symbol.signature == "retryExecuteNode(node: Node, state: State): Try<State>"
        assert symbol.metadata[METADATA_RETURN_TYPE] == "Try<State>"
        assert symbol.metadata[METADATA_CALLS] == ["attemptExecuteNode", "reducer.reduce"]
        assert "retryExecuteNode = (node: Node" in symbol.metadata[METADATA_SOURCE]

    def test_extract_constants(self, parser):
        """Test extracting constants."""
        content = """
const API_URL: string = "https://api.example.com";
const MAX_RETRIES: number = 3;
const config = { timeout: 5000 };
"""
        tree = parser.parse_file("test.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.ts", content)

        # Should extract UPPER_CASE constants only
        constants = [s for s in symbols if s.type == SymbolType.CONSTANT]
        assert len(constants) == 2

        constant_names = {c.name for c in constants}
        assert "API_URL" in constant_names
        assert "MAX_RETRIES" in constant_names

    def test_extract_import_dependencies(self, parser):
        """Test extracting import dependencies."""
        content = """
import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import * as _ from 'lodash';

class MyComponent {
    constructor(private http: HttpClient) {}
}
"""
        tree = parser.parse_file("test.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.ts", content)
        dependencies = parser.extract_dependencies(tree, symbols, "test.ts", content)

        # Should have import dependencies
        import_deps = [d for d in dependencies if d.relationship_type == "imports"]
        assert len(import_deps) >= 2

    def test_extract_class_inheritance(self, parser):
        """Test extracting class inheritance."""
        content = """
class Animal {
    constructor(public name: string) {}
}

class Dog extends Animal {
    bark(): void {
        console.log('Woof!');
    }
}
"""
        tree = parser.parse_file("test.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.ts", content)
        dependencies = parser.extract_dependencies(tree, symbols, "test.ts", content)

        # Should have extends dependency
        extends_deps = [d for d in dependencies if d.relationship_type == "extends"]
        assert len(extends_deps) == 1

    def test_extract_interface_implementation(self, parser):
        """Test extracting interface implementation."""
        content = """
interface Drawable {
    draw(): void;
}

interface Colorable {
    setColor(color: string): void;
}

class Shape implements Drawable, Colorable {
    draw(): void {
        console.log('Drawing');
    }

    setColor(color: string): void {
        console.log('Setting color');
    }
}
"""
        tree = parser.parse_file("test.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.ts", content)
        dependencies = parser.extract_dependencies(tree, symbols, "test.ts", content)

        # Should have implements dependencies
        implements_deps = [d for d in dependencies if d.relationship_type == "implements"]
        assert len(implements_deps) == 2

    def test_empty_file(self, parser):
        """Test parsing an empty file."""
        content = ""
        tree = parser.parse_file("empty.ts", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "empty.ts", content)
        assert len(symbols) == 0


# Made with Bob
