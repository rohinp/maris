"""Ollama-based embedding generation service."""

import logging
from typing import Callable, List, Optional

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
        batch_size: int = 64,
    ):
        """
        Initialize the Ollama embedding service.

        Args:
            model: Name of the Ollama embedding model to use
            host: Optional Ollama host URL (default: http://localhost:11434)
            batch_size: Number of texts to send in a single ``client.embed`` call
        """
        self.model = model
        self.host = host
        self.batch_size = batch_size
        self.client = ollama.Client(host=host) if host else ollama.Client()

        logger.info(
            f"Initialized OllamaEmbeddingService with model: {model}, batch_size: {batch_size}"
        )

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

    def generate_embeddings(
        self, texts: List[str], progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using native Ollama batch requests.

        Sends texts in chunks of ``batch_size`` using ``client.embed(input=[...])``,
        which issues a single HTTP request per chunk instead of one per text.

        Args:
            texts: List of texts to embed
            progress_callback: Optional callback function(current, total) for progress updates

        Returns:
            List of embedding vectors in the same order as input texts
        """
        if not texts:
            return []

        results: List[List[float]] = []
        total = len(texts)

        for batch_start in range(0, total, self.batch_size):
            batch = texts[batch_start : batch_start + self.batch_size]
            try:
                response = self.client.embed(model=self.model, input=batch)
                results.extend(response["embeddings"])
            except Exception as e:
                logger.error(f"Failed to embed batch starting at index {batch_start}: {e}")
                results.extend(self._generate_embeddings_individually(batch, results))

            if progress_callback:
                progress_callback(min(batch_start + self.batch_size, total), total)

        return results

    def _generate_embeddings_individually(
        self, texts: List[str], existing_results: List[List[float]]
    ) -> List[List[float]]:
        """Retry a failed batch one text at a time before using zero-vector fallback."""
        embeddings: List[List[float]] = []

        for text in texts:
            try:
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Failed to embed text after batch fallback: {e}")
                dim = self._fallback_dimension(existing_results, embeddings)
                embeddings.append([0.0] * dim)

        return embeddings

    def _fallback_dimension(
        self, existing_results: List[List[float]], current_batch_results: List[List[float]]
    ) -> int:
        """Infer zero-vector dimension from successful embeddings when available."""
        if current_batch_results:
            return len(current_batch_results[0])
        if existing_results:
            return len(existing_results[0])
        return 768

    def embed_symbol(self, symbol: Symbol) -> List[float]:
        """
        Generate an embedding for a symbol.

        Uses ``Symbol.to_rich_text()`` to build the embedding text, which
        includes name, type, language, parent, signature, return type, calls,
        docstring, body summary, and source when available.

        Args:
            symbol: Symbol to embed

        Returns:
            Embedding vector
        """
        return self.generate_embedding(symbol.to_rich_text())

    def embed_symbols(
        self, symbols: List[Symbol], progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple symbols in parallel.

        Args:
            symbols: List of symbols to embed
            progress_callback: Optional callback function(current, total) for progress updates

        Returns:
            List of embedding vectors
        """
        texts = [symbol.to_rich_text() for symbol in symbols]
        return self.generate_embeddings(texts, progress_callback=progress_callback)

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
