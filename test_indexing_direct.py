#!/usr/bin/env python3
"""Test indexing directly with absolute paths."""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from maris.agents.indexing_agent import IndexingAgent
from maris.storage.metadata_store import DuckDBMetadataStore
from maris.storage.vector_store import LanceDBVectorStore
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService


def test_indexing(repo_path: str, test_files: list):
    """Test indexing with specific files."""
    print("=" * 60)
    print(f"Testing IndexingAgent")
    print(f"Repo path: {repo_path}")
    print(f"Test files: {len(test_files)}")
    print("=" * 60)

    # Initialize stores
    maris_dir = Path(repo_path) / ".maris"
    maris_dir.mkdir(exist_ok=True)

    metadata_store = DuckDBMetadataStore(str(maris_dir / "maris.db"))
    vector_store = LanceDBVectorStore(str(maris_dir / "vectors"))
    embedding_service = OllamaEmbeddingService()

    # Create indexing agent
    agent = IndexingAgent(
        metadata_store=metadata_store,
        vector_store=vector_store,
        repo_path=repo_path,
        embedding_service=embedding_service,
    )

    print("\nIndexing files...")
    result = agent.index_files(test_files)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Files processed: {result.files_processed}")
    print(f"Symbols extracted: {result.symbols_extracted}")
    print(f"Embeddings generated: {result.embeddings_generated}")
    print(f"Duration: {result.duration_seconds:.2f}s")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for error in result.errors[:10]:
            print(f"  - {error}")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_indexing_direct.py /path/to/repo [file1] [file2] ...")
        print("\nExample:")
        print("  cd /path/to/event-hive")
        print(
            "  python3 /path/to/maris/test_indexing_direct.py . $(find . -name '*.scala' -type f | head -5)"
        )
        sys.exit(1)

    repo_path = sys.argv[1]

    if len(sys.argv) > 2:
        # Specific files provided
        test_files = sys.argv[2:]
    else:
        # Find some Scala files
        repo = Path(repo_path)
        test_files = [str(f) for f in list(repo.rglob("*.scala"))[:5]]

    if not test_files:
        print("No files to test!")
        sys.exit(1)

    print(f"Testing with {len(test_files)} files:")
    for f in test_files:
        print(f"  - {f}")

    result = test_indexing(repo_path, test_files)

    if result.files_processed == 0:
        print("\n❌ FAILED: No files were processed!")
        sys.exit(1)
    else:
        print(f"\n✅ SUCCESS: Processed {result.files_processed} files")
        sys.exit(0)

# Made with Bob
