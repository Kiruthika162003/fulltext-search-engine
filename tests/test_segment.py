from __future__ import annotations

import pytest

from quarry.errors import Frozen, Invalid, Missing
from quarry.schema import Schema
from quarry.segment import SegmentBuilder


def sealed_schema() -> Schema:
    schema = Schema()
    schema.add_text("body")
    schema.add_keyword("author")
    schema.add_numeric("year")
    schema.seal()
    return schema


def built() -> SegmentBuilder:
    builder = SegmentBuilder(schema=sealed_schema())
    builder.add({"body": "the black cat sat", "author": "meera", "year": 2020})
    builder.add({"body": "a black dog ran", "author": "raj", "year": 2021})
    builder.add({"body": "cats and dogs", "author": "meera", "year": 2021})
    return builder


class TestBuilding:
    def test_an_unsealed_schema_is_refused(self):
        with pytest.raises(Invalid, match="seal the schema"):
            SegmentBuilder(schema=Schema())

    def test_doc_ids_are_dense_from_zero(self):
        builder = SegmentBuilder(schema=sealed_schema())
        assert builder.add({"body": "one"}) == 0
        assert builder.add({"body": "two"}) == 1

    def test_unknown_fields_are_refused(self):
        builder = SegmentBuilder(schema=sealed_schema())
        with pytest.raises(Missing):
            builder.add({"ghost": "value"})

    def test_numeric_fields_take_integers_only(self):
        builder = SegmentBuilder(schema=sealed_schema())
        with pytest.raises(Invalid, match="not an integer"):
            builder.add({"year": "soon"})

    def test_an_empty_segment_cannot_seal(self):
        with pytest.raises(Invalid):
            SegmentBuilder(schema=sealed_schema()).seal("empty")

    def test_a_sealed_builder_is_done(self):
        builder = built()
        builder.seal("s0")
        with pytest.raises(Frozen):
            builder.add({"body": "late"})
        with pytest.raises(Frozen):
            builder.seal("again")


class TestTheSegment:
    def test_text_postings_carry_positions(self):
        segment = built().seal("s0")
        held = segment.postings_for("body", "black")
        assert held.docs() == [0, 1]
        assert held.find(0).positions == (0,)

    def test_keywords_match_exactly_unanalyzed(self):
        segment = built().seal("s0")
        assert segment.postings_for("author", "meera").docs() == [0, 2]
        assert segment.postings_for("author", "Meera") is None

    def test_numerics_index_in_sortable_form(self):
        segment = built().seal("s0")
        assert segment.postings_for("year", f"{2021:020d}").docs() == [1, 2]

    def test_field_lengths_feed_ranking(self):
        segment = built().seal("s0")
        assert segment.field_length("body", 0) == 3
        assert segment.average_field_length("body") == pytest.approx(2.67, abs=0.01)

    def test_the_vocabulary_is_sorted(self):
        segment = built().seal("s0")
        assert segment.vocabulary("author") == ["meera", "raj"]


class TestTombstones:
    def test_a_delete_is_a_bit_not_surgery(self):
        segment = built().seal("s0")
        segment.delete(1)
        assert segment.live_count() == 2
        assert segment.postings_for("body", "black").docs() == [0, 1]
        assert not segment.is_live(1)

    def test_a_deleted_document_names_its_tombstone(self):
        segment = built().seal("s0")
        segment.delete(1)
        with pytest.raises(Missing, match="tombstone"):
            segment.document(1)

    def test_waste_is_a_measured_share(self):
        segment = built().seal("s0")
        segment.delete(0)
        assert segment.waste_share() == pytest.approx(1 / 3)
