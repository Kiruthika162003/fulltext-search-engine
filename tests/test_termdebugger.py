from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder
from quarry.termdebugger import (
    trace_term,
    why_matched,
    why_not_matched,
)
from quarry.tokenize import Analyzer


def library() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "the black cat sat on the mat"})
    builder.add({"body": "a dog walked the long road"})
    builder.add({"body": "cats and dogs together at last"})
    segment = builder.seal("library")
    segment.delete(2)
    return segment


class TestTracing:
    def test_a_present_term_shows_its_frequency(self):
        held = trace_term(library(), Analyzer(), "body", "cat", 0)
        assert held.present
        assert held.frequency == 1
        assert held.line() == "'cat': present, frequency 1"

    def test_the_analyzed_form_is_shown_when_it_differs(self):
        held = trace_term(library(), Analyzer(), "body", "Cats", 0)
        assert held.analyzed == "cat"
        assert "'Cats' -> 'cat'" in held.line()

    def test_stopwords_trace_to_nothing(self):
        held = trace_term(library(), Analyzer(), "body", "the", 0)
        assert held.analyzed is None
        assert "cannot match" in held.line()


class TestWhyMatched:
    def test_the_verdict_counts_present_terms(self):
        page = why_matched(
            library(), Analyzer(), "body", ["cat", "mat", "dog"], 0
        )
        assert "verdict: 2 of 3 terms present in doc 0" in page

    def test_tombstoned_documents_are_named_first(self):
        page = why_matched(library(), Analyzer(), "body", ["cat"], 2)
        assert "tombstoned" in page

    def test_empty_queries_are_refused(self):
        with pytest.raises(Invalid, match="query was empty"):
            why_matched(library(), Analyzer(), "body", [], 0)


class TestWhyNot:
    def test_absence_lists_documents_that_do_hold_it(self):
        page = why_not_matched(
            library(), Analyzer(), "body", "dog", 0
        )
        assert "not in doc 0" in page
        assert "start with 1, 2" in page

    def test_presence_redirects_the_blame(self):
        page = why_not_matched(
            library(), Analyzer(), "body", "cat", 0
        )
        assert "IS present" in page
        assert "the reason is elsewhere" in page

    def test_a_term_absent_everywhere_says_nowhere(self):
        page = why_not_matched(
            library(), Analyzer(), "body", "zeppelin", 0
        )
        assert "appears nowhere" in page

    def test_deleted_documents_answer_with_the_tombstone(self):
        page = why_not_matched(
            library(), Analyzer(), "body", "cat", 2
        )
        assert "no term can match a tombstone" in page

    def test_nonexistent_documents_are_refused(self):
        with pytest.raises(Invalid, match="does not exist"):
            why_not_matched(library(), Analyzer(), "body", "cat", 9)
