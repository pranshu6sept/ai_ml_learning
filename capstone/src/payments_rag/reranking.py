"""Reranking: re-score a short list of retrieved chunks by reading question and chunk together."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from .retrieval import Hit

# A reranker maps (query, texts) to one relevance score per text. Higher means more relevant.
Reranker = Callable[[str, Sequence[str]], np.ndarray]

DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """A local cross-encoder: it reads the question and a chunk *together* and scores the pair.

    That is slower than comparing two stored vectors, so use it only on a short list of candidates.
    Scores are raw logits, not probabilities: where "relevant enough" starts must be learned.
    """

    def __init__(self, model_name: str = DEFAULT_RERANKER_MODEL) -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as error:  # pragma: no cover - depends on the optional group
            raise ImportError(
                "sentence-transformers is not installed; run `uv sync --group embeddings`"
            ) from error
        self.model_name = model_name
        self._model = CrossEncoder(model_name)

    def __call__(self, query: str, texts: Sequence[str]) -> np.ndarray:
        pairs = [(query, text) for text in texts]
        return np.asarray(self._model.predict(pairs, show_progress_bar=False), dtype=np.float64)


def rerank(
    query: str, hits: Sequence[Hit], reranker: Reranker, top_k: int | None = None
) -> list[Hit]:
    """Re-order ``hits`` by the reranker's score; the returned hits carry the reranker's score."""
    if not hits:
        return []
    scores = reranker(query, [hit.chunk.text for hit in hits])
    order = np.argsort(-scores, kind="stable")
    ranked = [Hit(hits[i].chunk, float(scores[i])) for i in order]
    return ranked if top_k is None else ranked[:top_k]
