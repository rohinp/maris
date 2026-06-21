"""Example: Ask questions about a repository using the Q&A Agent."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from maris.agents.qa_agent import QAAgent
from maris.embeddings.ollama_embeddings import OllamaEmbeddingService
from maris.knowledge.repository_knowledge_impl import RepositoryKnowledgeImpl
from maris.storage.metadata_store import DuckDBMetadataStore
from maris.storage.vector_store import LanceDBVectorStore


def main():
    """Ask questions about the MARIS repository."""

    print("🤖 Initializing MARIS Q&A Agent...")

    # Initialize storage layers
    metadata_store = DuckDBMetadataStore("data/maris_metadata.db")
    metadata_store.initialize()

    vector_store = LanceDBVectorStore("data/maris_vectors")
    vector_store.initialize()

    # Initialize embedding service
    embedding_service = OllamaEmbeddingService(model="nomic-embed-text")

    # Check if embedding model is available
    if not embedding_service.check_model_availability():
        print("⚠️  Embedding model 'nomic-embed-text' not found.")
        print("   Please install: ollama pull nomic-embed-text")
        return

    # Initialize knowledge service
    knowledge_service = RepositoryKnowledgeImpl(
        metadata_store=metadata_store,
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    # Initialize Q&A agent
    qa_agent = QAAgent(
        knowledge_service=knowledge_service,
        model="qwen2.5:7b",  # Or any other Ollama model you have
    )

    print("✅ Q&A Agent initialized!\n")

    # Example questions
    questions = [
        "What does the PythonParser class do?",
        "How does symbol extraction work?",
        "Where is the RepositoryKnowledgeService used?",
    ]

    for question in questions:
        print(f"❓ Question: {question}")
        print("=" * 60)

        try:
            answer = qa_agent.answer_question(question, max_symbols=5)

            print(f"\n💡 Answer ({answer.confidence} confidence):")
            print(answer.answer)

            if answer.relevant_symbols:
                print(f"\n📚 Relevant Symbols ({len(answer.relevant_symbols)}):")
                for symbol in answer.relevant_symbols[:3]:
                    print(f"  - {symbol.name} ({symbol.type.value}) in {symbol.file_path}")

            if answer.sources:
                print(f"\n📁 Sources ({len(answer.sources)}):")
                for source in answer.sources[:5]:
                    print(f"  - {source}")

        except Exception as e:
            print(f"❌ Error: {e}")

        print("\n" + "=" * 60 + "\n")

    # Interactive mode
    print("💬 Interactive Q&A Mode (type 'quit' to exit)")
    print("=" * 60)

    while True:
        try:
            question = input("\n❓ Your question: ").strip()

            if question.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break

            if not question:
                continue

            answer = qa_agent.answer_question(question)

            print(f"\n💡 Answer ({answer.confidence} confidence):")
            print(answer.answer)

            if answer.relevant_symbols:
                print(f"\n📚 Relevant Symbols: {len(answer.relevant_symbols)}")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()

# Made with Bob
