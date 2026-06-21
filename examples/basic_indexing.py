"""
Basic example of indexing a repository with MARIS.

This example demonstrates:
1. Initializing storage layers
2. Creating an indexing agent
3. Indexing a repository
4. Querying indexed symbols
"""

from pathlib import Path

from maris.agents.indexing_agent import IndexingAgent
from maris.storage.metadata_store import DuckDBMetadataStore
from maris.storage.vector_store import LanceDBVectorStore


def main() -> None:
    """Run basic indexing example."""
    # Configuration
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)

    repo_path = input("Enter repository path to index: ").strip()
    if not Path(repo_path).exists():
        print(f"Error: Repository path '{repo_path}' does not exist")
        return

    print("\n=== Initializing MARIS ===")

    # Initialize metadata store (DuckDB)
    print("Initializing metadata store...")
    metadata_store = DuckDBMetadataStore(str(data_dir / "maris.duckdb"))
    metadata_store.initialize()

    # Initialize vector store (LanceDB)
    print("Initializing vector store...")
    vector_store = LanceDBVectorStore(str(data_dir / "lancedb"))
    vector_store.initialize()

    # Create indexing agent
    print("Creating indexing agent...")
    agent = IndexingAgent(
        metadata_store=metadata_store,
        vector_store=vector_store,
        repo_path=repo_path,
    )

    print("\n=== Indexing Repository ===")
    print(f"Repository: {repo_path}")

    # Index the repository
    result = agent.index_repository()

    print("\n=== Indexing Results ===")
    print(f"Files processed: {result.files_processed}")
    print(f"Symbols extracted: {result.symbols_extracted}")
    print(f"Dependencies found: {result.dependencies_found}")
    print(f"Duration: {result.duration_seconds:.2f} seconds")

    if result.errors:
        print(f"\nErrors encountered: {len(result.errors)}")
        for error in result.errors[:5]:  # Show first 5 errors
            print(f"  - {error}")

    # Get repository statistics
    print("\n=== Repository Statistics ===")
    stats = agent.get_indexing_status()
    print(f"Total files: {stats['total_files']}")
    print(f"Total symbols: {stats['total_symbols']}")
    print(f"Total dependencies: {stats['total_dependencies']}")
    print(f"Languages: {', '.join(stats['languages'])}")

    # Query some symbols
    print("\n=== Sample Symbols ===")
    print("Enter a symbol name to search (or press Enter to skip): ", end="")
    symbol_name = input().strip()

    if symbol_name:
        symbols = metadata_store.find_symbols_by_name(symbol_name)
        if symbols:
            print(f"\nFound {len(symbols)} symbol(s) named '{symbol_name}':")
            for symbol in symbols:
                print(f"  - {symbol.name} ({symbol.type.value})")
                print(f"    File: {symbol.file_path}:{symbol.start_line}")
                if symbol.signature:
                    print(f"    Signature: {symbol.signature}")
        else:
            print(f"No symbols found with name '{symbol_name}'")

    # Cleanup
    metadata_store.close()
    vector_store.close()

    print("\n=== Done ===")
    print(f"Data stored in: {data_dir}")


if __name__ == "__main__":
    main()

# Made with Bob
