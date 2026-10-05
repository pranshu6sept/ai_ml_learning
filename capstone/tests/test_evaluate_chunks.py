import sys
from pathlib import Path
from typing import Any

import pytest

from payments_rag import Hit
from payments_rag.chunking import Chunk

EVALS = Path(__file__).resolve().parents[1] / "evals"


class FixedResults:
    """A retriever that returns the same ranked chunks for every question."""

    def __init__(self, hits: list[Hit]) -> None:
        self._hits = hits

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        return self._hits[:top_k]


def _score(chunks: list[Chunk], hits: list[Hit]) -> dict[str, Any]:
    sys.path.insert(0, str(EVALS))
    try:
        from evaluate_chunking import evaluate  # type: ignore[import-not-found]
    finally:
        sys.path.remove(str(EVALS))
    question = {
        "id": "q",
        "kind": "direct",
        "question": "what is x?",
        "gold": [{"doc": "d", "phrase": "the answer"}],
    }
    return evaluate(  # type: ignore[no-any-return]
        "unused", {}, [question], retriever_factory=lambda _c: FixedResults(hits), chunks=chunks
    )


def test_ndcg_uses_the_number_of_relevant_chunks_in_the_chunk_set_that_was_searched() -> None:
    relevant_a = Chunk("the answer, part a", 0, doc_id="d")
    relevant_b = Chunk("more text and the answer again", 1, doc_id="d")
    other = Chunk("unrelated", 2, doc_id="d")
    hits = [Hit(relevant_a, 1.0), Hit(other, 0.5)]  # finds one relevant chunk, at rank 1

    one_relevant_exists = _score([relevant_a, other], hits)
    two_relevant_exist = _score([relevant_a, relevant_b, other], hits)

    assert one_relevant_exists["ndcg@3"] == pytest.approx(1.0)  # found the only one: perfect
    assert two_relevant_exist["ndcg@3"] < 1.0  # a second relevant chunk was missed
