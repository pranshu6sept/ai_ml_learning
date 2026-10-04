"""Typed shapes for what the language model must return, and the JSON schema that enforces them.

Instead of asking a model for free text and parsing it with regular expressions, the graph asks for
JSON that matches a Pydantic model. Two layers protect the pipeline:

1. the request carries a JSON schema (``response_format``) so the service constrains the reply;
2. the reply is validated again with Pydantic, because a constraint on the wire is not a guarantee
   in your own process (a different model, an older API version, or a truncated reply can break it).

A reply that fails validation raises ``StructuredOutputError``; the caller decides whether to retry.
All models forbid extra fields and have no defaults, which is what the service's strict mode needs.
"""

from __future__ import annotations

from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)


class StructuredOutputError(ValueError):
    """The model's reply was not valid JSON for the requested shape."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Route(_Strict):
    """Where a question should go."""

    label: Literal["in_scope", "out_of_scope", "chit_chat"]
    reason: str = Field(description="One short sentence explaining the choice.")


class QueryRewrite(_Strict):
    """A better search query for the same question."""

    query: str = Field(description="The rewritten search query, a single line.")


class CitedAnswer(_Strict):
    """An answer written only from the numbered passages."""

    answer: str = Field(description="The answer; every sentence ends with a citation like [1].")
    citations: list[int] = Field(description="The passage numbers the answer relies on.")
    confidence: Literal["high", "medium", "low"] = Field(
        description="How completely the passages answer the question (the model's own estimate)."
    )


def response_format(model: type[BaseModel]) -> dict[str, Any]:
    """The ``response_format`` argument that makes the service return JSON for ``model``."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": model.__name__,
            "schema": model.model_json_schema(),
            "strict": True,
        },
    }


def parse(model: type[ModelT], raw: str) -> ModelT:
    """Validate a model reply; raises ``StructuredOutputError`` with the reason if it is wrong."""
    try:
        return model.model_validate_json(raw)
    except ValidationError as error:
        raise StructuredOutputError(f"{model.__name__}: {error.errors()[0]['msg']}") from error
