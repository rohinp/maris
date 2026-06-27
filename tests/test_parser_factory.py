"""Tests for ParserFactory."""

import pytest

from maris.indexing.parser import TreeSitterParser
from maris.indexing.parser_factory import ParserFactory
from maris.indexing.python_parser import PythonParser


class TestParserFactory:
    """Test suite for ParserFactory."""

    def test_get_parser_python(self):
        """Test getting Python parser."""
        parser = ParserFactory.get_parser("test.py")
        assert parser is not None
        assert isinstance(parser, PythonParser)
        assert parser.language == "python"

    def test_get_parser_unsupported_extension(self):
        """Test getting parser for unsupported extension."""
        parser = ParserFactory.get_parser("test.txt")
        assert parser is None

    def test_get_parser_unimplemented_language(self):
        """Test getting parser for planned but unimplemented language."""
        # Kotlin is planned but not yet implemented
        parser = ParserFactory.get_parser("Test.kt")
        assert parser is None

    def test_get_supported_extensions(self):
        """Test getting all supported extensions."""
        extensions = ParserFactory.get_supported_extensions()

        assert isinstance(extensions, list)
        assert len(extensions) > 0
        assert ".py" in extensions
        assert ".java" in extensions
        assert ".scala" in extensions
        assert ".kt" in extensions
        assert ".js" in extensions
        assert ".ts" in extensions
        assert ".go" in extensions
        assert ".sh" in extensions
        assert ".rs" in extensions

        # Should be sorted
        assert extensions == sorted(extensions)

    def test_get_implemented_extensions(self):
        """Test getting only implemented extensions."""
        extensions = ParserFactory.get_implemented_extensions()

        assert isinstance(extensions, list)
        assert ".py" in extensions  # Python is implemented

        # Should be sorted
        assert extensions == sorted(extensions)

    def test_is_supported(self):
        """Test checking if file extension is supported."""
        # Supported (planned)
        assert ParserFactory.is_supported("main.py") is True
        assert ParserFactory.is_supported("Main.java") is True
        assert ParserFactory.is_supported("app.scala") is True
        assert ParserFactory.is_supported("App.kt") is True
        assert ParserFactory.is_supported("app.js") is True
        assert ParserFactory.is_supported("app.ts") is True
        assert ParserFactory.is_supported("main.go") is True
        assert ParserFactory.is_supported("script.sh") is True
        assert ParserFactory.is_supported("main.rs") is True

        # Not supported
        assert ParserFactory.is_supported("readme.txt") is False
        assert ParserFactory.is_supported("data.csv") is False

    def test_is_implemented(self):
        """Test checking if parser is implemented."""
        # Implemented
        assert ParserFactory.is_implemented("main.py") is True
        assert ParserFactory.is_implemented("Main.java") is True
        assert ParserFactory.is_implemented("app.scala") is True

        # Planned but not implemented
        assert ParserFactory.is_implemented("App.kt") is False

        # Not supported at all
        assert ParserFactory.is_implemented("readme.txt") is False

    def test_get_language_name(self):
        """Test getting language name from file path."""
        assert ParserFactory.get_language_name("main.py") == "python"
        assert ParserFactory.get_language_name("Main.java") == "java"
        assert ParserFactory.get_language_name("app.scala") == "scala"
        assert ParserFactory.get_language_name("App.kt") == "kotlin"
        assert ParserFactory.get_language_name("App.kts") == "kotlin"
        assert ParserFactory.get_language_name("app.js") == "javascript"
        assert ParserFactory.get_language_name("app.jsx") == "javascript"
        assert ParserFactory.get_language_name("app.ts") == "typescript"
        assert ParserFactory.get_language_name("app.tsx") == "typescript"
        assert ParserFactory.get_language_name("main.go") == "go"
        assert ParserFactory.get_language_name("script.sh") == "bash"
        assert ParserFactory.get_language_name("script.bash") == "bash"
        assert ParserFactory.get_language_name("main.rs") == "rust"
        assert ParserFactory.get_language_name("readme.txt") is None

    def test_get_language_name_case_insensitive(self):
        """Test that language detection is case-insensitive."""
        assert ParserFactory.get_language_name("Main.PY") == "python"
        assert ParserFactory.get_language_name("Main.JAVA") == "java"
        assert ParserFactory.get_language_name("App.KT") == "kotlin"

    def test_get_language_name_with_path(self):
        """Test language detection with full paths."""
        assert ParserFactory.get_language_name("src/main/python/app.py") == "python"
        assert ParserFactory.get_language_name("/usr/local/bin/script.sh") == "bash"
        assert ParserFactory.get_language_name("C:\\Users\\test\\Main.java") == "java"

    def test_register_parser(self):
        """Test registering a custom parser."""

        # Create a mock parser class
        class MockParser(TreeSitterParser):
            def __init__(self):
                super().__init__("mock")

            def setup_parser(self):
                pass

            def extract_symbols(self, tree, file_path, content):
                return []

            def extract_dependencies(self, tree, symbols, file_path, content):
                return []

        # Register the parser
        ParserFactory.register_parser("MockParser", MockParser)

        # Verify it's registered
        assert "MockParser" in ParserFactory._PARSER_REGISTRY
        assert ParserFactory._PARSER_REGISTRY["MockParser"] == MockParser

    def test_register_parser_invalid_class(self):
        """Test that registering invalid parser class raises error."""

        class NotAParser:
            pass

        with pytest.raises(ValueError, match="must inherit from TreeSitterParser"):
            ParserFactory.register_parser("NotAParser", NotAParser)

    def test_get_parser_status(self):
        """Test getting parser implementation status."""
        status = ParserFactory.get_parser_status()

        assert isinstance(status, dict)
        assert len(status) > 0

        # Check Python status
        assert "python" in status
        python_status = status["python"]
        assert python_status["implemented"] is True
        assert ".py" in python_status["extensions"]
        assert python_status["parser_class"] == "PythonParser"

        # Check Java status (now implemented)
        assert "java" in status
        java_status = status["java"]
        assert java_status["implemented"] is True
        assert ".java" in java_status["extensions"]
        assert java_status["parser_class"] == "JavaParser"

        # Check Scala status (now implemented)
        assert "scala" in status
        scala_status = status["scala"]
        assert scala_status["implemented"] is True
        assert ".scala" in scala_status["extensions"]
        assert scala_status["parser_class"] == "ScalaParser"

        # Check Kotlin status (planned but not implemented)
        assert "kotlin" in status
        kotlin_status = status["kotlin"]
        assert kotlin_status["implemented"] is False
        assert ".kt" in kotlin_status["extensions"]
        assert kotlin_status["parser_class"] is None

    def test_get_parser_status_all_languages(self):
        """Test that all planned languages are in status."""
        status = ParserFactory.get_parser_status()

        expected_languages = [
            "python",
            "java",
            "scala",
            "kotlin",
            "javascript",
            "typescript",
            "go",
            "bash",
            "rust",
        ]

        for lang in expected_languages:
            assert lang in status, f"Language {lang} not in status"
            assert "implemented" in status[lang]
            assert "extensions" in status[lang]
            assert "parser_class" in status[lang]

    def test_multiple_extensions_same_language(self):
        """Test languages with multiple file extensions."""
        # Kotlin has .kt and .kts
        assert ParserFactory.get_language_name("App.kt") == "kotlin"
        assert ParserFactory.get_language_name("script.kts") == "kotlin"

        # JavaScript has .js and .jsx
        assert ParserFactory.get_language_name("app.js") == "javascript"
        assert ParserFactory.get_language_name("component.jsx") == "javascript"

        # TypeScript has .ts and .tsx
        assert ParserFactory.get_language_name("app.ts") == "typescript"
        assert ParserFactory.get_language_name("component.tsx") == "typescript"

        # Bash has .sh and .bash
        assert ParserFactory.get_language_name("script.sh") == "bash"
        assert ParserFactory.get_language_name("script.bash") == "bash"

    def test_parser_instance_independence(self):
        """Test that multiple parser instances are independent."""
        parser1 = ParserFactory.get_parser("test1.py")
        parser2 = ParserFactory.get_parser("test2.py")

        assert parser1 is not None
        assert parser2 is not None
        assert parser1 is not parser2  # Different instances

    def test_extension_map_completeness(self):
        """Test that all extensions in map have corresponding language names."""
        for ext in ParserFactory._EXTENSION_MAP.keys():
            lang = ParserFactory.get_language_name(f"test{ext}")
            assert lang is not None, f"Extension {ext} has no language mapping"

    def test_supported_vs_implemented(self):
        """Test relationship between supported and implemented extensions."""
        supported = set(ParserFactory.get_supported_extensions())
        implemented = set(ParserFactory.get_implemented_extensions())

        # Implemented should be subset of supported
        assert implemented.issubset(supported)

        # Python should be in both
        assert ".py" in supported
        assert ".py" in implemented


class TestParserFactoryIntegration:
    """Integration tests for ParserFactory with actual parsers."""

    def test_python_parser_integration(self):
        """Test that Python parser from factory works correctly."""
        parser = ParserFactory.get_parser("test.py")
        assert parser is not None

        # Test parsing simple Python code
        code = """
class TestClass:
    def test_method(self):
        pass

def test_function():
    pass
"""
        tree = parser.parse_file("test.py", code)
        assert tree is not None

        # Extract symbols
        symbols = parser.extract_symbols(tree, "test.py", code)
        assert len(symbols) > 0

        # Should find class and functions
        symbol_names = [s.name for s in symbols]
        assert "TestClass" in symbol_names
        assert "test_method" in symbol_names
        assert "test_function" in symbol_names

    def test_factory_with_real_file_paths(self):
        """Test factory with realistic file paths."""
        test_cases = [
            ("src/main.py", "python", True),
            ("src/com/example/Main.java", "java", True),
        ("src/main/scala/App.scala", "scala", True),
        ("src/App.kt", "kotlin", False),
        ("src/index.js", "javascript", True),
        ("src/index.ts", "typescript", True),
        ("cmd/main.go", "go", False),
        ("scripts/deploy.sh", "bash", True),
        ("src/main.rs", "rust", False),
        ]

        for file_path, expected_lang, should_have_parser in test_cases:
            lang = ParserFactory.get_language_name(file_path)
            assert lang == expected_lang, f"Wrong language for {file_path}"

            parser = ParserFactory.get_parser(file_path)
            if should_have_parser:
                assert parser is not None, f"Should have parser for {file_path}"
            else:
                assert parser is None, f"Should not have parser yet for {file_path}"


# Made with Bob
