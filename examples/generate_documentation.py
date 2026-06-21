"""Example: Generate documentation for a repository using the Documentation Agent."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from maris.agents.documentation_agent import DocumentationAgent
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService
from maris.knowledge.repository_knowledge_impl import RepositoryKnowledgeImpl
from maris.storage.metadata_store import DuckDBMetadataStore
from maris.storage.vector_store import LanceDBVectorStore


def main():
    """Generate documentation for the MARIS repository itself."""

    print("🔧 Initializing MARIS Documentation Generator...")

    # Initialize storage layers
    metadata_store = DuckDBMetadataStore("data/maris_metadata.db")
    metadata_store.initialize()

    vector_store = LanceDBVectorStore("data/maris_vectors")
    vector_store.initialize()

    # Initialize embedding service
    embedding_service = OllamaEmbeddingService(model="nomic-embed-text")

    # Check if Ollama model is available
    if not embedding_service.check_model_availability():
        print("⚠️  Model 'nomic-embed-text' not found. Attempting to pull...")
        if not embedding_service.pull_model():
            print("❌ Failed to pull model. Please install Ollama and pull the model manually:")
            print("   ollama pull nomic-embed-text")
            return

    # Initialize knowledge service
    knowledge_service = RepositoryKnowledgeImpl(
        metadata_store=metadata_store,
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    # Initialize documentation agent
    doc_agent = DocumentationAgent(knowledge_service)

    print("\n📊 Generating Architecture Overview...")
    arch_md = doc_agent.generate_architecture_markdown()

    # Save architecture documentation
    arch_path = Path("docs/GENERATED_ARCHITECTURE.md")
    arch_path.write_text(arch_md)
    print(f"✅ Architecture overview saved to: {arch_path}")

    # Example: Generate documentation for a specific file
    example_file = "src/maris/core/models.py"

    if knowledge_service.is_indexed(example_file):
        print(f"\n📝 Generating documentation for: {example_file}")
        file_md = doc_agent.generate_markdown_documentation(example_file)

        # Save file documentation
        doc_path = Path("docs/GENERATED_MODELS.md")
        doc_path.write_text(file_md)
        print(f"✅ File documentation saved to: {doc_path}")
    else:
        print(f"\n⚠️  File not indexed: {example_file}")
        print("   Run the indexing agent first to index the repository.")

    print("\n✨ Documentation generation complete!")


if __name__ == "__main__":
    main()

# Made with Bob
