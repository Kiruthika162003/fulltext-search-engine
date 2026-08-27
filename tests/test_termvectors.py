from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder
from quarry.termvectors import (
    cosine_similarity,
    keywords,
    term_vector,
    vector_page,
)


def shelf() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "copper kettle copper pot"})
    builder.add({"body": "copper kettle on the stove"})
    builder.add({"body": "wool blanket by the fire"})
    return builder.seal("shelf")


class TestVectors:
    def test_the_vector_reads_from_the_postings(self):
        entries = term_vector(shelf(), 0)
        by_term = {entry.term: entry for entry in entries}
        assert by_term["copper"].frequency == 2
        assert by_term["copper"].positions == (0, 2)
        assert by_term["kettle"].frequency == 1

    def test_deleted_documents_refuse_description(self):
        segment = shelf()
        segment.delete(0)
        with pytest.raises(Invalid, match="deleted content leaks"):
            term_vector(segment, 0)

    def test_nonexistent_documents_are_refused(self):
        with pytest.raises(Invalid, match="does not exist"):
            term_vector(shelf(), 9)


class TestKeywords:
    def test_frequent_here_and_rare_elsewhere_wins(self):
        top = keywords(shelf(), 0, top_n=2)
        assert top == ["copper", "pot"]
        assert "kettle" not in top

    def test_common_words_rank_below_distinctive_ones(self):
        top = keywords(shelf(), 2, top_n=3)
        assert "copper" not in top

    def test_zero_keywords_describe_nothing(self):
        with pytest.raises(Invalid, match="describe nothing"):
            keywords(shelf(), 0, top_n=0)


class TestSimilarity:
    def test_kindred_documents_score_high(self):
        assert cosine_similarity(shelf(), 0, 1) > 0.5

    def test_strangers_score_zero(self):
        assert cosine_similarity(shelf(), 0, 2) == 0.0

    def test_a_document_matches_itself_perfectly(self):
        assert cosine_similarity(shelf(), 0, 0) == 1.0


class TestThePage:
    def test_the_page_shows_frequency_and_positions(self):
        page = vector_page(shelf(), 0)
        assert page.startswith("doc 0:")
        assert "body:copper x2 at [0, 2]" in page
