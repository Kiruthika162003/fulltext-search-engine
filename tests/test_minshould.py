from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.minshould import (
    MinShouldMatch,
    dial_report,
    floor_from_percent,
    matching_docs,
)
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder

TERMS = ("cat", "dog", "bird")


def aviary() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "cat dog bird together"})
    builder.add({"body": "cat dog only"})
    builder.add({"body": "bird alone on a wire"})
    builder.add({"body": "nothing relevant"})
    return builder.seal("aviary")


class TestTheRounding:
    def test_percentages_round_toward_strictness(self):
        assert floor_from_percent(5, 60) == 3
        assert floor_from_percent(4, 60) == 3
        assert floor_from_percent(3, 100) == 3
        assert floor_from_percent(10, 1) == 1

    def test_degenerate_inputs_are_refused(self):
        with pytest.raises(Invalid):
            floor_from_percent(0, 50)
        with pytest.raises(Invalid):
            floor_from_percent(5, 0)
        with pytest.raises(Invalid):
            floor_from_percent(5, 101)


class TestTheSpec:
    def test_a_floor_of_zero_is_or_in_a_costume(self):
        with pytest.raises(Invalid, match="say OR"):
            MinShouldMatch(terms=TERMS, floor=0)

    def test_six_of_five_is_a_bug_upstream(self):
        with pytest.raises(Invalid, match="not an enthusiasm"):
            MinShouldMatch(terms=TERMS, floor=4)


class TestTheDial:
    def test_floor_one_is_or(self):
        docs = matching_docs(
            aviary(), "body", MinShouldMatch(terms=TERMS, floor=1)
        )
        assert [doc for doc, _ in docs] == [0, 1, 2]

    def test_the_middle_stop_holds_the_floor(self):
        docs = matching_docs(
            aviary(), "body", MinShouldMatch(terms=TERMS, floor=2)
        )
        assert docs == [(0, 3), (1, 2)]

    def test_the_top_stop_is_and(self):
        docs = matching_docs(
            aviary(), "body", MinShouldMatch(terms=TERMS, floor=3)
        )
        assert docs == [(0, 3)]

    def test_tombstones_never_meet_the_floor(self):
        segment = aviary()
        segment.delete(0)
        docs = matching_docs(
            segment, "body", MinShouldMatch(terms=TERMS, floor=3)
        )
        assert docs == []

    def test_the_report_walks_or_to_and(self):
        page = dial_report(aviary(), "body", TERMS)
        assert page.splitlines() == [
            "3 terms, the dial from OR to AND:",
            "  OR: 3 document(s)",
            "  at least 2: 2 document(s)",
            "  AND: 1 document(s)",
        ]
