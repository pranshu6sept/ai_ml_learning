"""Tool calling: let the model choose how to search, with arguments validated by Pydantic.

The model is offered one tool, ``search_corpus``, and forced to call it. Instead of answering, it
returns the arguments it would call the tool with: the search query plus optional filters (region,
publication date range). We never run anything the model names; we validate the arguments against a
schema and turn them into a ``SearchFilter`` for our own search code.

Why this is safer than parsing free text: the schema lists the allowed regions, so the model cannot
invent one, and the dates are checked again here because a schema on the wire is not a guarantee in
your own process. Why it is still risky: a filter the model chose wrongly (for example "India" for a
question that a global document answers) silently removes the right passages. The graph therefore
drops the filters when its first search finds weak evidence.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .search_filters import SearchFilter

TOOL_NAME = "search_corpus"
TOOL_DESCRIPTION = (
    "Search the payments and banking documents. Use `query` for the topic and the filters only "
    "when the question names a region or regulator, or asks about a period of time."
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class SearchCorpus(BaseModel):
    """The arguments of the ``search_corpus`` tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(description="The topic to search for, as a short search query.")
    jurisdictions: list[Literal["EU", "India", "US", "global"]] = Field(
        description="Restrict to these regions; an empty list means no restriction."
    )
    published_from: str | None = Field(
        description="Only documents published on or after this date, YYYY-MM-DD; null for none."
    )
    published_to: str | None = Field(
        description="Only documents published on or before this date, YYYY-MM-DD; null for none."
    )


def tool_definition() -> dict[str, Any]:
    """The ``tools`` entry that offers ``search_corpus`` to the model."""
    return {
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": TOOL_DESCRIPTION,
            "parameters": SearchCorpus.model_json_schema(),
            "strict": True,
        },
    }


def tool_choice() -> dict[str, Any]:
    """Force the model to call ``search_corpus`` rather than reply in prose."""
    return {"type": "function", "function": {"name": TOOL_NAME}}


def to_filter(args: SearchCorpus) -> SearchFilter:
    """The filters in the tool arguments. A date that is not YYYY-MM-DD is dropped, not trusted."""

    def ok(value: str | None) -> str | None:
        return value if value and _DATE.fullmatch(value) else None

    return SearchFilter(
        jurisdictions=tuple(dict.fromkeys(args.jurisdictions)),
        published_from=ok(args.published_from),
        published_to=ok(args.published_to),
    )
