from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.facets import FacetCount, facet, numeric_facet
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index


def shop() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.add_keyword("colour")
    schema.add_numeric("price")
    schema.seal()
    index = Index(schema=schema, flush_at=3)
    rows = [
        ("wool cat toy", "red", 10),
        ("felt cat bed", "red", 40),
        ("cat scratching post", "blue", 25),
        ("cat treat sachet", "green", 5),
        ("cat carrier", "blue", 60),
        ("dog lead", "red", 15),
    ]
    for body, colour, price in rows:
        index.add({"body": body, "colour": colour, "price": price})
    index.flush()
    return index


class TestKeywordFacets:
    def test_counts_run_over_every_match_not_the_page(self):
        result = facet(shop(), parse("cat"), "colour", top_n=2)
        assert result.matched_docs == 5
        assert result.top == (
            FacetCount(value="blue", count=2),
            FacetCount(value="red", count=2),
        )

    def test_the_tail_is_counted_not_dropped(self):
        result = facet(shop(), parse("cat"), "colour", top_n=2)
        assert result.distinct_beyond == 1
        assert result.line() == "colour: blue (2), red (2) and 1 more"

    def test_ties_break_alphabetically(self):
        result = facet(shop(), parse("cat"), "colour", top_n=3)
        assert [held.value for held in result.top] == [
            "blue",
            "red",
            "green",
        ]

    def test_tombstones_never_count(self):
        index = shop()
        index.delete(0)
        result = facet(index, parse("cat"), "colour", top_n=3)
        red = next(h for h in result.top if h.value == "red")
        assert red.count == 1

    def test_text_fields_are_refused(self):
        with pytest.raises(Invalid, match="free text"):
            facet(shop(), parse("cat"), "body")

    def test_zero_rows_is_refused(self):
        with pytest.raises(Invalid, match="blank sidebar"):
            facet(shop(), parse("cat"), "colour", top_n=0)


class TestNumericFacets:
    def test_buckets_count_half_open_ranges(self):
        rows = numeric_facet(
            shop(), parse("cat"), "price", edges=(0, 20, 50)
        )
        assert rows[0] == FacetCount(value="[0, 20)", count=2)
        assert rows[1] == FacetCount(value="[20, 50)", count=2)

    def test_the_overflow_is_named_not_vanished(self):
        rows = numeric_facet(
            shop(), parse("cat"), "price", edges=(0, 20, 50)
        )
        assert rows[-1] == FacetCount(value="outside all buckets", count=1)

    def test_backwards_edges_are_refused(self):
        with pytest.raises(Invalid, match="strictly increasing"):
            numeric_facet(shop(), parse("cat"), "price", edges=(50, 20))

    def test_one_edge_is_not_a_bucketing(self):
        with pytest.raises(Invalid, match="two edges"):
            numeric_facet(shop(), parse("cat"), "price", edges=(10,))

    def test_keyword_fields_refuse_buckets(self):
        with pytest.raises(Invalid, match="need numbers"):
            numeric_facet(
                shop(), parse("cat"), "colour", edges=(0, 10)
            )
