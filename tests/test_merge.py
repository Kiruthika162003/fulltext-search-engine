from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.merge import TIER_FANOUT, MergePlan, maintain, merge, plan_merge
from quarry.query import parse
from quarry.schema import Schema
from quarry.searcher import search
from quarry.writer import Index


def opened(flush_at: int = 2) -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    return Index(schema=schema, flush_at=flush_at)


def stocked(docs: int = 8) -> Index:
    index = opened(flush_at=2)
    for number in range(docs):
        index.add({"body": f"document number {number} about cats"})
    index.flush()
    return index


class TestPlanning:
    def test_few_clean_segments_need_nothing(self):
        index = stocked(docs=4)
        assert len(index.segments) == 2
        assert plan_merge(index) is None

    def test_enough_segments_trigger_a_tier(self):
        index = stocked(docs=8)
        plan = plan_merge(index)
        assert plan is not None
        assert plan.reason.startswith("tier")
        assert len(plan.segment_names) == TIER_FANOUT

    def test_waste_overrides_size(self):
        index = stocked(docs=4)
        index.delete(0)
        plan = plan_merge(index)
        assert plan is not None
        assert plan.reason.startswith("waste")
        assert plan.segment_names == ("seg0",)


class TestMerging:
    def test_the_merge_drops_the_dead_and_renumbers(self):
        index = stocked(docs=8)
        index.delete(2)
        merged = merge(
            index, MergePlan(segment_names=("seg0", "seg1"), reason="test")
        )
        assert merged.doc_count() == 3
        assert merged.tombstones == set()

    def test_bookmarks_move_with_the_merge(self):
        index = stocked(docs=4)
        merge(
            index, MergePlan(segment_names=("seg0", "seg1"), reason="test")
        )
        assert index.document(3) == {"body": "document number 3 about cats"}
        assert index.locations[3][0] == "seg2"

    def test_deleted_ids_stay_deleted_after_the_move(self):
        index = stocked(docs=4)
        index.delete(1)
        merge(
            index, MergePlan(segment_names=("seg0", "seg1"), reason="test")
        )
        with pytest.raises(Missing):
            index.document(1)

    def test_search_answers_the_same_before_and_after(self):
        index = stocked(docs=8)
        index.delete(5)
        query = parse("cats")

        def answers() -> set[int]:
            found = set()
            for segment in index.segments:
                for hit in search(segment, query, limit=100):
                    found.add(index.external_id(segment.name, hit.doc))
            return found

        before = answers()
        maintain(index)
        assert answers() == before

    def test_an_all_dead_plan_drops_the_segments(self):
        index = stocked(docs=2)
        index.delete(0)
        index.delete(1)
        with pytest.raises(Invalid, match="nothing to seal"):
            merge(
                index, MergePlan(segment_names=("seg0",), reason="test")
            )
        assert index.segments == []

    def test_absent_segments_are_refused_by_name(self):
        with pytest.raises(Invalid, match="ghost"):
            merge(
                stocked(docs=2),
                MergePlan(segment_names=("ghost",), reason="test"),
            )


class TestMaintenance:
    def test_maintain_runs_to_quiescence(self):
        index = stocked(docs=16)
        taken = maintain(index)
        assert taken
        assert plan_merge(index) is None
        assert index.searchable_count() == 16
