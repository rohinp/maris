"""Tests for OllamaEmbeddingService.generate_embeddings batch behaviour."""

from unittest.mock import MagicMock, patch

import pytest

from maris.embeddings.ollama_embeddings import OllamaEmbeddingService


def _make_embed_response(vectors):
    """Build the dict structure returned by ollama.Client.embed."""
    return {"embeddings": vectors}


@pytest.fixture
def service():
    """OllamaEmbeddingService with a mocked Ollama client."""
    with patch("maris.embeddings.ollama_embeddings.ollama.Client") as MockClient:
        svc = OllamaEmbeddingService(model="nomic-embed-text", batch_size=3)
        svc.client = MockClient.return_value
        yield svc


# ---------------------------------------------------------------------------
# generate_embeddings — batching
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingsBatching:
    """Verify that texts are split into chunks and one HTTP call is made per chunk."""

    def test_single_batch_when_texts_fit(self, service):
        """Fewer texts than batch_size → exactly one client.embed call."""
        vectors = [[float(i)] * 768 for i in range(2)]
        service.client.embed.return_value = _make_embed_response(vectors)

        result = service.generate_embeddings(["a", "b"])

        service.client.embed.assert_called_once_with(
            model="nomic-embed-text", input=["a", "b"]
        )
        assert result == vectors

    def test_multiple_batches_for_large_input(self, service):
        """7 texts with batch_size=3 → 3 calls (3, 3, 1)."""
        texts = [f"text{i}" for i in range(7)]
        # Provide per-batch responses
        service.client.embed.side_effect = [
            _make_embed_response([[float(i)] * 768 for i in range(3)]),
            _make_embed_response([[float(i)] * 768 for i in range(3, 6)]),
            _make_embed_response([[float(i)] * 768 for i in range(6, 7)]),
        ]

        result = service.generate_embeddings(texts)

        assert service.client.embed.call_count == 3
        assert len(result) == 7

    def test_empty_input_returns_empty_list(self, service):
        """Empty text list short-circuits without any HTTP calls."""
        result = service.generate_embeddings([])

        service.client.embed.assert_not_called()
        assert result == []


# ---------------------------------------------------------------------------
# generate_embeddings — result ordering
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingsOrdering:
    """Results must be returned in the same order as the input texts."""

    def test_order_preserved_across_batches(self, service):
        """Vectors from multiple batches are concatenated in input order."""
        batch1 = [[1.0] * 768, [2.0] * 768, [3.0] * 768]
        batch2 = [[4.0] * 768, [5.0] * 768]
        service.client.embed.side_effect = [
            _make_embed_response(batch1),
            _make_embed_response(batch2),
        ]

        texts = [f"t{i}" for i in range(5)]
        result = service.generate_embeddings(texts)

        assert result == batch1 + batch2

    def test_single_text_returns_single_vector(self, service):
        vec = [[0.5] * 768]
        service.client.embed.return_value = _make_embed_response(vec)

        result = service.generate_embeddings(["hello"])

        assert result == vec


# ---------------------------------------------------------------------------
# generate_embeddings — progress callback
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingsProgressCallback:
    """Progress callback fires once per batch with cumulative count."""

    def test_callback_called_once_per_batch(self, service):
        """3 batches → 3 callback invocations with correct (current, total)."""
        texts = [f"t{i}" for i in range(7)]
        service.client.embed.side_effect = [
            _make_embed_response([[0.0] * 768] * 3),
            _make_embed_response([[0.0] * 768] * 3),
            _make_embed_response([[0.0] * 768] * 1),
        ]
        cb = MagicMock()

        service.generate_embeddings(texts, progress_callback=cb)

        assert cb.call_count == 3
        cb.assert_any_call(3, 7)
        cb.assert_any_call(6, 7)
        cb.assert_any_call(7, 7)

    def test_no_callback_when_not_provided(self, service):
        """No error when progress_callback is None (the default)."""
        service.client.embed.return_value = _make_embed_response([[0.0] * 768])
        # Should not raise
        service.generate_embeddings(["text"])


# ---------------------------------------------------------------------------
# generate_embeddings — failed-batch fallback
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingsFallback:
    """A failing batch is retried per text before zero-vector fallback is used."""

    def test_failed_batch_retries_texts_individually(self, service):
        """When a batch raises, each text is retried with the single-text API."""
        service.client.embed.side_effect = RuntimeError("Ollama down")
        vectors = [[1.0] * 768, [2.0] * 768]
        service.client.embeddings.side_effect = [{"embedding": vector} for vector in vectors]

        result = service.generate_embeddings(["a", "b"])

        assert result == vectors
        assert service.client.embeddings.call_count == 2

    def test_failed_individual_retry_produces_zero_vector_for_that_text(self, service):
        """Only texts that fail after individual retry are replaced with zero vectors."""
        service.client.embed.side_effect = RuntimeError("Ollama down")
        service.client.embeddings.side_effect = [
            {"embedding": [1.0] * 768},
            RuntimeError("Bad text"),
        ]

        result = service.generate_embeddings(["a", "b"])

        assert result == [[1.0] * 768, [0.0] * 768]

    def test_failed_batch_uses_dim_from_prior_good_batch(self, service):
        """Zero-vector dimension is inferred from a previously successful batch."""
        good_vec = [1.0] * 512  # intentionally non-768 to detect the dim source
        service.client.embed.side_effect = [
            _make_embed_response([good_vec] * 3),  # batch 0 succeeds
            RuntimeError("Ollama down"),            # batch 1 fails
        ]
        service.client.embeddings.side_effect = RuntimeError("Ollama down")
        texts = [f"t{i}" for i in range(6)]  # 2 batches of 3

        result = service.generate_embeddings(texts)

        assert len(result) == 6
        assert result[:3] == [good_vec] * 3
        assert result[3:] == [[0.0] * 512] * 3
