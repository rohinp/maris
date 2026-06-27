"""Markdown file parser for documentation and README files."""

import re
from typing import Any, List

from maris.core.models import Dependency, Symbol, SymbolType
from maris.indexing.parser import TreeSitterParser


class MarkdownParser(TreeSitterParser):
    """
    Parser for Markdown files (.md).

    Extracts headings, code blocks, and links as symbols,
    making documentation searchable and queryable.
    """

    def __init__(self):
        """Initialize the Markdown parser."""
        super().__init__("markdown")

    def setup_parser(self) -> None:
        """
        Markdown parser doesn't use tree-sitter.

        This method is required by the base class but does nothing
        since we parse markdown files directly.
        """
        # Markdown files don't need tree-sitter parsing
        self.parser = None

    def parse_file(self, file_path: str, content: str) -> Any:  # type: ignore[override]
        """
        Parse a Markdown file.

        Args:
            file_path: Path to the markdown file
            content: File content

        Returns:
            The content itself (we parse it directly in extract_symbols)
        """
        return content

    def extract_symbols(self, tree: Any, file_path: str, content: str) -> List[Symbol]:  # type: ignore[override]
        """
        Extract symbols from Markdown content.

        Extracts:
        - Headings (H1-H6)
        - Code blocks with language tags
        - Links to other documents

        Args:
            tree: Content string (not used as tree)
            file_path: Relative path to the markdown file
            content: File content

        Returns:
            List of extracted symbols
        """
        symbols = []
        lines = content.split("\n")

        # Extract headings
        heading_symbols = self._extract_headings(lines, file_path)
        symbols.extend(heading_symbols)

        # Extract code blocks
        code_block_symbols = self._extract_code_blocks(lines, file_path)
        symbols.extend(code_block_symbols)

        return symbols

    def _extract_headings(self, lines: List[str], file_path: str) -> List[Symbol]:
        """
        Extract heading symbols from markdown.

        Args:
            lines: Lines of markdown content
            file_path: File path

        Returns:
            List of heading symbols
        """
        symbols = []

        for line_num, line in enumerate(lines, 1):
            # Match ATX-style headings: # Heading
            match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if match:
                level = len(match.group(1))
                heading_text = match.group(2).strip()

                # Generate a clean symbol name (remove special chars)
                symbol_name = re.sub(r"[^\w\s-]", "", heading_text).strip()
                symbol_name = re.sub(r"\s+", "_", symbol_name)

                symbol_id = self.generate_symbol_id(file_path, symbol_name, line_num)

                # Use different symbol types based on heading level
                if level == 1:
                    symbol_type = SymbolType.CLASS  # Top-level sections
                elif level == 2:
                    symbol_type = SymbolType.INTERFACE  # Major subsections
                else:
                    symbol_type = SymbolType.FUNCTION  # Smaller sections

                symbols.append(
                    Symbol(
                        id=symbol_id,
                        name=symbol_name,
                        type=symbol_type,
                        file_path=file_path,
                        language=self.language,
                        start_line=line_num,
                        end_line=line_num,
                        docstring=f"H{level}: {heading_text}",
                    )
                )

        return symbols

    def _extract_code_blocks(self, lines: List[str], file_path: str) -> List[Symbol]:
        """
        Extract code block symbols from markdown.

        Args:
            lines: Lines of markdown content
            file_path: File path

        Returns:
            List of code block symbols
        """
        symbols = []
        in_code_block = False
        code_block_start = 0
        code_block_lang = ""

        for line_num, line in enumerate(lines, 1):
            # Match code fence: ```language
            if line.strip().startswith("```"):
                if not in_code_block:
                    # Starting a code block
                    in_code_block = True
                    code_block_start = line_num
                    # Extract language if specified
                    lang_match = re.match(r"^```(\w+)", line.strip())
                    code_block_lang = lang_match.group(1) if lang_match else "code"
                else:
                    # Ending a code block
                    in_code_block = False

                    # Create symbol for this code block
                    symbol_name = f"code_block_{code_block_lang}_{code_block_start}"
                    symbol_id = self.generate_symbol_id(file_path, symbol_name, code_block_start)

                    symbols.append(
                        Symbol(
                            id=symbol_id,
                            name=symbol_name,
                            type=SymbolType.CONSTANT,  # Treat code blocks as constants
                            file_path=file_path,
                            language=self.language,
                            start_line=code_block_start,
                            end_line=line_num,
                            docstring=f"Code block ({code_block_lang})",
                        )
                    )

        return symbols

    def extract_dependencies(
        self, tree: Any, symbols: List[Symbol], file_path: str, content: str
    ) -> List[Dependency]:  # type: ignore[override]
        """
        Extract dependencies from Markdown files.

        Extracts:
        - Links to other markdown files
        - Links to external resources

        Args:
            tree: Content string (not used as tree)
            symbols: List of symbols extracted from the file
            file_path: Relative path to the markdown file
            content: File content

        Returns:
            List of dependency relationships
        """
        dependencies = []

        # Extract markdown links: [text](url)
        link_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
        matches = re.finditer(link_pattern, content)

        for match in matches:
            link_url = match.group(2)

            # Skip external URLs (http/https)
            if link_url.startswith(("http://", "https://", "mailto:")):
                continue

            # Skip anchors within the same document
            if link_url.startswith("#"):
                continue

            # This is likely a reference to another file
            dep_id = f"{file_path}:references:{link_url}"
            dependencies.append(
                Dependency(
                    id=dep_id,
                    from_symbol_id=file_path,
                    to_symbol_id=link_url,
                    relationship_type="references",
                )
            )

        # Extract reference-style links: [text][ref]
        ref_link_pattern = r"\[([^\]]+)\]\[([^\]]+)\]"
        ref_matches = re.finditer(ref_link_pattern, content)

        for match in ref_matches:
            ref_id = match.group(2)
            # Look for the reference definition: [ref]: url
            ref_def_pattern = rf"^\[{re.escape(ref_id)}\]:\s*(.+)$"
            ref_def_match = re.search(ref_def_pattern, content, re.MULTILINE)

            if ref_def_match:
                ref_url = ref_def_match.group(1).strip()

                # Skip external URLs
                if ref_url.startswith(("http://", "https://", "mailto:")):
                    continue

                dep_id = f"{file_path}:references:{ref_url}"
                dependencies.append(
                    Dependency(
                        id=dep_id,
                        from_symbol_id=file_path,
                        to_symbol_id=ref_url,
                        relationship_type="references",
                    )
                )

        return dependencies


# Made with Bob
