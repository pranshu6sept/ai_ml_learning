import json
from types import SimpleNamespace
from typing import Any

from payments_rag import AzureChatGenerator, AzureSettings, Hit
from payments_rag.ask import ask
from payments_rag.chunking import Chunk
from payments_rag.grounding import NO_ANSWER

PASSAGE = "pacs.008 is the FI to FI customer credit transfer message."
HIT = Hit(Chunk(PASSAGE, 0, doc_id="iso", section="ISO > pacs", source_url="http://x"), 1.0)
SETTINGS = AzureSettings("https://s", "k", "https://o", "chat", "emb")


class FakeSearch:
    def __init__(self, hits: list[Hit]) -> None:
        self._hits = hits

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        return self._hits[:top_k]


class ScriptedClient:
    """Returns the scripted replies in order, one per model call."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **_: Any) -> Any:
        self.calls += 1
        message = SimpleNamespace(content=self.replies.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _generator(replies: list[str]) -> tuple[AzureChatGenerator, ScriptedClient]:
    client = ScriptedClient(replies)
    return AzureChatGenerator(SETTINGS, client=client), client


def _verdict(label: str, quote: str = "") -> str:
    return json.dumps({"label": label, "quote": quote})


def test_a_supported_question_gets_a_cited_answer_and_its_sources() -> None:
    generator, client = _generator(
        [_verdict("full", PASSAGE), "pacs.008 moves a credit transfer [1]."]
    )

    result = ask("What is pacs.008?", FakeSearch([HIT]), generator)

    assert not result.refused
    assert result.text == "pacs.008 moves a credit transfer [1]."
    assert result.sources == ("[1] iso > ISO > pacs (http://x)",)
    assert client.calls == 2


def test_only_passages_the_answer_cites_are_listed_as_sources() -> None:
    other = Hit(Chunk("Unrelated.", 1, doc_id="other", section="S", source_url="http://y"), 0.5)
    generator, _ = _generator([_verdict("full", PASSAGE), "pacs.008 moves a transfer [1]."])

    result = ask("What is pacs.008?", FakeSearch([HIT, other]), generator)

    assert result.sources == ("[1] iso > ISO > pacs (http://x)",)


def test_an_unsupported_question_is_refused_without_writing_an_answer() -> None:
    generator, client = _generator([_verdict("none")])

    result = ask("Who won the cup?", FakeSearch([HIT]), generator)

    assert result.refused
    assert result.text == NO_ANSWER
    assert result.sources == ()
    assert client.calls == 1  # only the answerability check ran


def test_an_invented_quote_is_refused() -> None:
    generator, _ = _generator([_verdict("full", "pacs.008 settles in two hours")])

    result = ask("How fast?", FakeSearch([HIT]), generator)

    assert result.refused
    assert "quote was not found" in result.reason


def test_no_search_results_refuses_without_calling_the_model() -> None:
    generator, client = _generator([])

    result = ask("anything", FakeSearch([]), generator)

    assert result.refused
    assert client.calls == 0
