import json
from types import SimpleNamespace
from typing import Any

import pytest

from payments_rag import AzureChatGenerator, AzureSettings
from payments_rag.structured import (
    CitedAnswer,
    QueryRewrite,
    Route,
    StructuredOutputError,
    parse,
    response_format,
)

SETTINGS = AzureSettings("https://o", "emb", "chat", "https://s")


class Recorder:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.sent: list[dict[str, Any]] = []
        self.completions = self
        self.chat = self

    def create(self, **kwargs: Any) -> Any:
        self.sent.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))]
        )


def test_the_schema_forbids_extra_fields_and_requires_every_field() -> None:
    schema = response_format(CitedAnswer)["json_schema"]

    assert schema["strict"] is True and schema["name"] == "CitedAnswer"
    body = schema["schema"]
    assert body["additionalProperties"] is False
    assert set(body["required"]) == {"answer", "citations", "confidence"}
    assert body["properties"]["confidence"]["enum"] == ["high", "medium", "low"]


def test_a_valid_reply_becomes_a_typed_object() -> None:
    raw = json.dumps({"answer": "Funds move [1].", "citations": [1], "confidence": "high"})

    answer = parse(CitedAnswer, raw)

    assert answer.citations == [1] and answer.confidence == "high"


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        json.dumps({"label": "in_scope"}),  # missing reason
        json.dumps({"label": "maybe", "reason": "x"}),  # label outside the allowed values
        json.dumps({"label": "in_scope", "reason": "x", "extra": 1}),  # extra field
    ],
)
def test_a_reply_that_does_not_fit_the_shape_is_rejected(raw: str) -> None:
    with pytest.raises(StructuredOutputError):
        parse(Route, raw)


def test_complete_structured_sends_the_schema_and_returns_a_validated_model() -> None:
    client = Recorder(json.dumps({"query": "pacs.008 customer credit transfer"}))
    generator = AzureChatGenerator(SETTINGS, client=client)

    result = generator.complete_structured("rewrite this", QueryRewrite)

    assert result.query == "pacs.008 customer credit transfer"
    assert client.sent[0]["response_format"]["json_schema"]["name"] == "QueryRewrite"


def test_complete_structured_raises_when_the_model_returns_the_wrong_shape() -> None:
    generator = AzureChatGenerator(SETTINGS, client=Recorder(json.dumps({"q": "x"})))

    with pytest.raises(StructuredOutputError):
        generator.complete_structured("rewrite this", QueryRewrite)


def test_json_mode_and_schema_are_separate_requests() -> None:
    client = Recorder("{}")
    generator = AzureChatGenerator(SETTINGS, client=client)

    generator.complete("a", json_mode=True)
    generator.complete("b")

    assert client.sent[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in client.sent[1]
