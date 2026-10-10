# ruff: noqa: E501
"""The prompts live in text files; moving them out of the code must not change what is sent."""

from __future__ import annotations

import re

import pytest

from payments_rag import Chunk, Hit, build_prompt, prompts
from payments_rag.grounding import GroundedAnswer, answerability_prompt

HITS = (
    Hit(
        Chunk(
            "PSD2 bans retailer surcharges for card use.", 0, "psd2", "PSD2 > Fees", "https://eu"
        ),
        1.0,
    ),
    Hit(
        Chunk("Settlement moves funds between banks.", 1, "card", "Lifecycle", "https://card"), 0.5
    ),
)
QUESTION = "Can a shop add a card surcharge?"

# Captured from the prompts as they were written inside the code, before they moved to files.
PLAIN = "Answer the question using ONLY the numbered passages below. Cite the passage number after every claim, like [1]. If the passages do not contain the answer, reply exactly: I don't know based on the provided documents.\n\nPassages:\n[1] PSD2 bans retailer surcharges for card use.\n\n[2] Settlement moves funds between banks.\n\nQuestion: Can a shop add a card surcharge?"
STRICT = "Answer the question using ONLY the numbered passages below. Cite the passage number after every claim, like [1]. Write short sentences and end EVERY sentence with a citation such as [1] or [1][2]. Do not write an introduction, a summary or any sentence that has no citation. If the passages do not contain the answer, reply exactly: I don't know based on the provided documents.\n\nPassages:\n[1] PSD2 bans retailer surcharges for card use.\n\n[2] Settlement moves funds between banks.\n\nQuestion: Can a shop add a card surcharge?"
ABSTAIN = "Reply exactly: I don't know based on the provided documents."
ANSWERABILITY = 'You decide whether numbered passages contain the answer to a question.\n\nQuestion: Can a shop add a card surcharge?\n\nPassages:\n[1] PSD2 bans retailer surcharges for card use.\n\n[2] Settlement moves funds between banks.\n\nReturn a JSON object with these keys:\n- "label": "full" if one passage states the specific fact the question asks for; "partial" if\n  the passages are on the topic but do not state that specific fact; "none" if they do not help.\n- "quote": when the label is "full", copy ONE sentence or phrase that states the answer, exactly\n  as it appears in a passage (word for word). Otherwise an empty string.\nDo not use outside knowledge. A related passage that does not state the specific fact asked for\nis "partial", not "full".\n'


def test_the_answer_prompt_is_unchanged_by_the_move_to_files() -> None:
    answer = GroundedAnswer(QUESTION, False, HITS, "x")

    assert build_prompt(answer) == PLAIN
    assert build_prompt(answer, strict=True) == STRICT


def test_the_abstention_prompt_is_unchanged() -> None:
    assert build_prompt(GroundedAnswer("q", True, (), "r")) == ABSTAIN


def test_the_answerability_prompt_is_unchanged() -> None:
    assert answerability_prompt(QUESTION, HITS) == ANSWERABILITY


def test_every_prompt_file_survives_the_whitespace_fixers() -> None:
    # The pre-commit hooks strip trailing spaces and force one final newline; a prompt that
    # depended on either would change silently when committed.
    for name in prompts.prompt_names():
        text = prompts.load(name)
        assert text.endswith("\n") and not text.endswith("\n\n"), name
        assert not any(line != line.rstrip() for line in text.splitlines()), name


def test_the_version_is_a_short_stable_hash() -> None:
    assert re.fullmatch(r"[0-9a-f]{12}", prompts.prompt_version())
    assert prompts.prompt_version() == prompts.prompt_version()


def test_editing_any_prompt_changes_the_version(monkeypatch: pytest.MonkeyPatch) -> None:
    before = prompts.prompt_version()
    original = prompts.load

    monkeypatch.setattr(
        prompts, "load", lambda name: original(name) + " " if name == "answer" else original(name)
    )

    assert prompts.prompt_version() != before


def test_the_three_production_prompts_exist() -> None:
    assert {"answer", "answerability", "strict_citation_rule"} <= set(prompts.prompt_names())
