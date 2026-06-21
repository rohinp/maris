"""Tests for Python parser."""

import pytest

from maris.core.models import SymbolType
from maris.indexing.python_parser import PythonParser


# Sample Python code for testing
SAMPLE_PYTHON_CODE = '''
"""Module docstring."""

MAX_RETRIES = 3
API_TIMEOUT = 30

class Calculator:
    """A simple calculator class."""

    def __init__(self):
        """Initialize the calculator."""
        self.result = 0

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    def subtract(self, a, b):
        """Subtract b from a."""
        return a - b

def multiply(x, y):
    """Multiply two numbers."""
    return x * y

def divide(numerator, denominator):
    """
    Divide numerator by denominator.

    Args:
        numerator: The number to divide
        denominator: The number to divide by

    Returns:
        The result of division
    """
    if denominator == 0:
        raise ValueError("Cannot divide by zero")
    return numerator / denominator
'''


class TestPythonParser:
    """Test suite for Python parser."""

    @pytest.fixture
    def parser(self):
        """Create a Python parser instance."""
        return PythonParser()

    def test_parser_initialization(self, parser):
        """Test that parser initializes correctly."""
        assert parser.language == "python"
        assert parser.parser is None  # Not set up yet

    def test_parser_setup(self, parser):
        """Test that parser sets up correctly."""
        parser.setup_parser()
        assert parser.parser is not None

    def test_parse_file(self, parser):
        """Test parsing a Python file."""
        tree = parser.parse_file("test.py", SAMPLE_PYTHON_CODE)
        assert tree is not None
        assert tree.root_node is not None

    def test_extract_classes(self, parser):
        """Test extracting class symbols."""
        tree = parser.parse_file("test.py", SAMPLE_PYTHON_CODE)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_PYTHON_CODE)

        # Find the Calculator class
        classes = [s for s in symbols if s.type == SymbolType.CLASS]
        assert len(classes) == 1

        calc_class = classes[0]
        assert calc_class.name == "Calculator"
        assert calc_class.docstring == "A simple calculator class."
        assert calc_class.file_path == "test.py"
        assert calc_class.language == "python"

    def test_extract_methods(self, parser):
        """Test extracting method symbols."""
        tree = parser.parse_file("test.py", SAMPLE_PYTHON_CODE)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_PYTHON_CODE)

        # Find methods
        methods = [s for s in symbols if s.type == SymbolType.METHOD]
        assert len(methods) == 3  # __init__, add, subtract

        method_names = {m.name for m in methods}
        assert "__init__" in method_names
        assert "add" in method_names
        assert "subtract" in method_names

        # Check that methods have parent_id set
        for method in methods:
            assert method.parent_id is not None

    def test_extract_functions(self, parser):
        """Test extracting function symbols."""
        tree = parser.parse_file("test.py", SAMPLE_PYTHON_CODE)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_PYTHON_CODE)

        # Find top-level functions
        functions = [s for s in symbols if s.type == SymbolType.FUNCTION]
        assert len(functions) == 2  # multiply, divide

        function_names = {f.name for f in functions}
        assert "multiply" in function_names
        assert "divide" in function_names

        # Check that functions don't have parent_id
        for func in functions:
            assert func.parent_id is None

    def test_extract_constants(self, parser):
        """Test extracting constant symbols."""
        tree = parser.parse_file("test.py", SAMPLE_PYTHON_CODE)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_PYTHON_CODE)

        # Find constants
        constants = [s for s in symbols if s.type == SymbolType.CONSTANT]
        assert len(constants) == 2  # MAX_RETRIES, API_TIMEOUT

        constant_names = {c.name for c in constants}
        assert "MAX_RETRIES" in constant_names
        assert "API_TIMEOUT" in constant_names

    def test_function_signatures(self, parser):
        """Test that function signatures are extracted."""
        tree = parser.parse_file("test.py", SAMPLE_PYTHON_CODE)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_PYTHON_CODE)

        # Find the multiply function
        multiply_func = next(s for s in symbols if s.name == "multiply")
        assert multiply_func.signature is not None
        assert "def multiply" in multiply_func.signature
        assert "x" in multiply_func.signature
        assert "y" in multiply_func.signature

    def test_docstring_extraction(self, parser):
        """Test that docstrings are extracted correctly."""
        tree = parser.parse_file("test.py", SAMPLE_PYTHON_CODE)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_PYTHON_CODE)

        # Check class docstring
        calc_class = next(s for s in symbols if s.name == "Calculator")
        assert calc_class.docstring == "A simple calculator class."

        # Check method docstring
        add_method = next(s for s in symbols if s.name == "add")
        assert add_method.docstring == "Add two numbers."

        # Check function docstring (multi-line)
        divide_func = next(s for s in symbols if s.name == "divide")
        assert divide_func.docstring is not None
        assert "Divide numerator by denominator" in divide_func.docstring

    def test_line_numbers(self, parser):
        """Test that line numbers are correct."""
        tree = parser.parse_file("test.py", SAMPLE_PYTHON_CODE)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_PYTHON_CODE)

        # All symbols should have valid line numbers
        for symbol in symbols:
            assert symbol.start_line > 0
            assert symbol.end_line >= symbol.start_line

    def test_symbol_ids_unique(self, parser):
        """Test that symbol IDs are unique."""
        tree = parser.parse_file("test.py", SAMPLE_PYTHON_CODE)
        symbols = parser.extract_symbols(tree, "test.py", SAMPLE_PYTHON_CODE)

        symbol_ids = [s.id for s in symbols]
        assert len(symbol_ids) == len(set(symbol_ids))  # All unique

    def test_empty_file(self, parser):
        """Test parsing an empty file."""
        tree = parser.parse_file("empty.py", "")
        symbols = parser.extract_symbols(tree, "empty.py", "")
        assert len(symbols) == 0

    def test_file_with_only_comments(self, parser):
        """Test parsing a file with only comments."""
        code = "# This is a comment\n# Another comment\n"
        tree = parser.parse_file("comments.py", code)
        symbols = parser.extract_symbols(tree, "comments.py", code)
        assert len(symbols) == 0

    def test_nested_functions(self, parser):
        """Test that nested functions are not extracted as top-level."""
        code = """
def outer():
    def inner():
        pass
    return inner
"""
        tree = parser.parse_file("nested.py", code)
        symbols = parser.extract_symbols(tree, "nested.py", code)

        # Should only extract outer function
        functions = [s for s in symbols if s.type == SymbolType.FUNCTION]
        assert len(functions) == 1
        assert functions[0].name == "outer"


class TestPythonParserEdgeCases:
    """Test edge cases for Python parser."""

    @pytest.fixture
    def parser(self):
        """Create a Python parser instance."""
        return PythonParser()

    def test_class_without_docstring(self, parser):
        """Test class without docstring."""
        code = """
class MyClass:
    pass
"""
        tree = parser.parse_file("test.py", code)
        symbols = parser.extract_symbols(tree, "test.py", code)

        classes = [s for s in symbols if s.type == SymbolType.CLASS]
        assert len(classes) == 1
        assert classes[0].docstring is None

    def test_function_without_parameters(self, parser):
        """Test function without parameters."""
        code = '''
def no_params():
    """Function with no parameters."""
    return 42
'''
        tree = parser.parse_file("test.py", code)
        symbols = parser.extract_symbols(tree, "test.py", code)

        functions = [s for s in symbols if s.type == SymbolType.FUNCTION]
        assert len(functions) == 1
        assert "no_params" in functions[0].signature

    def test_lowercase_variable_not_constant(self, parser):
        """Test that lowercase variables are not treated as constants."""
        code = """
max_value = 100
MIN_VALUE = 10
"""
        tree = parser.parse_file("test.py", code)
        symbols = parser.extract_symbols(tree, "test.py", code)

        constants = [s for s in symbols if s.type == SymbolType.CONSTANT]
        assert len(constants) == 1
        assert constants[0].name == "MIN_VALUE"

    def test_single_letter_uppercase_not_constant(self, parser):
        """Test that single uppercase letters are not treated as constants."""
        code = """
X = 1
Y = 2
REAL_CONSTANT = 3
"""
        tree = parser.parse_file("test.py", code)
        symbols = parser.extract_symbols(tree, "test.py", code)

        constants = [s for s in symbols if s.type == SymbolType.CONSTANT]
        # Should only get REAL_CONSTANT (more than 1 character)
        assert len(constants) == 1
        assert constants[0].name == "REAL_CONSTANT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
