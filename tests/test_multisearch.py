from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.merge import MergePlan, merge
from quarry.multisearch import search_index
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index


def opened(flush_at: int = 2) -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    return Index(schema=schema, flush_at=flush_at)


def corpus() -> Index:
    index = opened(flush_at=2)
    index.add({"body": "the black cat sat"})
    index.add({"body": "a black dog ran far and wide today"})
    index.add({"body": "cats everywhere cats"})
    index.add({"body": "a quiet xylophone"})
    index.flush()
    return index


class TestGlobalStatistics:
    def test_results_carry_external_ids(self):
        page = search_index(corpus(), parse("cat"))
        assert {hit.external for hit in page.hits} == {0, 2}

    def test_ranking_ignores_segment_boundaries(self):
        split = corpus()
        merged = corpus()
        merge(
            merged,
            MergePlan(segment_names=("seg0", "seg1"), reason="test"),
        )
        split_page = search_index(split, parse("black cat"))
        merged_page = search_index(merged, parse("black cat"))
        assert [
            (hit.external, hit.score) for hit in split_page.hits
        ] == [(hit.external, hit.score) for hit in merged_page.hits]

    def test_rare_terms_win_across_segments(self):
        page = search_index(corpus(), parse("xylophone cats"))
        assert page.hits[0].external == 3

    def test_deletes_disappear_from_answers(self):
        index = corpus()
        index.delete(2)
        page = search_index(index, parse("cat"))
        assert {hit.external for hit in page.hits} == {0}


class TestPagination:
    def wide(self) -> Index:
        index = opened(flush_at=3)
        for number in range(9):
            index.add({"body": f"common word row {number}"})
        index.flush()
        return index

    def test_pages_walk_without_overlap(self):
        index = self.wide()
        first = search_index(index, parse("common"), limit=4)
        assert len(first.hits) == 4
        assert first.token is not None
        second = search_index(
            index, parse("common"), limit=4, after=first.token
        )
        third = search_index(
            index, parse("common"), limit=4, after=second.token
        )
        walked = [
            hit.external
            for page in (first, second, third)
            for hit in page.hits
        ]
        assert sorted(walked) == list(range(9))
        assert len(set(walked)) == 9

    def test_the_last_page_carries_no_token(self):
        index = self.wide()
        first = search_index(index, parse("common"), limit=4)
        second = search_index(
            index, parse("common"), limit=4, after=first.token
        )
        third = search_index(
            index, parse("common"), limit=4, after=second.token
        )
        assert third.token is None

    def test_a_flush_between_pages_does_not_break_the_walk(self):
        index = self.wide()
        first = search_index(index, parse("common"), limit=4)
        index.add({"body": "common newcomer"})
        index.flush()
        second = search_index(
            index, parse("common"), limit=20, after=first.token
        )
        seen = {hit.external for hit in first.hits} | {
            hit.external for hit in second.hits
        }
        assert set(range(9)) <= seen

    def test_a_zero_limit_is_refused(self):
        with pytest.raises(Invalid):
            search_index(corpus(), parse("cat"), limit=0)
