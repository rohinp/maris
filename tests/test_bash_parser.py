"""Tests for BashParser."""

import pytest

from maris.indexing.bash_parser import BashParser
from maris.core.models import SymbolType


class TestBashParser:
    """Test suite for BashParser."""

    @pytest.fixture
    def parser(self):
        """Create a BashParser instance."""
        return BashParser()

    def test_parser_initialization(self, parser):
        """Test that parser initializes correctly."""
        assert parser.language == "bash"
        assert parser.parser is None

    def test_setup_parser(self, parser):
        """Test parser setup."""
        parser.setup_parser()
        assert parser.parser is not None

    def test_extract_function(self, parser):
        """Test extracting a simple function."""
        content = """#!/bin/bash

# This is a greeting function
greet() {
    echo "Hello, $1"
}

# Main function
main() {
    greet "World"
}

main
"""
        tree = parser.parse_file("test.sh", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.sh", content)

        # Should extract two functions
        assert len(symbols) == 2

        # Check greet function
        greet_symbol = next((s for s in symbols if s.name == "greet"), None)
        assert greet_symbol is not None
        assert greet_symbol.type == SymbolType.FUNCTION
        assert greet_symbol.language == "bash"
        assert greet_symbol.docstring == "This is a greeting function"

        # Check main function
        main_symbol = next((s for s in symbols if s.name == "main"), None)
        assert main_symbol is not None
        assert main_symbol.type == SymbolType.FUNCTION
        assert main_symbol.docstring == "Main function"

    def test_extract_dependencies(self, parser):
        """Test extracting dependencies."""
        content = """#!/bin/bash

source ./utils.sh

helper() {
    echo "Helper"
}

main() {
    helper
}
"""
        tree = parser.parse_file("test.sh", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.sh", content)
        dependencies = parser.extract_dependencies(tree, symbols, "test.sh", content)

        # Should have source dependency
        source_deps = [d for d in dependencies if d.relationship_type == "sources"]
        assert len(source_deps) > 0
        assert any("utils.sh" in d.to_symbol_id for d in source_deps)

    def test_empty_file(self, parser):
        """Test parsing an empty file."""
        content = ""
        tree = parser.parse_file("empty.sh", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "empty.sh", content)
        assert len(symbols) == 0

    def test_function_without_comment(self, parser):
        """Test extracting function without documentation."""
        content = """#!/bin/bash

simple_func() {
    echo "Simple"
}
"""
        tree = parser.parse_file("test.sh", content)
        assert tree is not None

        symbols = parser.extract_symbols(tree, "test.sh", content)
        assert len(symbols) == 1
        assert symbols[0].name == "simple_func"
        assert symbols[0].docstring is None


# Made with Bob
