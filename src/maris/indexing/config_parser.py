"""Configuration file parser for YAML, JSON, TOML, and INI files."""

import json
from typing import Any, List, Optional

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None  # type: ignore

try:
    import toml

    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False
    toml = None  # type: ignore

from configparser import ConfigParser as IniConfigParser

from maris.core.models import Dependency, Symbol, SymbolType
from maris.indexing.parser import TreeSitterParser


class ConfigParser(TreeSitterParser):
    """
    Parser for configuration files (YAML, JSON, TOML, INI).

    This parser extracts configuration keys and values as symbols,
    making them searchable and queryable for infrastructure and
    system-related questions.
    """

    def __init__(self):
        """Initialize the Config parser."""
        super().__init__("config")

    def setup_parser(self) -> None:
        """
        Config parser doesn't use tree-sitter.

        This method is required by the base class but does nothing
        since we parse config files directly.
        """
        # Config files don't need tree-sitter parsing
        self.parser = None

    def parse_file(self, file_path: str, content: str) -> Any:  # type: ignore[override]
        """
        Parse a configuration file.

        Args:
            file_path: Path to the config file
            content: File content

        Returns:
            Parsed configuration as a dictionary or None if parsing fails
        """
        file_path_lower = file_path.lower()

        try:
            if file_path_lower.endswith((".yaml", ".yml")):
                return self._parse_yaml(content)
            elif file_path_lower.endswith(".json"):
                return self._parse_json(content)
            elif file_path_lower.endswith(".toml"):
                return self._parse_toml(content)
            elif file_path_lower.endswith(".ini"):
                return self._parse_ini(content)
            else:
                return None
        except Exception as e:
            print(f"Error parsing config file {file_path}: {e}")
            return None

    def _parse_yaml(self, content: str) -> Optional[dict]:
        """Parse YAML content."""
        if not YAML_AVAILABLE or yaml is None:
            print("PyYAML not installed. Install with: pip install pyyaml")
            return None
        return yaml.safe_load(content)  # type: ignore

    def _parse_json(self, content: str) -> Optional[dict]:
        """Parse JSON content."""
        return json.loads(content)

    def _parse_toml(self, content: str) -> Optional[dict]:
        """Parse TOML content."""
        if not TOML_AVAILABLE or toml is None:
            print("toml not installed. Install with: pip install toml")
            return None
        return toml.loads(content)  # type: ignore

    def _parse_ini(self, content: str) -> Optional[dict]:
        """Parse INI content."""
        parser = IniConfigParser()
        parser.read_string(content)

        # Convert to nested dict
        result = {}
        for section in parser.sections():
            result[section] = dict(parser.items(section))
        return result

    def extract_symbols(self, tree: Any, file_path: str, content: str) -> List[Symbol]:  # type: ignore[override]
        """
        Extract configuration keys as symbols.

        Args:
            tree: Parsed configuration dictionary
            file_path: Relative path to the config file
            content: File content

        Returns:
            List of extracted symbols (configuration keys)
        """
        if tree is None:
            return []

        symbols = []
        self._extract_keys_recursive(tree, file_path, "", symbols, content)
        return symbols

    def _extract_keys_recursive(
        self,
        data: dict,
        file_path: str,
        prefix: str,
        symbols: List[Symbol],
        content: str,
        depth: int = 0,
    ) -> None:
        """
        Recursively extract configuration keys.

        Args:
            data: Configuration data (dict or value)
            file_path: File path
            prefix: Key prefix for nested keys
            symbols: List to append symbols to
            content: File content
            depth: Current nesting depth
        """
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            # Determine the line number by searching in content
            line_number = self._find_key_line(content, key, depth)

            # Create symbol for this key
            symbol_id = self.generate_symbol_id(file_path, full_key, line_number)

            # Determine symbol type based on value
            if isinstance(value, dict):
                symbol_type = SymbolType.CLASS  # Treat sections as classes
                docstring = f"Configuration section: {full_key}"
            else:
                symbol_type = SymbolType.CONSTANT  # Treat values as constants
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                docstring = f"Configuration value: {value_str}"

            symbols.append(
                Symbol(
                    id=symbol_id,
                    name=full_key,
                    type=symbol_type,
                    file_path=file_path,
                    language=self.language,
                    start_line=line_number,
                    end_line=line_number,
                    docstring=docstring,
                )
            )

            # Recursively process nested dictionaries
            if isinstance(value, dict):
                self._extract_keys_recursive(
                    value, file_path, full_key, symbols, content, depth + 1
                )

    def _find_key_line(self, content: str, key: str, depth: int) -> int:
        """
        Find the line number where a key appears in the content.

        Args:
            content: File content
            key: Key to search for
            depth: Nesting depth (for indentation hints)

        Returns:
            Line number (1-based) or 1 if not found
        """
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            # Look for the key in the line (simple heuristic)
            if key in line and ":" in line:
                return i
        return 1

    def extract_dependencies(
        self, tree: Any, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:  # type: ignore[override]
        """
        Extract dependencies from configuration files.

        For config files, we look for references to other files or services.

        Args:
            tree: Parsed configuration dictionary
            symbols: List of symbols extracted from the file
            file_path: Relative path to the config file
            content: File content

        Returns:
            List of dependency relationships
        """
        dependencies = []

        if tree is None:
            return dependencies

        # Look for common patterns that indicate dependencies
        self._extract_file_references(tree, file_path, dependencies)
        self._extract_service_references(tree, file_path, dependencies)

        return dependencies

    def _extract_file_references(
        self, data: dict, file_path: str, dependencies: List[Dependency]
    ) -> None:
        """Extract references to other files."""
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            # Look for keys that typically reference files
            if any(keyword in key.lower() for keyword in ["file", "path", "config", "include"]):
                if isinstance(value, str) and (
                    "/" in value
                    or "\\" in value
                    or value.endswith((".yaml", ".yml", ".json", ".toml", ".ini"))
                ):
                    dep_id = f"{file_path}:references:{value}"
                    dependencies.append(
                        Dependency(
                            id=dep_id,
                            from_symbol_id=file_path,
                            to_symbol_id=value,
                            relationship_type="references",
                        )
                    )

            # Recursively check nested dicts
            if isinstance(value, dict):
                self._extract_file_references(value, file_path, dependencies)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._extract_file_references(item, file_path, dependencies)

    def _extract_service_references(
        self, data: dict, file_path: str, dependencies: List[Dependency]
    ) -> None:
        """Extract references to services or external systems."""
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            # Look for keys that typically reference services
            if any(
                keyword in key.lower()
                for keyword in ["service", "host", "url", "endpoint", "database", "db"]
            ):
                if isinstance(value, str):
                    dep_id = f"{file_path}:uses:{value}"
                    dependencies.append(
                        Dependency(
                            id=dep_id,
                            from_symbol_id=file_path,
                            to_symbol_id=value,
                            relationship_type="uses",
                        )
                    )

            # Recursively check nested dicts
            if isinstance(value, dict):
                self._extract_service_references(value, file_path, dependencies)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._extract_service_references(item, file_path, dependencies)


# Made with Bob
