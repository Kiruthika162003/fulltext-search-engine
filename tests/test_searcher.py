from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.query import parse
from quarry.schema import Schema
from quarry.searcher import search
from quarry.segment import Segment, SegmentBuilder


def library() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.add_keyword("author")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add(
        {"body": "the black cat sat on the mat", "author": "meera"}
    )
    builder.add({"body": "a black dog chased the black cat", "author": "raj"})
    builder.add({"body": "dogs and cats living together", "author": "meera"})
    builder.add({"body": "a quiet study of xylophones", "author": "dana"})
    return builder.seal("s0")


def docs(segment: Segment, text: str) -> list[int]:
    return [hit.doc for hit in search(segment, parse(text))]


class TestMatching:
    def test_bare_terms_union_and_rank(self):
        assert set(docs(library(), "cat")) == {0, 1, 2}

    def test_required_terms_intersect(self):
        assert docs(library(), "+black +cat") == [1, 0]

    def test_prohibited_terms_subtract(self):
        assert set(docs(library(), "cat -dog")) == {0}

    def test_phrases_prove_adjacency(self):
        assert docs(library(), '"black cat"') == [1, 0]
        assert docs(library(), '"cat dog"') == []

    def test_keyword_fields_match_exactly(self):
        assert set(docs(library(), "+author:meera cat")) == {0, 2}

    def test_or_widens(self):
        assert set(docs(library(), "xylophones OR dog")) == {1, 2, 3}


class TestRanking:
    def test_more_mentions_rank_higher(self):
        segment = library()
        hits = search(segment, parse("black"))
        assert hits[0].doc == 1
        assert hits[0].score > hits[1].score

    def test_rare_terms_outrank_common_ones(self):
        segment = library()
        hits = search(segment, parse("xylophones cats"))
        assert hits[0].doc == 3

    def test_ties_break_by_doc_id(self):
        schema = Schema()
        schema.add_text("body")
        schema.seal()
        builder = SegmentBuilder(schema=schema)
        builder.add({"body": "same words here"})
        builder.add({"body": "same words here"})
        segment = builder.seal("twin")
        hits = search(segment, parse("same words"))
        assert [hit.doc for hit in hits] == [0, 1]
        assert hits[0].score == hits[1].score

    def test_the_limit_caps_the_page(self):
        segment = library()
        assert len(search(segment, parse("cat OR dog"), limit=2)) == 2

    def test_a_zero_limit_is_refused(self):
        with pytest.raises(Invalid):
            search(library(), parse("cat"), limit=0)


class TestTombstones:
    def test_deleted_docs_leave_the_results(self):
        segment = library()
        segment.delete(1)
        assert set(docs(segment, "black")) == {0}

    def test_the_survivors_keep_their_scores(self):
        segment = library()
        before = {h.doc: h.score for h in search(segment, parse("cat"))}
        segment.delete(2)
        after = {h.doc: h.score for h in search(segment, parse("cat"))}
        assert after[0] == before[0]
