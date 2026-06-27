"""Ollama-based embedding generation service."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        batch_size: int = 32,
        max_workers: int = 4,
    ):
        """
        Initialize the Ollama embedding service.

        Args:
            model: Name of the Ollama embedding model to use
            host: Optional Ollama host URL (default: http://localhost:11434)
            batch_size: Number of texts to embed in a single batch
            max_workers: Maximum number of parallel workers for embedding generation
        """
        self.model = model
        self.host = host
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.client = ollama.Client(host=host) if host else ollama.Client()

        logger.info(
            f"Initialized OllamaEmbeddingService with model: {model}, max_workers: {max_workers}"
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
        Generate embeddings for multiple texts in parallel.

        Args:
            texts: List of texts to embed
            progress_callback: Optional callback function(current, total) for progress updates

        Returns:
            List of embedding vectors in the same order as input texts
        """
        if not texts:
            return []

        # Store results with their original indices to maintain order
        results: List[List[float]] = [None] * len(texts)  # type: ignore
        completed = 0

        def embed_with_index(idx: int, text: str) -> tuple:
            """Embed a single text and return with its index."""
            try:
                embedding = self.generate_embedding(text)
                return (idx, embedding, None)
            except Exception as e:
                logger.error(f"Failed to embed text at index {idx}: {e}")
                return (idx, [0.0] * 768, str(e))  # Fallback zero vector

        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(embed_with_index, idx, text): idx for idx, text in enumerate(texts)
            }

            # Process completed tasks
            for future in as_completed(futures):
                idx, embedding, error = future.result()
                results[idx] = embedding
                completed += 1

                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed, len(texts))

                if error:
                    logger.warning(f"Used fallback embedding for text {idx} due to error: {error}")

        return results

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
