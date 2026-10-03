import json
from pathlib import Path

import pytest

from payments_rag import Chunk, Retriever, build_retriever

CAPSTONE = Path(__file__).resolve().parents[1]


def test_retriever_returns_chunks_with_their_metadata() -> None:
    chunks = [
        Chunk("Settlement moves funds between banks.", 0, doc_id="card", section="Lifecycle"),
        Chunk("A dispute is a customer challenge.", 1, doc_id="faq", section="FAQ 5"),
    ]

    hits = build_retriever(chunks).search("What is a dispute?", top_k=1)

    assert [(h.chunk.doc_id, h.chunk.section) for h in hits] == [("faq", "FAQ 5")]
    assert hits[0].score > 0


def test_retriever_omits_chunks_that_share_no_terms_with_the_query() -> None:
    retriever = Retriever(["Settlement moves funds.", "Authorization checks the card."])

    assert retriever.search("quantum chromodynamics") == []
    assert len(retriever.search("settlement funds", top_k=5)) == 1


def test_retriever_validates_its_inputs() -> None:
    with pytest.raises(ValueError, match="empty"):
        Retriever([])
    with pytest.raises(ValueError, match="top_k"):
        Retriever(["text"]).search("text", top_k=0)


def test_every_gold_phrase_exists_in_its_document() -> None:
    corpus = CAPSTONE / "docs" / "corpus"
    documents = {p.stem: p.read_text(encoding="utf-8") for p in (corpus / "raw").glob("*.md")}
    documents["faqs"] = (corpus / "faqs.md").read_text(encoding="utf-8")
    questions = json.loads((CAPSTONE / "evals" / "questions.json").read_text(encoding="utf-8"))

    answerable = [q for q in questions if q["gold"]]
    assert len(answerable) >= 20
    assert any(not q["gold"] for q in questions), "keep some unanswerable questions"
    for question in answerable:
        for gold in question["gold"]:
            haystack = " ".join(documents[gold["doc"]].split()).lower()
            assert " ".join(gold["phrase"].split()).lower() in haystack, question["id"]
