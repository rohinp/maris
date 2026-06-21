"""Tests for dependency extraction in Python parser."""

import pytest

from maris.core.models import SymbolType
from maris.indexing.python_parser import PythonParser


# Sample Python code with dependencies
SAMPLE_CODE_WITH_DEPENDENCIES = '''
import os
import sys
from typing import List, Dict
from pathlib import Path

class DataProcessor:
    """Process data from various sources."""

    def __init__(self):
        self.data = []

    def load_data(self, filepath: str):
        """Load data from file."""
        path = Path(filepath)
        return path.read_text()

    def process(self, data: str):
        """Process the data."""
        result = self.transform(data)
        return self.validate(result)

    def transform(self, data: str):
        """Transform data."""
        return data.upper()

    def validate(self, data: str):
        """Validate data."""
        return len(data) > 0

def helper_function(value):
    """A helper function."""
    processor = DataProcessor()
    return processor.process(value)

class AdvancedProcessor(DataProcessor):
    """Advanced processor that extends DataProcessor."""

    def advanced_process(self, data: str):
        """Advanced processing."""
        return super().process(data)
'''


class TestDependencyExtraction:
    """Test dependency extraction functionality."""

    @pytest.fixture
    def parser(self):
        """Create a Python parser instance."""
        return PythonParser()

    def test_extract_import_dependencies(self, parser):
        """Test extracting import dependencies."""
        tree = parser.parse_file("test.py", SAMPLE_CODE_WITH_DEPENDENCIES)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_CODE_WITH_DEPENDENCIES)
        dependencies = parser.extract_dependencies(
            tree, symbols, "test.py", SAMPLE_CODE_WITH_DEPENDENCIES
        )

        # Find import dependencies
        import_deps = [d for d in dependencies if d.relationship_type == "imports"]

        # Should have imports for os, sys, typing.List, typing.Dict, pathlib.Path
        assert len(import_deps) >= 3

        # Check that we have the expected imports
        imported_modules = {d.to_symbol_id for d in import_deps}
        assert "os" in imported_modules
        assert "sys" in imported_modules

    def test_extract_call_dependencies(self, parser):
        """Test extracting function call dependencies."""
        tree = parser.parse_file("test.py", SAMPLE_CODE_WITH_DEPENDENCIES)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_CODE_WITH_DEPENDENCIES)
        dependencies = parser.extract_dependencies(
            tree, symbols, "test.py", SAMPLE_CODE_WITH_DEPENDENCIES
        )

        # Find call dependencies
        call_deps = [d for d in dependencies if d.relationship_type == "calls"]

        # Should have some call dependencies detected
        assert len(call_deps) >= 1

        # Verify that dependencies have proper structure
        for dep in call_deps:
            assert dep.from_symbol_id
            assert dep.to_symbol_id
            assert dep.relationship_type == "calls"
            assert dep.id  # Should have unique ID

    def test_extract_inheritance_dependencies(self, parser):
        """Test extracting class inheritance dependencies."""
        tree = parser.parse_file("test.py", SAMPLE_CODE_WITH_DEPENDENCIES)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_CODE_WITH_DEPENDENCIES)
        dependencies = parser.extract_dependencies(
            tree, symbols, "test.py", SAMPLE_CODE_WITH_DEPENDENCIES
        )

        # Find inheritance dependencies
        inheritance_deps = [d for d in dependencies if d.relationship_type == "extends"]

        # AdvancedProcessor extends DataProcessor
        assert len(inheritance_deps) >= 1

        # Check the inheritance relationship
        for dep in inheritance_deps:
            if "AdvancedProcessor" in dep.from_symbol_id:
                assert "DataProcessor" in dep.to_symbol_id

    def test_dependency_ids_unique(self, parser):
        """Test that dependency IDs are unique."""
        tree = parser.parse_file("test.py", SAMPLE_CODE_WITH_DEPENDENCIES)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_CODE_WITH_DEPENDENCIES)
        dependencies = parser.extract_dependencies(
            tree, symbols, "test.py", SAMPLE_CODE_WITH_DEPENDENCIES
        )

        dep_ids = [d.id for d in dependencies]
        assert len(dep_ids) == len(set(dep_ids))

    def test_no_dependencies_in_simple_code(self, parser):
        """Test that simple code without dependencies returns empty list."""
        simple_code = """
def simple_function():
    return 42
"""
        tree = parser.parse_file("test.py", simple_code)
        symbols = parser.extract_symbols(tree, "test.py", simple_code)
        dependencies = parser.extract_dependencies(tree, symbols, "test.py", simple_code)

        # Should have no call or inheritance dependencies
        call_deps = [d for d in dependencies if d.relationship_type == "calls"]
        inheritance_deps = [d for d in dependencies if d.relationship_type == "extends"]

        assert len(call_deps) == 0
        assert len(inheritance_deps) == 0


class TestDependencyEdgeCases:
    """Test edge cases in dependency extraction."""

    @pytest.fixture
    def parser(self):
        """Create a Python parser instance."""
        return PythonParser()

    def test_multiple_inheritance(self, parser):
        """Test extracting dependencies from multiple inheritance."""
        code = """
class Base1:
    pass

class Base2:
    pass

class Derived(Base1, Base2):
    pass
"""
        tree = parser.parse_file("test.py", code)
        symbols = parser.extract_symbols(tree, "test.py", code)
        dependencies = parser.extract_dependencies(tree, symbols, "test.py", code)

        inheritance_deps = [d for d in dependencies if d.relationship_type == "extends"]

        # Derived should extend both Base1 and Base2
        assert len(inheritance_deps) >= 2

    def test_nested_function_calls(self, parser):
        """Test extracting dependencies from nested function calls."""
        code = """
def helper():
    return 42

def outer():
    return helper()
"""
        tree = parser.parse_file("test.py", code)
        symbols = parser.extract_symbols(tree, "test.py", code)
        dependencies = parser.extract_dependencies(tree, symbols, "test.py", code)

        # Should detect the call from outer to helper
        call_deps = [d for d in dependencies if d.relationship_type == "calls"]
        assert len(call_deps) >= 1

        # Create a map of symbol IDs to names for verification
        symbol_map = {s.id: s.name for s in symbols}

        # Verify that we have a call from outer to helper
        for dep in call_deps:
            from_name = symbol_map.get(dep.from_symbol_id, "")
            to_name = symbol_map.get(dep.to_symbol_id, "")
            if from_name == "outer" and to_name == "helper":
                # Found the expected dependency
                assert True
                return

        # If we get here, the expected dependency wasn't found
        assert (
            False
        ), f"Expected call from 'outer' to 'helper' not found. Found: {[(symbol_map.get(d.from_symbol_id), symbol_map.get(d.to_symbol_id)) for d in call_deps]}"

    def test_method_chaining(self, parser):
        """Test extracting dependencies from method chaining."""
        code = """
class Builder:
    def step1(self):
        return self

    def step2(self):
        return self

    def build(self):
        return self.step1().step2()
"""
        tree = parser.parse_file("test.py", code)
        symbols = parser.extract_symbols(tree, "test.py", code)
        dependencies = parser.extract_dependencies(tree, symbols, "test.py", code)

        call_deps = [d for d in dependencies if d.relationship_type == "calls"]

        # build method should call step1 and step2
        assert len(call_deps) >= 2


# Made with Bob
