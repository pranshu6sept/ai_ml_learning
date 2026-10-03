"""Metadata filters for Azure AI Search: by chunking strategy, source document, region and date.

Filters narrow the candidates *before* ranking (Azure's default pre-filter), so a question about one
region is answered only from that region's documents. They turn into an OData ``$filter`` string.

Matching is exact. ``jurisdictions=("India",)`` does not also match documents marked ``global``, and
a date filter drops documents with no ``published`` date (7 of the 11 corpus documents have none).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VALUE = re.compile(r"[\w .\-]+")  # no quotes or commas, so a value cannot break out of the filter
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _checked(values: tuple[str, ...], what: str) -> str:
    for value in values:
        if not _VALUE.fullmatch(value):
            raise ValueError(f"{what} {value!r}: only letters, digits, spaces, '.', '_' and '-'")
    return ",".join(values)


def _date(value: str, what: str) -> str:
    if not _DATE.fullmatch(value):
        raise ValueError(f"{what} {value!r} is not YYYY-MM-DD")
    return f"{value}T00:00:00Z"


@dataclass(frozen=True)
class SearchFilter:
    """Which chunks may be returned. An empty field means no restriction on that field."""

    doc_ids: tuple[str, ...] = ()  # source documents, by file stem (e.g. "psd2_overview")
    jurisdictions: tuple[str, ...] = ()  # region, e.g. "India", "EU", "US", "global"
    source_types: tuple[str, ...] = ()  # e.g. "regulator_public_docs"
    published_from: str | None = None  # YYYY-MM-DD, on or after
    published_to: str | None = None  # YYYY-MM-DD, on or before

    def is_empty(self) -> bool:
        return not (
            self.doc_ids
            or self.jurisdictions
            or self.source_types
            or self.published_from
            or self.published_to
        )


def build_odata(strategy: str | None, filters: SearchFilter | None = None) -> str | None:
    """Combine the strategy and metadata filters into one OData filter (None means no filter)."""
    clauses: list[str] = []
    if strategy:
        clauses.append(f"strategy eq '{_checked((strategy,), 'strategy')}'")
    if filters is not None:
        for field, values in (
            ("doc_id", filters.doc_ids),
            ("jurisdiction", filters.jurisdictions),
            ("source_type", filters.source_types),
        ):
            if values:
                clauses.append(f"search.in({field}, '{_checked(values, field)}', ',')")
        if filters.published_from:
            clauses.append(f"published ge {_date(filters.published_from, 'published_from')}")
        if filters.published_to:
            clauses.append(f"published le {_date(filters.published_to, 'published_to')}")
    return " and ".join(clauses) or None
