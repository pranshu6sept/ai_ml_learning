import json
from pathlib import Path
from typing import Any

import pytest

EVALS = Path(__file__).resolve().parents[1] / "evals"


@pytest.fixture()
def golden(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    monkeypatch.syspath_prepend(str(EVALS))
    lines = (EVALS / "golden_set.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line]


def test_the_golden_set_is_between_50_and_100_questions_with_unique_ids(
    golden: list[dict[str, Any]],
) -> None:
    ids = [q["id"] for q in golden]

    assert 50 <= len(golden) <= 100
    assert len(ids) == len(set(ids))


def test_every_answerable_question_has_gold_passages_and_a_reference_answer(
    golden: list[dict[str, Any]],
) -> None:
    for q in golden:
        if q["expected"] == "answer":
            assert q["gold"], q["id"]
            assert q["reference_answer"] and q["reference_answer"].strip(), q["id"]
        else:
            assert q["expected"] == "refuse", q["id"]
            assert not q["gold"] and q["reference_answer"] is None, q["id"]


def test_the_committed_golden_set_matches_what_the_build_script_makes(
    golden: list[dict[str, Any]],
) -> None:
    import build_golden_set  # type: ignore[import-not-found]

    assert golden == build_golden_set.build()


def test_reference_answers_do_not_contain_unfilled_placeholders(
    golden: list[dict[str, Any]],
) -> None:
    for q in golden:
        text = q["reference_answer"] or ""
        assert not any(marker in text for marker in ("TODO", "XXX", "<<", "??")), q["id"]
