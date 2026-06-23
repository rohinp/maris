#!/usr/bin/env python3
"""Debug script to test Scala parsing directly."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from maris.indexing.scala_parser import ScalaParser
from maris.indexing.parser_factory import ParserFactory


def test_parser_factory():
    """Test if ParserFactory can create a Scala parser."""
    print("=" * 60)
    print("Testing ParserFactory")
    print("=" * 60)

    # Check supported extensions
    extensions = ParserFactory.get_supported_extensions()
    print(f"Supported extensions: {extensions}")

    # Check if .scala is supported
    if ".scala" in extensions:
        print("✓ .scala is supported")
    else:
        print("✗ .scala is NOT supported")
        return False

    # Try to get language name
    lang = ParserFactory.get_language_name("test.scala")
    print(f"Language for test.scala: {lang}")

    # Try to get parser
    parser = ParserFactory.get_parser("test.scala")
    if parser:
        print(f"✓ Got parser: {type(parser).__name__}")
        return True
    else:
        print("✗ Failed to get parser")
        return False


def test_scala_parser_direct():
    """Test ScalaParser directly."""
    print("\n" + "=" * 60)
    print("Testing ScalaParser directly")
    print("=" * 60)

    try:
        parser = ScalaParser()
        print(f"✓ Created ScalaParser: {parser}")

        # Test with simple Scala code
        test_code = """
package com.example

class HelloWorld {
  def greet(name: String): String = {
    s"Hello, $name!"
  }
}
"""

        print("\nParsing test code...")
        tree = parser.parse_file("test.scala", test_code)

        if tree:
            print(f"✓ Parse successful, tree: {tree}")

            # Extract symbols
            symbols = parser.extract_symbols(tree, "test.scala", test_code)
            print(f"✓ Extracted {len(symbols)} symbols:")
            for sym in symbols:
                print(f"  - {sym.type.value}: {sym.name}")

            return True
        else:
            print("✗ Parse failed, tree is None")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_real_file(file_path: str):
    """Test parsing a real Scala file."""
    print("\n" + "=" * 60)
    print(f"Testing real file: {file_path}")
    print("=" * 60)

    path = Path(file_path)
    if not path.exists():
        print(f"✗ File not found: {file_path}")
        return False

    try:
        content = path.read_text()
        print(f"File size: {len(content)} bytes")
        print(f"Lines: {len(content.splitlines())}")

        # Try with ParserFactory
        parser = ParserFactory.get_parser(str(path))
        if not parser:
            print("✗ ParserFactory returned None")
            return False

        print(f"✓ Got parser: {type(parser).__name__}")

        # Parse
        tree = parser.parse_file(str(path), content)
        if not tree:
            print("✗ Parse returned None")
            return False

        print(f"✓ Parse successful")

        # Extract symbols
        symbols = parser.extract_symbols(tree, str(path), content)
        print(f"✓ Extracted {len(symbols)} symbols:")

        # Show first 10 symbols
        for sym in symbols[:10]:
            print(f"  - {sym.type.value}: {sym.name} at {sym.file_path}:{sym.start_line}")

        if len(symbols) > 10:
            print(f"  ... and {len(symbols) - 10} more")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Scala Parser Debug Script")
    print("=" * 60)

    # Test 1: ParserFactory
    factory_ok = test_parser_factory()

    # Test 2: Direct ScalaParser
    direct_ok = test_scala_parser_direct()

    # Test 3: Real file if provided
    if len(sys.argv) > 1:
        file_ok = test_real_file(sys.argv[1])
    else:
        print("\n" + "=" * 60)
        print("To test a real file, run:")
        print(f"  python3 {sys.argv[0]} /path/to/file.scala")
        print("=" * 60)
        file_ok = None

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"ParserFactory: {'✓ PASS' if factory_ok else '✗ FAIL'}")
    print(f"Direct ScalaParser: {'✓ PASS' if direct_ok else '✗ FAIL'}")
    if file_ok is not None:
        print(f"Real file parsing: {'✓ PASS' if file_ok else '✗ FAIL'}")

    sys.exit(0 if (factory_ok and direct_ok) else 1)

# Made with Bob
