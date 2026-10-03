"""Text embeddings: turn text into vectors where similar meanings sit close together."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

# An embedder maps a list of texts to a 2-D float array (one L2-normalised row per text).
Embedder = Callable[[Sequence[str]], np.ndarray]

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceTransformerEmbedder:
    """A local, open-source embedding model (no API key). Needs the ``embeddings`` dependency group.

    The default, all-MiniLM-L6-v2, makes 384-number vectors and reads at most about 256 word pieces.
    Longer text is silently cut off, which is another reason to keep chunks short.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:  # pragma: no cover - depends on the optional group
            raise ImportError(
                "sentence-transformers is not installed; run `uv sync --group embeddings`"
            ) from error
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def __call__(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self._model.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vectors, dtype=np.float32)
