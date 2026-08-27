from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.seginspect import (
    field_profile,
    hot_terms,
    interrogate,
    posting_histogram,
    shape_summary,
)
from quarry.segment import Segment, SegmentBuilder


def prose() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "cat cat cat dog"})
    builder.add({"body": "cat dog bird"})
    builder.add({"body": "quiet evening"})
    segment = builder.seal("prose")
    segment.delete(2)
    return segment


def serials() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "sku1001 sku1002 sku1003 sku1004 shared"})
    builder.add({"body": "sku2001 sku2002 sku2003 sku2004 shared"})
    return builder.seal("serials")


class TestTheSummary:
    def test_shape_counts_live_and_dead(self):
        assert shape_summary(prose()) == (
            "prose: 2 live + 1 dead = 3 documents, 5 distinct "
            "field-terms"
        )

    def test_hot_terms_rank_by_occurrences(self):
        top = hot_terms(prose(), limit=2)
        assert top[0].term == "cat"
        assert top[0].occurrences == 4
        assert top[1].term == "dog"

    def test_zero_rows_are_refused(self):
        with pytest.raises(Invalid):
            hot_terms(prose(), limit=0)

    def test_the_field_profile_states_its_units(self):
        profile = field_profile(prose())
        assert profile == "body: 9 terms total, 3.0 terms per document"


class TestTheHistogram:
    def test_buckets_count_list_lengths(self):
        histogram = posting_histogram(prose())
        assert histogram["1 doc"] == 3
        assert histogram["2-10 docs"] == 2

    def test_the_serial_number_smell_is_called_out(self):
        page = interrogate(serials())
        assert "smells of serial numbers" in page

    def test_healthy_prose_earns_no_note(self):
        page = interrogate(prose())
        assert "smells of serial numbers" not in page

    def test_the_interrogation_reads_top_to_bottom(self):
        page = interrogate(prose())
        lines = page.splitlines()
        assert lines[0].startswith("prose: 2 live")
        assert "hot terms:" in lines
        assert "posting list sizes:" in lines
