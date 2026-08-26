from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.proximity import (
    SpanWindow,
    near,
    proximity_bonus,
    span_windows,
    tightest_window,
)
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder


def prose() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "black cat sleeping"})
    builder.add({"body": "black dog and a distant lonely cat"})
    builder.add({"body": "cat fur on a black coat near the door"})
    builder.add({"body": "nothing relevant here"})
    return builder.seal("prose")


class TestTightestWindow:
    def test_the_pointer_walk_finds_the_squeeze(self):
        assert tightest_window([(0, 10), (2, 9)]) == (9, 10)

    def test_interleaved_positions_still_squeeze(self):
        assert tightest_window([(1, 4, 9), (2, 5), (3, 6)]) == (1, 3)

    def test_one_list_is_a_point(self):
        assert tightest_window([(7, 11)]) == (7, 7)

    def test_an_empty_list_means_no_window(self):
        assert tightest_window([(1, 2), ()]) is None

    def test_no_lists_is_refused(self):
        with pytest.raises(Invalid):
            tightest_window([])


class TestSpans:
    def test_each_holding_document_reports_its_window(self):
        windows = span_windows(prose(), "body", ["black", "cat"])
        assert windows[0] == SpanWindow(doc=0, start=0, end=1)
        assert windows[1].doc == 1
        assert windows[1].width() > 1

    def test_a_term_missing_everywhere_means_no_spans(self):
        assert span_windows(prose(), "body", ["black", "zebra"]) == []

    def test_empty_terms_are_refused(self):
        with pytest.raises(Invalid):
            span_windows(prose(), "body", [])


class TestTheBonus:
    def test_adjacency_earns_the_full_bonus(self):
        assert proximity_bonus(window_width=1, term_count=2) == 1.0

    def test_the_decay_is_linear_to_the_horizon(self):
        halfway = proximity_bonus(
            window_width=5, term_count=2, horizon=8
        )
        assert halfway == 0.5

    def test_past_the_horizon_earns_exactly_nothing(self):
        assert proximity_bonus(window_width=9, term_count=2, horizon=8) == 0.0

    def test_single_terms_earn_zero_by_definition(self):
        assert proximity_bonus(window_width=0, term_count=1) == 0.0

    def test_impossible_widths_are_refused(self):
        with pytest.raises(Invalid, match="cannot hold"):
            proximity_bonus(window_width=0, term_count=2)


class TestNear:
    def test_within_zero_is_adjacency(self):
        assert near(prose(), "body", ["black", "cat"], within=0) == [0]

    def test_a_wider_allowance_admits_the_stragglers(self):
        found = near(prose(), "body", ["black", "cat"], within=5)
        assert found == [0, 1, 2]

    def test_negative_nearness_is_refused(self):
        with pytest.raises(Invalid, match="overlap"):
            near(prose(), "body", ["black", "cat"], within=-1)
