import pytest

from payments_rag import SearchFilter, build_odata


def test_no_strategy_and_no_filters_means_no_filter() -> None:
    assert build_odata(None) is None
    assert build_odata(None, SearchFilter()) is None
    assert SearchFilter().is_empty()


def test_the_strategy_alone_keeps_the_filter_the_index_always_used() -> None:
    assert build_odata("structure_aware") == "strategy eq 'structure_aware'"


def test_each_metadata_filter_becomes_one_clause_joined_with_and() -> None:
    flt = SearchFilter(
        doc_ids=("psd2_overview", "cfpb_credit_card_disputes"),
        jurisdictions=("India",),
        source_types=("regulator_public_docs",),
        published_from="2024-01-01",
        published_to="2025-12-31",
    )

    assert build_odata("structure_aware", flt) == (
        "strategy eq 'structure_aware'"
        " and search.in(doc_id, 'psd2_overview,cfpb_credit_card_disputes', ',')"
        " and search.in(jurisdiction, 'India', ',')"
        " and search.in(source_type, 'regulator_public_docs', ',')"
        " and published ge 2024-01-01T00:00:00Z"
        " and published le 2025-12-31T00:00:00Z"
    )
    assert not flt.is_empty()


@pytest.mark.parametrize("bad", ["India' or true or '", "a,b", 'x"y', ""])
def test_a_value_cannot_break_out_of_the_filter(bad: str) -> None:
    with pytest.raises(ValueError, match="only letters"):
        build_odata(None, SearchFilter(jurisdictions=(bad,)))


@pytest.mark.parametrize("bad", ["2025/01/01", "01-01-2025", "2025-1-1", "yesterday"])
def test_dates_must_be_year_month_day(bad: str) -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_odata(None, SearchFilter(published_from=bad))
