import json
from types import SimpleNamespace

from payments_rag import (
    Answerability,
    AzureChatGenerator,
    AzureSettings,
    Hit,
    answerability_prompt,
    parse_answerability,
)
from payments_rag.chunking import Chunk

PASSAGE = (
    "## Business areas\n- pain: payments initiation, messages that support starting a payment.\n"
    "- pacs: payments clearing and settlement."
)
EVIDENCE = (Hit(Chunk(PASSAGE, 0, doc_id="iso"), 1.0),)


def _reply(label: str, quote: str = "") -> str:
    return json.dumps({"label": label, "quote": quote})


def test_a_full_claim_with_a_quote_that_really_is_in_the_passages_can_answer() -> None:
    result = parse_answerability(_reply("full", "pacs: payments clearing and settlement"), EVIDENCE)

    assert result == Answerability("full", "pacs: payments clearing and settlement", True)
    assert result.can_answer


def test_a_full_claim_with_an_invented_quote_cannot_answer() -> None:
    result = parse_answerability(
        _reply("full", "pacs.008 is the message for a customer credit transfer"), EVIDENCE
    )

    assert result.label == "full"
    assert not result.quote_found
    assert not result.can_answer


def test_quote_matching_ignores_case_spacing_and_markdown_marks() -> None:
    quote = "**PACS:**  payments   clearing and SETTLEMENT"

    assert parse_answerability(_reply("full", quote), EVIDENCE).can_answer


def test_a_partial_or_none_label_never_answers_even_with_a_real_quote() -> None:
    quote = "pain: payments initiation, messages that support starting a payment"

    assert not parse_answerability(_reply("partial", quote), EVIDENCE).can_answer
    assert not parse_answerability(_reply("none", quote), EVIDENCE).can_answer


def test_a_very_short_quote_is_not_accepted_as_proof() -> None:
    assert not parse_answerability(_reply("full", "pain"), EVIDENCE).can_answer


def test_unreadable_or_unexpected_replies_count_as_none() -> None:
    for raw in ("not json", "", "[]", json.dumps({"label": "definitely"})):
        assert parse_answerability(raw, EVIDENCE).label == "none"
        assert not parse_answerability(raw, EVIDENCE).can_answer


def test_the_prompt_numbers_the_passages_and_asks_for_a_word_for_word_quote() -> None:
    prompt = answerability_prompt("What is pacs?", EVIDENCE)

    assert "Question: What is pacs?" in prompt
    assert "[1] ## Business areas" in prompt
    assert "word for word" in prompt


def test_the_generator_asks_for_json_and_returns_the_checked_result() -> None:
    sent: list[dict[str, object]] = []

    def create(**kwargs: object) -> SimpleNamespace:
        sent.append(kwargs)
        content = _reply("full", "pacs: payments clearing and settlement")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    settings = AzureSettings("https://oai", "emb", "chat", "https://search")
    generator = AzureChatGenerator(
        settings,
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )

    result = generator.check_answerability("What is pacs?", EVIDENCE)

    assert result.can_answer
    assert sent[0]["response_format"] == {"type": "json_object"}
