"""Retrieval over chunks: TF-IDF, BM25, embeddings or a hybrid, with source metadata on each hit."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cache

import numpy as np
import snowballstemmer
from sklearn.feature_extraction.text import (
    ENGLISH_STOP_WORDS,
    CountVectorizer,
    TfidfVectorizer,
)
from sklearn.metrics.pairwise import cosine_similarity

from .chunking import Chunk
from .embeddings import Embedder

METHODS = ("tfidf", "bm25", "embedding", "hybrid")
_TOKEN = re.compile(r"(?u)\b\w\w+\b")


@dataclass(frozen=True)
class Hit:
    """One retrieved chunk and its score (higher is closer; 0 means no shared terms)."""

    chunk: Chunk
    score: float


def make_analyzer(stem: bool) -> Callable[[str], list[str]]:
    """Lowercase, split into words, drop English stop words, and optionally stem each word.

    Stemming reduces words to a common root ("applies" and "apply" both become "appli"), so a
    question and a passage can match even when they use different forms of a word.
    """
    stemmer = snowballstemmer.stemmer("english")

    @cache
    def stem_word(word: str) -> str:
        return str(stemmer.stemWord(word))

    def analyze(text: str) -> list[str]:
        tokens = [t for t in _TOKEN.findall(text.lower()) if t not in ENGLISH_STOP_WORDS]
        return [stem_word(t) for t in tokens] if stem else tokens

    return analyze


class Retriever:
    """An index over chunks. Build it once, then call ``search`` for every query.

    * ``tfidf``: cosine similarity of TF-IDF vectors (lexical: matches words).
    * ``bm25``: Okapi BM25, which saturates repeated terms (``k1``) and normalises for chunk length
      (``b``). Also lexical.
    * ``embedding``: cosine similarity of embedding vectors (matches meaning; needs ``embedder``).
    * ``hybrid``: reciprocal rank fusion of ``bm25`` and ``embedding``: each chunk scores
      ``sum(1 / (rrf_k + rank))`` over the two rankings, so a chunk both agree on rises to the top.
    """

    def __init__(
        self,
        chunks: Iterable[Chunk | str],
        *,
        method: str = "tfidf",
        stem: bool = False,
        k1: float = 1.5,
        b: float = 0.75,
        embedder: Embedder | None = None,
        rrf_k: int = 60,
    ) -> None:
        if method not in METHODS:
            raise ValueError(f"unknown method {method!r}; choose from {METHODS}")
        if method in ("embedding", "hybrid") and embedder is None:
            raise ValueError(f"method {method!r} needs an embedder")
        self.chunks = [
            chunk if isinstance(chunk, Chunk) else Chunk(chunk, index)
            for index, chunk in enumerate(chunks)
        ]
        if not self.chunks:
            raise ValueError("chunks must not be empty")
        self.method = method
        self.k1, self.b, self.rrf_k = k1, b, rrf_k
        self._analyze = make_analyzer(stem)
        self._embedder = embedder
        texts = [chunk.text for chunk in self.chunks]

        if method == "tfidf":
            self._vectorizer = TfidfVectorizer(analyzer=self._analyze)
            self._matrix = self._vectorizer.fit_transform(texts)
        if method in ("bm25", "hybrid"):
            counter = CountVectorizer(analyzer=self._analyze)
            self._counts = counter.fit_transform(texts).tocsc()
            self._vocab = counter.vocabulary_
            doc_freq = np.diff(self._counts.indptr)
            self._idf = np.log(1 + (len(self.chunks) - doc_freq + 0.5) / (doc_freq + 0.5))
            self._doc_len = np.asarray(self._counts.sum(axis=1)).ravel()
            self._avg_len = float(self._doc_len.mean()) or 1.0
        if embedder is not None and method in ("embedding", "hybrid"):
            self._vectors = np.asarray(embedder(texts))

    def _tfidf_scores(self, query: str) -> np.ndarray:
        vector = self._vectorizer.transform([query])
        return np.asarray(cosine_similarity(vector, self._matrix)).ravel()

    def _bm25_scores(self, query: str) -> np.ndarray:
        scores = np.zeros(len(self.chunks))
        norm = self.k1 * (1 - self.b + self.b * self._doc_len / self._avg_len)
        for term in set(self._analyze(query)):
            column = self._vocab.get(term)
            if column is None:
                continue
            tf = self._counts[:, column].toarray().ravel()
            scores += self._idf[column] * tf * (self.k1 + 1) / np.maximum(tf + norm, 1e-12)
        return scores

    def _embedding_scores(self, query: str) -> np.ndarray:
        assert self._embedder is not None
        return np.asarray(self._vectors @ np.asarray(self._embedder([query]))[0])

    def _reciprocal_rank_fusion(self, *score_lists: np.ndarray) -> np.ndarray:
        fused = np.zeros(len(self.chunks))
        for scores in score_lists:
            ranks = np.empty(len(scores), dtype=int)
            ranks[np.argsort(-scores, kind="stable")] = np.arange(1, len(scores) + 1)
            fused += np.where(scores > 0, 1.0 / (self.rrf_k + ranks), 0.0)
        return fused

    def _scores(self, query: str) -> np.ndarray:
        if self.method == "tfidf":
            return self._tfidf_scores(query)
        if self.method == "bm25":
            return self._bm25_scores(query)
        if self.method == "embedding":
            return self._embedding_scores(query)
        return self._reciprocal_rank_fusion(self._bm25_scores(query), self._embedding_scores(query))

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        """Return up to ``top_k`` chunks, best first. Chunks with a score of 0 or less (no shared
        terms, or no similarity) are left out, so an empty result means "no evidence"."""
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        scores = self._scores(query)
        order = np.argsort(-scores, kind="stable")[:top_k]
        return [Hit(self.chunks[i], float(scores[i])) for i in order if scores[i] > 0]


def build_retriever(chunks: Iterable[Chunk | str], **options: object) -> Retriever:
    """Build a retriever from chunks (or plain strings); options go to ``Retriever``."""
    return Retriever(chunks, **options)  # type: ignore[arg-type]


def retrieve_chunks(
    query: str,
    chunks: Iterable[str],
    top_k: int = 3,
) -> list[tuple[str, float]]:
    """Convenience wrapper: index plain strings and return ``(text, score)`` pairs.

    It rebuilds the index on every call; use ``Retriever`` when asking more than one question.
    """
    if top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    chunk_list = list(chunks)
    if not chunk_list:
        return []
    return [(hit.chunk.text, hit.score) for hit in Retriever(chunk_list).search(query, top_k)]
