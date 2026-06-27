"""Tests for JavaScriptParser."""

import pytest

from maris.core.models import METADATA_CALLS, METADATA_SOURCE, SymbolType
from maris.indexing.javascript_parser import JavaScriptParser


class TestJavaScriptParser:
    """Test suite for JavaScriptParser."""

    @pytest.fixture
    def parser(self):
        """Create a JavaScriptParser instance."""
        return JavaScriptParser()

    def test_parser_initialization(self, parser):
        """Test that parser initializes correctly."""
        assert parser.language == "javascript"
        assert parser.parser is None

    def test_setup_parser(self, parser):
        """Test parser setup."""
        parser.setup_parser()
        assert parser.parser is not None

    def test_extract_class(self, parser):
        """Test extracting a class."""
        content = """
/**
 * User class
 */
class User {
    constructor(name) {
        this.name = name;
    }

    /**
     * Get user name
     */
    getName() {
        return this.name;
    }
}
"""
        tree = parser.parse_file("test.js", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.js", content)

        # Should extract class and method
        assert len(symbols) >= 2

        # Check class
        user_class = next((s for s in symbols if s.name == "User"), None)
        assert user_class is not None
        assert user_class.type == SymbolType.CLASS
        assert user_class.language == "javascript"
        assert "User class" in user_class.docstring

        # Check method
        get_name_method = next((s for s in symbols if s.name == "getName"), None)
        assert get_name_method is not None
        assert get_name_method.type == SymbolType.METHOD
        assert "Get user name" in get_name_method.docstring

    def test_extract_function(self, parser):
        """Test extracting functions."""
        content = """
/**
 * Calculate sum
 */
function add(a, b) {
    return a + b;
}

/**
 * Arrow function
 */
const multiply = (a, b) => a * b;
"""
        tree = parser.parse_file("test.js", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.js", content)

        # Should extract both functions
        assert len(symbols) >= 2

        # Check regular function
        add_func = next((s for s in symbols if s.name == "add"), None)
        assert add_func is not None
        assert add_func.type == SymbolType.FUNCTION
        assert "Calculate sum" in add_func.docstring

        # Check arrow function
        multiply_func = next((s for s in symbols if s.name == "multiply"), None)
        assert multiply_func is not None
        assert multiply_func.type == SymbolType.FUNCTION

    def test_extract_arrow_function_enriched_metadata(self, parser):
        """Test extracting rich metadata for arrow functions."""
        content = """
const retryExecuteNode = (node, state) => {
    attemptExecuteNode(node, state);
    reducer.reduce(state);
};
"""
        tree = parser.parse_file("test.js", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.js", content)
        symbol = next((s for s in symbols if s.name == "retryExecuteNode"), None)

        assert symbol is not None
        assert symbol.signature == "retryExecuteNode(node, state)"
        assert symbol.metadata[METADATA_CALLS] == ["attemptExecuteNode", "reducer.reduce"]
        assert "retryExecuteNode = (node, state)" in symbol.metadata[METADATA_SOURCE]

    def test_extract_constants(self, parser):
        """Test extracting constants."""
        content = """
const API_URL = "https://api.example.com";
const MAX_RETRIES = 3;
const config = { timeout: 5000 };
"""
        tree = parser.parse_file("test.js", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.js", content)

        # Should extract UPPER_CASE constants only
        constants = [s for s in symbols if s.type == SymbolType.CONSTANT]
        assert len(constants) == 2

        constant_names = {c.name for c in constants}
        assert "API_URL" in constant_names
        assert "MAX_RETRIES" in constant_names
        assert "config" not in constant_names  # lowercase, not extracted

    def test_extract_import_dependencies(self, parser):
        """Test extracting import dependencies."""
        content = """
import React from 'react';
import { useState, useEffect } from 'react';
import './styles.css';

function App() {
    return <div>Hello</div>;
}
"""
        tree = parser.parse_file("test.js", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.js", content)
        dependencies = parser.extract_dependencies(tree, symbols, "test.js", content)

        # Should have import dependencies
        import_deps = [d for d in dependencies if d.relationship_type == "imports"]
        assert len(import_deps) >= 2

    def test_extract_require_dependencies(self, parser):
        """Test extracting CommonJS require dependencies."""
        content = """
const express = require('express');
const path = require('path');

function createServer() {
    const app = express();
    return app;
}
"""
        tree = parser.parse_file("test.js", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.js", content)
        dependencies = parser.extract_dependencies(tree, symbols, "test.js", content)

        # Should have require dependencies
        require_deps = [d for d in dependencies if d.relationship_type == "requires"]
        assert len(require_deps) >= 2

    def test_extract_inheritance(self, parser):
        """Test extracting class inheritance."""
        content = """
class Animal {
    constructor(name) {
        this.name = name;
    }
}

class Dog extends Animal {
    bark() {
        console.log('Woof!');
    }
}
"""
        tree = parser.parse_file("test.js", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.js", content)
        dependencies = parser.extract_dependencies(tree, symbols, "test.js", content)

        # Should have extends dependency
        extends_deps = [d for d in dependencies if d.relationship_type == "extends"]
        assert len(extends_deps) == 1
        assert "Animal" in extends_deps[0].to_symbol_id

    def test_empty_file(self, parser):
        """Test parsing an empty file."""
        content = ""
        tree = parser.parse_file("empty.js", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "empty.js", content)
        assert len(symbols) == 0


# Made with Bob
