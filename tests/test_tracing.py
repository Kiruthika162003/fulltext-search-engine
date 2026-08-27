from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.tracing import Span, slowest_path


def traced_request() -> Span:
    root = Span(name="search", start=0)
    parse = root.child("parse", 0)
    parse.finish(5)
    retrieve = root.child("retrieve", 5)
    lookup = retrieve.child("postings", 6)
    lookup.finish(40)
    retrieve.finish(55)
    retrieve.tag("segments", "3")
    score = root.child("score", 55)
    score.finish(80)
    root.finish(100)
    return root


class TestSpans:
    def test_durations_are_arithmetic(self):
        root = traced_request()
        assert root.duration() == 100
        assert root.children[1].duration() == 50

    def test_time_cannot_run_backwards(self):
        span = Span(name="odd", start=10)
        with pytest.raises(Invalid, match="cannot end at"):
            span.finish(5)

    def test_children_cannot_predate_parents(self):
        root = Span(name="search", start=10)
        with pytest.raises(Invalid, match="before its"):
            root.child("early", 5)

    def test_children_cannot_outlive_parents(self):
        root = Span(name="search", start=0)
        child = root.child("late", 1)
        child.finish(50)
        root.finish(10)
        with pytest.raises(Invalid, match="impossible"):
            root.render()

    def test_double_finishing_is_refused(self):
        span = Span(name="x", start=0)
        span.finish(5)
        with pytest.raises(Invalid, match="already finished"):
            span.finish(6)


class TestRendering:
    def test_the_tree_indents_with_shares(self):
        page = traced_request().render()
        lines = page.splitlines()
        assert lines[0] == "search: 100"
        assert "  parse: 5 (5% of search)" in page
        assert "50% of search" in page
        assert "68% of retrieve" in page

    def test_tags_ride_along(self):
        page = traced_request().render()
        assert "{segments=3}" in page

    def test_unexplained_time_is_named(self):
        page = traced_request().render()
        assert "[unexplained: 20 inside search" in page
        assert "next surprise" in page


class TestTheSlowLane:
    def test_the_fattest_children_form_the_path(self):
        assert slowest_path(traced_request()) == [
            "search",
            "retrieve",
            "postings",
        ]
