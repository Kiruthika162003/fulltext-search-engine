from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder
from quarry.spans import before, near, phrase_via_spans
from quarry.tokenize import Analyzer


def logbook() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "error then timeout on the gateway"})
    builder.add({"body": "timeout preceded the error report"})
    builder.add({"body": "error logged; database timeout followed later"})
    builder.add({"body": "an error without incident"})
    segment = builder.seal("logbook")
    return segment


class TestNear:
    def test_near_matches_either_order(self):
        matches = near(
            logbook(), Analyzer(), "body", "error", "timeout", 3
        )
        assert [match.doc for match in matches] == [0, 1, 2]

    def test_the_distance_is_a_real_fence(self):
        matches = near(
            logbook(), Analyzer(), "body", "error", "timeout", 2
        )
        assert [match.doc for match in matches] == [0, 1]

    def test_the_window_is_reported_exactly(self):
        match = near(
            logbook(), Analyzer(), "body", "error", "timeout", 3
        )[0]
        assert match.window() == 2
        assert "2 apart" in match.line()

    def test_absent_pairs_match_nowhere(self):
        assert (
            near(logbook(), Analyzer(), "body", "error", "zeppelin", 5)
            == []
        )


class TestBefore:
    def test_order_is_enforced(self):
        matches = before(
            logbook(), Analyzer(), "body", "error", "timeout", 3
        )
        assert [match.doc for match in matches] == [0, 2]

    def test_the_reverse_order_finds_the_other_document(self):
        matches = before(
            logbook(), Analyzer(), "body", "timeout", "error", 3
        )
        assert [match.doc for match in matches] == [1]

    def test_tombstones_never_match(self):
        segment = logbook()
        segment.delete(0)
        matches = before(
            segment, Analyzer(), "body", "error", "timeout", 3
        )
        assert [match.doc for match in matches] == [2]


class TestTheContract:
    def test_distance_zero_is_refused(self):
        with pytest.raises(Invalid, match="adjacency"):
            near(logbook(), Analyzer(), "body", "error", "timeout", 0)

    def test_stopword_spans_constrain_nothing(self):
        with pytest.raises(Invalid, match="constrains nothing"):
            near(logbook(), Analyzer(), "body", "the", "timeout", 2)

    def test_before_at_one_is_the_phrase(self):
        schema = Schema()
        schema.add_text("body")
        schema.seal()
        builder = SegmentBuilder(schema=schema)
        builder.add({"body": "deep work matters"})
        builder.add({"body": "work runs deep"})
        segment = builder.seal("phrases")
        assert phrase_via_spans(
            segment, Analyzer(), "body", "deep", "work"
        ) == [0]
