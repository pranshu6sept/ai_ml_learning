import json
import re
from pathlib import Path

from payments_rag import strip_sections

CORPUS = Path(__file__).resolve().parents[1] / "docs" / "corpus"
REQUIRED = {"id", "title", "source_type", "jurisdiction", "url", "file", "status", "verification"}
VERIFICATION = {
    "fetched",
    "fetched_and_search_summary",
    "via_search_summary",
    "author_written_unverified",
    "author_written_cross_checked",
    "author_written_partly_verified",
}


def _sources() -> list[dict[str, object]]:
    return json.loads((CORPUS / "sources.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_every_source_has_the_required_fields_and_a_known_verification() -> None:
    for source in _sources():
        assert source.keys() >= REQUIRED, source["id"]
        assert source["verification"] in VERIFICATION, source["id"]


def test_every_source_file_exists_and_is_registered_once() -> None:
    files = [str(source["file"]) for source in _sources()]

    assert len(files) == len(set(files))
    for name in files:
        assert (CORPUS / name).is_file(), name
    raw_on_disk = {f"raw/{p.name}" for p in (CORPUS / "raw").glob("*.md")}
    assert raw_on_disk <= set(files), "a raw document is missing from sources.json"


def test_documents_fetched_from_the_web_record_when_they_were_retrieved() -> None:
    for source in _sources():
        if str(source["verification"]).startswith(("fetched", "via_search")):
            assert source.get("retrieved"), source["id"]


def test_meta_sections_are_removed_by_ingestion() -> None:
    meta = ("Practical RAG relevance", "Example questions this helps answer")
    for path in (CORPUS / "raw").glob("*.md"):
        cleaned = strip_sections(path.read_text(encoding="utf-8"), meta).lower()
        assert "practical rag relevance" not in cleaned, path.name
        assert "example questions" not in cleaned, path.name


def test_every_source_states_its_publication_date_or_an_explicit_null() -> None:
    for source in _sources():
        assert "published" in source, source["id"]
        published = source["published"]
        assert published is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(published)), source["id"]


def test_repealed_documents_say_so_in_their_text_and_name_their_replacement() -> None:
    ids = {str(s["id"]) for s in _sources()}
    repealed = [s for s in _sources() if s["status"] == "repealed"]
    assert repealed, "the 2016 RBI circular should be marked repealed"
    for source in repealed:
        text = (CORPUS / str(source["file"])).read_text(encoding="utf-8").lower()
        assert "repealed" in text, source["id"]
        assert source["superseded_by"] in ids, source["id"]


def test_gold_phrases_in_every_question_file_exist_in_their_documents() -> None:
    documents = {
        p.stem: _flat(p.read_text(encoding="utf-8")) for p in (CORPUS / "raw").glob("*.md")
    }
    documents["faqs"] = _flat((CORPUS / "faqs.md").read_text(encoding="utf-8"))
    for path in sorted((CORPUS.parents[1] / "evals").glob("questions*.json")):
        for question in json.loads(path.read_text(encoding="utf-8")):
            for gold in question["gold"]:
                assert _flat(gold["phrase"]) in documents[gold["doc"]], (path.name, question["id"])


def _flat(text: str) -> str:
    return " ".join(text.split()).lower()


def test_independent_questions_name_their_source_and_ids_are_unique_across_files() -> None:
    evals = CORPUS.parents[1] / "evals"
    seen: set[str] = set()
    for path in sorted(evals.glob("questions*.json")):
        for question in json.loads(path.read_text(encoding="utf-8")):
            assert question["id"] not in seen, f"duplicate id {question['id']} in {path.name}"
            seen.add(question["id"])

    independent = json.loads((evals / "questions_independent.json").read_text(encoding="utf-8"))
    texts = [q["question"] for q in independent]
    assert len(texts) == len(set(texts)), "a question appears twice"
    assert all(str(q["source"]).startswith("https://") for q in independent)
    assert sum(bool(q["gold"]) for q in independent) >= 5
    assert sum(not q["gold"] for q in independent) >= 20, "keep the unanswerable ones"
