from types import SimpleNamespace
from typing import Any

from payments_rag import (
    NO_ANSWER,
    AzureChatGenerator,
    AzureSettings,
    GroundedAnswer,
    Hit,
    build_prompt,
    enforce_citations,
    split_sentences,
)
from payments_rag.chunking import Chunk


def _answer() -> GroundedAnswer:
    hits = tuple(Hit(Chunk(f"passage {n}", n, doc_id="d"), 1.0) for n in (1, 2))
    return GroundedAnswer("What is X?", False, hits, "test")


def test_every_sentence_that_has_a_valid_citation_is_kept_unchanged() -> None:
    reply = "X is a standard [1]. It is used by banks [2]."

    result = enforce_citations(reply, 2)

    assert result.text == reply
    assert result.dropped == ()
    assert not result.refused


def test_a_sentence_with_no_citation_is_dropped_and_reported() -> None:
    reply = "Here is what the passages say. X is a standard [1]. It is widely used."

    result = enforce_citations(reply, 2)

    assert result.text == "X is a standard [1]."
    assert result.dropped == ("Here is what the passages say.", "It is widely used.")


def test_a_citation_to_a_passage_that_does_not_exist_is_removed_and_counted() -> None:
    result = enforce_citations("X is a standard [1][5]. Another claim [9].", 2)

    assert result.text == "X is a standard [1]."
    assert result.invalid_markers == 2
    assert result.dropped == ("Another claim [9].",)


def test_a_citation_written_after_the_full_stop_belongs_to_the_sentence_before_it() -> None:
    assert split_sentences("X is a standard. [1] Y follows [2].") == [
        "X is a standard [1].",
        "Y follows [2].",
    ]
    result = enforce_citations("X is a standard. [1] Y follows. [2]", 2)
    assert result.text == "X is a standard [1]. Y follows [2]."
    assert result.dropped == ()


def test_a_citation_alone_on_its_own_line_joins_the_line_above() -> None:
    assert split_sentences("X is a standard\n[1]") == ["X is a standard [1]"]


def test_a_reply_with_no_valid_citation_becomes_the_refusal() -> None:
    result = enforce_citations("X is a standard. Banks use it.", 2)

    assert result.text == NO_ANSWER
    assert result.refused
    assert len(result.dropped) == 2


def test_a_refusal_is_passed_through_untouched() -> None:
    result = enforce_citations("I don't know based on the provided documents.", 2)

    assert result.refused
    assert result.dropped == ()


def test_the_strict_prompt_adds_the_per_sentence_rule_and_the_default_does_not() -> None:
    assert "end EVERY sentence" in build_prompt(_answer(), strict=True)
    assert "end EVERY sentence" not in build_prompt(_answer())
    assert "ONLY the numbered passages" in build_prompt(_answer())


class _ScriptedModel:
    """A fake chat client that returns scripted replies in order and records the prompts it got."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.prompts.append(kwargs["messages"][0]["content"])
        message = SimpleNamespace(content=self.replies.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _generator(model: _ScriptedModel) -> AzureChatGenerator:
    return AzureChatGenerator(
        AzureSettings("https://oai", "emb", "chat", "https://s"), client=model
    )


def test_a_retry_that_cites_every_sentence_replaces_the_answer_with_a_dropped_lead() -> None:
    model = _ScriptedModel(
        "No, shops cannot charge extra. The directive bans surcharges [1].",
        "No, shops cannot charge extra [1]. The directive bans surcharges [1].",
    )

    result = _generator(model).generate_cited(_answer())

    assert result.text == "No, shops cannot charge extra [1]. The directive bans surcharges [1]."
    assert result.dropped == ()
    assert (
        "No, shops cannot charge extra." in model.prompts[1]
    )  # the retry names the uncited sentence


def test_no_retry_is_made_when_every_sentence_is_already_cited() -> None:
    model = _ScriptedModel("X is a standard [1].")

    result = _generator(model).generate_cited(_answer())

    assert result.text == "X is a standard [1]."
    assert len(model.prompts) == 1


def test_a_retry_that_is_worse_is_ignored() -> None:
    model = _ScriptedModel(
        "Lead sentence. X is a standard [1].",
        "I don't know based on the provided documents.",
    )

    result = _generator(model).generate_cited(_answer())

    assert result.text == "X is a standard [1]."
    assert result.dropped == ("Lead sentence.",)


def test_with_no_retries_the_uncited_sentence_is_simply_dropped() -> None:
    model = _ScriptedModel("Lead sentence. X is a standard [1].")

    result = _generator(model).generate_cited(_answer(), retries=0)

    assert result.dropped == ("Lead sentence.",)
    assert len(model.prompts) == 1


def test_a_retry_that_drops_as_many_sentences_as_the_first_attempt_is_ignored() -> None:
    model = _ScriptedModel(
        "No, shops cannot charge extra. The directive bans surcharges [1].",
        "This is because the directive bans surcharges [1]. It also limits fees. Not cited.",
    )

    result = _generator(model).generate_cited(_answer())

    assert result.text == "The directive bans surcharges [1]."  # the first attempt, kept
    assert len(model.prompts) == 2
