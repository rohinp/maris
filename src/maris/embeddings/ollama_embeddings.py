"""Ollama-based embedding generation service."""

import logging
from typing import List, Optional

import ollama

from maris.core.models import Symbol

logger = logging.getLogger(__name__)


class OllamaEmbeddingService:
    """
    Service for generating embeddings using Ollama.

    Uses local Ollama models for privacy-first embedding generation.
    Recommended models:
    - nomic-embed-text (default)
    - mxbai-embed-large
    - all-minilm
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        host: Optional[str] = None,
        batch_size: int = 32,
    ):
        """
        Initialize the Ollama embedding service.

        Args:
            model: Name of the Ollama embedding model to use
            host: Optional Ollama host URL (default: http://localhost:11434)
            batch_size: Number of texts to embed in a single batch
        """
        self.model = model
        self.host = host
        self.batch_size = batch_size
        self.client = ollama.Client(host=host) if host else ollama.Client()

        logger.info(f"Initialized OllamaEmbeddingService with model: {model}")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        try:
            response = self.client.embeddings(model=self.model, prompt=text)
            return response["embedding"]
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            logger.debug(f"Processing batch {i // self.batch_size + 1} ({len(batch)} texts)")

            for text in batch:
                try:
                    embedding = self.generate_embedding(text)
                    embeddings.append(embedding)
                except Exception as e:
                    logger.error(f"Failed to embed text in batch: {e}")
                    # Use zero vector as fallback
                    embeddings.append([0.0] * 768)  # Default dimension

        return embeddings

    def embed_symbol(self, symbol: Symbol) -> List[float]:
        """
        Generate an embedding for a symbol.

        Creates a rich text representation of the symbol including:
        - Symbol name and type
        - Signature (if available)
        - Docstring (if available)
        - File path context

        Args:
            symbol: Symbol to embed

        Returns:
            Embedding vector
        """
        # Build rich text representation
        parts = [
            f"Symbol: {symbol.name}",
            f"Type: {symbol.type.value}",
            f"Language: {symbol.language}",
        ]

        if symbol.signature:
            parts.append(f"Signature: {symbol.signature}")

        if symbol.docstring:
            parts.append(f"Documentation: {symbol.docstring}")

        parts.append(f"File: {symbol.file_path}")

        text = "\n".join(parts)
        return self.generate_embedding(text)

    def embed_symbols(self, symbols: List[Symbol]) -> List[List[float]]:
        """
        Generate embeddings for multiple symbols.

        Args:
            symbols: List of symbols to embed

        Returns:
            List of embedding vectors
        """
        texts = []
        for symbol in symbols:
            parts = [
                f"Symbol: {symbol.name}",
                f"Type: {symbol.type.value}",
                f"Language: {symbol.language}",
            ]

            if symbol.signature:
                parts.append(f"Signature: {symbol.signature}")

            if symbol.docstring:
                parts.append(f"Documentation: {symbol.docstring}")

            parts.append(f"File: {symbol.file_path}")

            texts.append("\n".join(parts))

        return self.generate_embeddings(texts)

    def check_model_availability(self) -> bool:
        """
        Check if the configured model is available in Ollama.

        Returns:
            True if model is available, False otherwise
        """
        try:
            models = self.client.list()
            model_names = [m["name"] for m in models.get("models", [])]
            return self.model in model_names
        except Exception as e:
            logger.error(f"Failed to check model availability: {e}")
            return False

    def pull_model(self) -> bool:
        """
        Pull the configured model from Ollama registry.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Pulling model: {self.model}")
            self.client.pull(self.model)
            logger.info(f"Successfully pulled model: {self.model}")
            return True
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False


# Made with Bob
