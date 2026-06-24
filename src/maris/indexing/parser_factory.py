"""Factory for creating language-specific parsers."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from maris.indexing.parser import TreeSitterParser
from maris.indexing.python_parser import PythonParser
from maris.indexing.java_parser import JavaParser
from maris.indexing.scala_parser import ScalaParser
from maris.indexing.bash_parser import BashParser
from maris.indexing.javascript_parser import JavaScriptParser
from maris.indexing.typescript_parser import TypeScriptParser
from maris.indexing.config_parser import ConfigParser
from maris.indexing.markdown_parser import MarkdownParser


class ParserFactory:
    """
    Factory for creating language-specific Tree-sitter parsers.

    This factory maps file extensions to parser classes and provides
    methods to get the appropriate parser for a given file.
    """

    # Mapping of file extensions to parser class names
    _EXTENSION_MAP: Dict[str, str] = {
        ".py": "PythonParser",
        ".java": "JavaParser",
        ".scala": "ScalaParser",
        ".kt": "KotlinParser",
        ".kts": "KotlinParser",  # Kotlin script
        ".js": "JavaScriptParser",
        ".jsx": "JavaScriptParser",
        ".ts": "TypeScriptParser",
        ".tsx": "TypeScriptParser",
        ".go": "GoParser",
        ".sh": "ShellParser",
        ".bash": "ShellParser",
        ".rs": "RustParser",
        ".yaml": "ConfigParser",
        ".yml": "ConfigParser",
        ".json": "ConfigParser",
        ".toml": "ConfigParser",
        ".ini": "ConfigParser",
        ".md": "MarkdownParser",
    }

    # Mapping of language names to parser classes
    _PARSER_REGISTRY: Dict[str, Type[TreeSitterParser]] = {
        "PythonParser": PythonParser,
        "JavaParser": JavaParser,
        "ScalaParser": ScalaParser,
        "ShellParser": BashParser,
        "JavaScriptParser": JavaScriptParser,
        "TypeScriptParser": TypeScriptParser,
        "ConfigParser": ConfigParser,
        "MarkdownParser": MarkdownParser,
        # Additional parsers will be registered as they are implemented
        # 'KotlinParser': KotlinParser,
        # 'GoParser': GoParser,
        # 'RustParser': RustParser,
    }

    @classmethod
    def get_parser(cls, file_path: str) -> Optional[TreeSitterParser]:
        """
        Get the appropriate parser for a file based on its extension.

        Args:
            file_path: Path to the source file

        Returns:
            Parser instance or None if language is not supported

        Example:
            >>> parser = ParserFactory.get_parser("src/main.py")
            >>> if parser:
            ...     tree = parser.parse_file("src/main.py", content)
        """
        extension = Path(file_path).suffix.lower()
        parser_name = cls._EXTENSION_MAP.get(extension)

        if not parser_name:
            return None

        parser_class = cls._PARSER_REGISTRY.get(parser_name)
        if not parser_class:
            # Parser not yet implemented
            return None

        return parser_class()

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """
        Get list of all supported file extensions.

        Returns:
            List of file extensions (e.g., ['.py', '.java', '.scala'])

        Example:
            >>> extensions = ParserFactory.get_supported_extensions()
            >>> print(extensions)
            ['.py', '.java', '.scala', ...]
        """
        return sorted(cls._EXTENSION_MAP.keys())

    @classmethod
    def get_implemented_extensions(cls) -> List[str]:
        """
        Get list of file extensions with implemented parsers.

        Returns:
            List of file extensions that have working parsers

        Example:
            >>> extensions = ParserFactory.get_implemented_extensions()
            >>> print(extensions)
            ['.py']  # Only Python is implemented initially
        """
        implemented = []
        for ext, parser_name in cls._EXTENSION_MAP.items():
            if parser_name in cls._PARSER_REGISTRY:
                implemented.append(ext)
        return sorted(implemented)

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """
        Check if a file extension is supported (planned or implemented).

        Args:
            file_path: Path to the source file

        Returns:
            True if the file extension is in the extension map

        Example:
            >>> ParserFactory.is_supported("main.py")
            True
            >>> ParserFactory.is_supported("main.txt")
            False
        """
        extension = Path(file_path).suffix.lower()
        return extension in cls._EXTENSION_MAP

    @classmethod
    def is_implemented(cls, file_path: str) -> bool:
        """
        Check if a file extension has an implemented parser.

        Args:
            file_path: Path to the source file

        Returns:
            True if the parser is implemented and available

        Example:
            >>> ParserFactory.is_implemented("main.py")
            True
            >>> ParserFactory.is_implemented("main.java")
            False  # Not yet implemented
        """
        extension = Path(file_path).suffix.lower()
        parser_name = cls._EXTENSION_MAP.get(extension)
        if not parser_name:
            return False
        return parser_name in cls._PARSER_REGISTRY

    @classmethod
    def get_language_name(cls, file_path: str) -> Optional[str]:
        """
        Get the language name for a file.

        Args:
            file_path: Path to the source file

        Returns:
            Language name (e.g., "python", "java") or None

        Example:
            >>> ParserFactory.get_language_name("main.py")
            'python'
            >>> ParserFactory.get_language_name("Main.java")
            'java'
        """
        extension = Path(file_path).suffix.lower()

        # Map extensions to language names
        language_map = {
            ".py": "python",
            ".java": "java",
            ".scala": "scala",
            ".kt": "kotlin",
            ".kts": "kotlin",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".sh": "bash",
            ".bash": "bash",
            ".rs": "rust",
            ".yaml": "config",
            ".yml": "config",
            ".json": "config",
            ".toml": "config",
            ".ini": "config",
            ".md": "markdown",
        }

        return language_map.get(extension)

    @classmethod
    def register_parser(cls, parser_name: str, parser_class: Type[TreeSitterParser]) -> None:
        """
        Register a new parser class.

        This method allows dynamic registration of parser implementations,
        useful for plugins or extensions.

        Args:
            parser_name: Name of the parser (e.g., "JavaParser")
            parser_class: Parser class that inherits from TreeSitterParser

        Example:
            >>> class JavaParser(TreeSitterParser):
            ...     pass
            >>> ParserFactory.register_parser("JavaParser", JavaParser)
        """
        if not issubclass(parser_class, TreeSitterParser):
            raise ValueError(f"{parser_class} must inherit from TreeSitterParser")

        cls._PARSER_REGISTRY[parser_name] = parser_class

    @classmethod
    def get_parser_status(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all parsers (planned vs implemented).

        Returns:
            Dictionary mapping languages to their status

        Example:
            >>> status = ParserFactory.get_parser_status()
            >>> print(status)
            {
                'python': {'implemented': True, 'extensions': ['.py']},
                'java': {'implemented': False, 'extensions': ['.java']},
                ...
            }
        """
        status = {}

        # Group extensions by language
        language_extensions: Dict[str, List[str]] = {}
        for ext, parser_name in cls._EXTENSION_MAP.items():
            lang = cls.get_language_name(f"file{ext}")
            if lang:
                if lang not in language_extensions:
                    language_extensions[lang] = []
                language_extensions[lang].append(ext)

        # Build status for each language
        for lang, extensions in sorted(language_extensions.items()):
            # Check if any extension for this language is implemented
            parser_name = cls._EXTENSION_MAP.get(extensions[0]) if extensions else None
            implemented = parser_name in cls._PARSER_REGISTRY if parser_name else False

            status[lang] = {
                "implemented": implemented,
                "extensions": sorted(extensions),
                "parser_class": parser_name if implemented else None,
            }

        return status


# Made with Bob
