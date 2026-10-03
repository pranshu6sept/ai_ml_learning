import os
from collections.abc import Sequence

import numpy as np
import pytest

from payments_rag import Retriever, SentenceTransformerEmbedder

# A toy embedder: words with the same meaning share a dimension, so "extra" and "surcharges" match.
CONCEPTS = [
    {"surcharge", "surcharges", "extra", "fee"},
    {"settlement", "funds", "money"},
    {"authorization", "approval", "approved"},
]


def toy_embedder(texts: Sequence[str]) -> np.ndarray:
    vectors = np.zeros((len(texts), len(CONCEPTS) + 1), dtype=np.float32)
    for row, text in enumerate(texts):
        words = {w.strip(".,?").lower() for w in text.split()}
        for column, concept in enumerate(CONCEPTS):
            vectors[row, column] = len(words & concept)
        vectors[row, -1] = 0.01  # keeps every vector non-zero
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


CHUNKS = [
    "The directive bans retailer surcharges for card use.",
    "Settlement moves funds between banks.",
    "Authorization is the approval step.",
]


def test_embedding_retrieval_matches_meaning_without_shared_words() -> None:
    retriever = Retriever(CHUNKS, method="embedding", embedder=toy_embedder)

    hits = retriever.search("Can shops charge an extra fee?", top_k=1)

    assert hits[0].chunk.text == CHUNKS[0]
    # The lexical methods cannot find it: no word of the question appears in that chunk.
    assert Retriever(CHUNKS, method="bm25").search("Can shops charge an extra fee?") == []


def test_hybrid_rewards_chunks_that_both_rankings_like() -> None:
    both = "Settlement of funds: money moves between banks."
    chunks = [both, "Settlement is mentioned here only.", "Money and funds are discussed here."]
    retriever = Retriever(chunks, method="hybrid", embedder=toy_embedder)

    hits = retriever.search("settlement funds money", top_k=3)

    assert hits[0].chunk.text == both
    assert hits[0].score <= 2 / (retriever.rrf_k + 1)  # at most rank 1 in both lists


def test_hybrid_ignores_the_lexical_ranking_for_chunks_with_no_word_match() -> None:
    retriever = Retriever(CHUNKS, method="hybrid", embedder=toy_embedder)

    hits = retriever.search("Can shops charge an extra fee?", top_k=3)

    assert hits[0].chunk.text == CHUNKS[0]  # found through the embedding ranking alone


@pytest.mark.parametrize("method", ["embedding", "hybrid"])
def test_embedding_methods_need_an_embedder(method: str) -> None:
    with pytest.raises(ValueError, match="needs an embedder"):
        Retriever(CHUNKS, method=method)


@pytest.mark.skipif(
    os.environ.get("RUN_MODEL_TESTS") != "1",
    reason="downloads a model; set RUN_MODEL_TESTS=1 and install the embeddings group",
)
def test_real_model_links_a_question_to_a_differently_worded_sentence() -> None:
    embedder = SentenceTransformerEmbedder()
    retriever = Retriever(CHUNKS, method="embedding", embedder=embedder)

    hits = retriever.search("Can shops charge extra for paying by card?", top_k=1)

    assert hits[0].chunk.text == CHUNKS[0]
