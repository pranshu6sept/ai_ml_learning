import json
import math

from payments_rag import (
    CORRECTNESS_SCORES,
    RELEVANCE_SCORES,
    Hit,
    agreement,
    correctness_prompt,
    faithfulness_prompt,
    parse_faithfulness,
    parse_verdict,
    relevance_prompt,
)
from payments_rag.chunking import Chunk

EVIDENCE = (Hit(Chunk("Settlement moves funds between banks.", 0, doc_id="cards"), 1.0),)


def test_prompts_contain_every_input_and_no_leftover_placeholder() -> None:
    prompts = [
        faithfulness_prompt("Funds move [1].", EVIDENCE),
        relevance_prompt("What is settlement?", "Funds move [1]."),
        correctness_prompt("What is settlement?", "Funds move between banks.", "Funds move [1]."),
    ]

    assert "[1] Settlement moves funds between banks." in prompts[0]
    assert "What is settlement?" in prompts[1] and "Funds move [1]." in prompts[1]
    assert "Funds move between banks." in prompts[2]
    assert all("<<" not in p for p in prompts)


def test_faithfulness_is_the_share_of_supported_claims() -> None:
    raw = json.dumps(
        {
            "claims": [
                {"claim": "funds move", "supported": True},
                {"claim": "within one hour", "supported": False},
            ]
        }
    )

    result = parse_faithfulness(raw)

    assert result is not None
    assert (result.supported, result.total, result.score) == (1, 2, 0.5)
    assert result.unsupported == ("within one hour",)


def test_no_claims_gives_an_undefined_score_not_a_perfect_one() -> None:
    result = parse_faithfulness(json.dumps({"claims": []}))

    assert result is not None and math.isnan(result.score)


def test_malformed_faithfulness_replies_are_rejected() -> None:
    for raw in (
        "not json",
        "[]",
        json.dumps({"claims": "none"}),
        json.dumps({"claims": [{"claim": "x", "supported": "yes"}]}),
        json.dumps({"claims": ["x"]}),
        json.dumps({"other": 1}),
    ):
        assert parse_faithfulness(raw) is None, raw


def test_verdicts_map_to_scores_and_unknown_words_are_rejected() -> None:
    assert parse_verdict('{"verdict": "direct"}', RELEVANCE_SCORES) == ("direct", 1.0)
    assert parse_verdict('{"verdict": "partial"}', CORRECTNESS_SCORES) == ("partial", 0.5)
    assert parse_verdict('{"verdict": "incorrect"}', CORRECTNESS_SCORES) == ("incorrect", 0.0)
    for raw in ('{"verdict": "great"}', '{"verdict": 1}', "nope", "[]", "{}"):
        assert parse_verdict(raw, RELEVANCE_SCORES) is None, raw
    assert parse_verdict('{"verdict": "correct"}', RELEVANCE_SCORES) is None  # wrong vocabulary


def test_identical_labels_agree_perfectly_and_opposite_labels_are_worse_than_chance() -> None:
    assert agreement(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == (1.0, 1.0)
    observed, kappa = agreement(["a", "b", "a", "b"], ["b", "a", "b", "a"])
    assert observed == 0.0 and kappa == -1.0


def test_kappa_discounts_agreement_that_chance_would_produce() -> None:
    # Both judges say "ok" almost always: 9 of 10 agree, but most of that is chance.
    observed, kappa = agreement(["ok"] * 9 + ["bad"], ["ok"] * 8 + ["bad", "ok"])

    assert observed == 0.8
    assert kappa < 0.0  # the one "bad" each judge gave landed on different items


def test_when_both_judges_use_one_label_kappa_is_undefined_but_agreement_is_one() -> None:
    observed, kappa = agreement(["ok", "ok"], ["ok", "ok"])

    assert observed == 1.0 and math.isnan(kappa)


def test_judges_must_label_the_same_number_of_items() -> None:
    import pytest

    with pytest.raises(ValueError, match="same items"):
        agreement(["a"], ["a", "b"])
    assert all(math.isnan(v) for v in agreement([], []))
